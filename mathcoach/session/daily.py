"""每日挑战：确定性 5 题、5 分钟限时，结果可持久化。"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime
from uuid import uuid4

from ..domain.diagnosis import diagnose
from ..domain.judge import evaluate
from ..domain.models import (
    Consent,
    DailyResult,
    Exercise,
    KnowledgeCard,
    MistakeEntry,
)
from ..memory.repository import Repository
from ..safety.guards import REFUSAL_TEXT, detect_injection
from ..safety.redlines import (
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
)

DAILY_QUESTION_COUNT = 5
DAILY_TIME_LIMIT_S = 300


@dataclass(frozen=True)
class DailyQuestion:
    card: KnowledgeCard
    exercise: Exercise


@dataclass(frozen=True)
class DailySubmission:
    question: DailyQuestion
    correct: bool | None
    feedback: str


@dataclass
class DailyState:
    date_key: str
    questions: tuple[DailyQuestion, ...]
    started_at: datetime
    index: int = 0
    correct: int = 0
    finished: bool = False
    timed_out: bool = False
    feedback: str = ""


def build_daily_questions(
    cards: list[KnowledgeCard], day: date, count: int = DAILY_QUESTION_COUNT
) -> tuple[DailyQuestion, ...]:
    """同一天、同一内容集合下结果稳定；优先每个学段各取一题。"""
    pool = sorted(
        ((card, exercise) for card in cards for exercise in card.exercises),
        key=lambda pair: (pair[0].id, pair[1].id),
    )
    if not pool:
        return ()

    rng = random.Random(day.toordinal())
    by_stage: dict[str, list[tuple[KnowledgeCard, Exercise]]] = {}
    for card, exercise in pool:
        by_stage.setdefault(card.stage.value, []).append((card, exercise))

    selected: list[DailyQuestion] = []
    used_cards: set[str] = set()
    for stage in sorted(by_stage):
        candidates = list(by_stage[stage])
        rng.shuffle(candidates)
        for card, exercise in candidates:
            if card.id not in used_cards:
                selected.append(DailyQuestion(card, exercise))
                used_cards.add(card.id)
                break

    remaining = list(pool)
    rng.shuffle(remaining)
    for card, exercise in remaining:
        if len(selected) >= count:
            break
        if card.id in used_cards:
            continue
        selected.append(DailyQuestion(card, exercise))
        used_cards.add(card.id)
    return tuple(selected[:count])


def elapsed_seconds(state: DailyState, now: datetime) -> int:
    return max(0, int((now - state.started_at).total_seconds()))


def remaining_seconds(state: DailyState, now: datetime) -> int:
    return max(0, DAILY_TIME_LIMIT_S - elapsed_seconds(state, now))


def time_is_up(state: DailyState, now: datetime) -> bool:
    return remaining_seconds(state, now) <= 0


def current_question(state: DailyState) -> DailyQuestion | None:
    if state.finished or state.index >= len(state.questions):
        return None
    return state.questions[state.index]


def finish_daily(state: DailyState, now: datetime, timed_out: bool = False) -> None:
    if state.finished:
        return
    state.finished = True
    state.timed_out = timed_out
    if timed_out:
        state.feedback = "时间到，本次挑战结束。"


def submit_daily_answer(
    state: DailyState, answer: str, now: datetime
) -> DailySubmission | None:
    question = current_question(state)
    if question is None:
        return None
    if time_is_up(state, now):
        finish_daily(state, now, timed_out=True)
        return None
    blocked = detect_injection(answer)
    if blocked is not None:
        state.feedback = f"{REFUSAL_TEXT} 本次不计分。"
        return DailySubmission(question, None, state.feedback)

    judgement = evaluate(question.exercise, answer)
    if judgement.correct is True:
        state.correct += 1
        feedback = "答对了。"
    elif judgement.correct is False:
        feedback = f"答错了。标准思路：{question.exercise.solution_outline}"
    else:
        feedback = "这一步无法自动核对，建议人工复核。"

    state.index += 1
    state.feedback = feedback
    if state.index >= len(state.questions):
        finish_daily(state, now)
    return DailySubmission(question, judgement.correct, feedback)


def build_daily_result(state: DailyState, now: datetime) -> DailyResult:
    return DailyResult(
        date=state.date_key,
        correct=state.correct,
        total=len(state.questions),
        duration_s=min(DAILY_TIME_LIMIT_S, elapsed_seconds(state, now)),
        completed_at=now,
    )


def record_daily_mistake(
    repository: Repository,
    consent: Consent,
    question: DailyQuestion,
    answer: str,
    now: datetime,
) -> None:
    if not consent.mistake_book:
        return
    try:
        assert_write_allowed("mistake", consent=consent)
    except (WriteBlocked, ConfirmationRequired) as exc:
        repository.record_audit("mistake", f"blocked:{exc.reason}")
        return
    exercise = question.exercise
    repository.save_mistake(
        MistakeEntry(
            id=uuid4().hex,
            exercise_id=exercise.id,
            card_id=question.card.id,
            stage=question.card.stage,
            course=question.card.course,
            exercise_type=exercise.kind,
            stem=exercise.stem,
            user_answer=answer,
            correct_answer=exercise.answer,
            error_type=diagnose(exercise, [answer]).error_type,
            max_hint_level=1,
            created_at=now,
            exercise_snapshot={
                "id": exercise.id,
                "kind": exercise.kind.value,
                "stem": exercise.stem,
                "options": list(exercise.options),
                "solution_outline": exercise.solution_outline,
                "variants": list(exercise.variants),
            },
        )
    )
    repository.record_audit("mistake", "ok")


def save_daily_result(
    repository: Repository, consent: Consent, state: DailyState, now: datetime
) -> DailyResult | None:
    try:
        assert_write_allowed("daily", consent=consent)
    except (WriteBlocked, ConfirmationRequired) as exc:
        repository.record_audit("daily", f"blocked:{exc.reason}")
        return None
    result = build_daily_result(state, now)
    repository.save_daily_result(result)
    repository.record_audit("daily", "ok")
    return result
