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
    """每日挑战的一道题。

    Attributes:
        card: 所属知识点卡。
        exercise: 题目。
    """

    card: KnowledgeCard
    exercise: Exercise


@dataclass(frozen=True)
class DailySubmission:
    """一次每日作答的结果。

    Attributes:
        question: 对应题目。
        correct: 判定结果，无法自动核对时为 None。
        feedback: 反馈文案。
    """

    question: DailyQuestion
    correct: bool | None
    feedback: str


@dataclass
class DailyState:
    """每日挑战的可变状态。

    Attributes:
        date_key: 日期键，挑战赛用 ``challenge-<seed>``。
        questions: 题目序列。
        started_at: 开始时间。
        time_limit_s: 限时秒数。
        index: 当前题下标。
        correct: 答对题数。
        finished: 是否已结束。
        timed_out: 是否超时结束。
        feedback: 最近一次反馈。
        persisted: 是否已持久化。
    """

    date_key: str
    questions: tuple[DailyQuestion, ...]
    started_at: datetime
    time_limit_s: int = DAILY_TIME_LIMIT_S
    index: int = 0
    correct: int = 0
    finished: bool = False
    timed_out: bool = False
    feedback: str = ""
    persisted: bool = False


def build_quiz_questions(
    cards: list[KnowledgeCard], seed: int, count: int = DAILY_QUESTION_COUNT
) -> tuple[DailyQuestion, ...]:
    """给定种子确定性抽题，优先每个学段各取一题。

    Args:
        cards: 知识点卡。
        seed: 随机种子。
        count: 题目上限。

    Returns:
        按卡去重的题目元组，最多 ``count`` 道。
    """
    pool = sorted(
        ((card, exercise) for card in cards for exercise in card.exercises),
        key=lambda pair: (pair[0].id, pair[1].id),
    )
    if not pool:
        return ()

    rng = random.Random(seed)
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


def build_daily_questions(
    cards: list[KnowledgeCard], day: date, count: int = DAILY_QUESTION_COUNT
) -> tuple[DailyQuestion, ...]:
    """用日期序数当种子抽题，同一天结果稳定。

    Args:
        cards: 知识点卡。
        day: 日期。
        count: 题目上限。

    Returns:
        题目元组。
    """
    return build_quiz_questions(cards, day.toordinal(), count)


def elapsed_seconds(state: DailyState, now: datetime) -> int:
    """返回已用秒数，负值按 0 计。"""
    return max(0, int((now - state.started_at).total_seconds()))


def remaining_seconds(state: DailyState, now: datetime) -> int:
    """返回剩余秒数，不小于 0。"""
    return max(0, state.time_limit_s - elapsed_seconds(state, now))


def time_is_up(state: DailyState, now: datetime) -> bool:
    """剩余时间归零时返回 True。"""
    return remaining_seconds(state, now) <= 0


def current_question(state: DailyState) -> DailyQuestion | None:
    """返回当前题；已结束或越界时返回 None。"""
    if state.finished or state.index >= len(state.questions):
        return None
    return state.questions[state.index]


def finish_daily(state: DailyState, now: datetime, timed_out: bool = False) -> None:
    """结束本次挑战。

    重复调用无副作用；超时结束时写入固定反馈。

    Args:
        state: 每日挑战状态，原地修改。
        now: 当前时间，当前未参与判定。
        timed_out: 是否因超时结束。
    """
    if state.finished:
        return
    state.finished = True
    state.timed_out = timed_out
    if timed_out:
        state.feedback = "时间到，本次挑战结束。"


def submit_daily_answer(
    state: DailyState, answer: str, now: datetime
) -> DailySubmission | None:
    """提交一道每日挑战作答。

    先检查当前题与剩余时间，再做注入检测和判分；无法自动核对时
    不计分也不判错。

    Args:
        state: 每日挑战状态，原地修改。
        answer: 作答文本。
        now: 当前时间。

    Returns:
        提交结果；没有当前题或已超时返回 None。
    """
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
    """把当前状态整理成可持久化的日挑战结果。"""
    return DailyResult(
        date=state.date_key,
        correct=state.correct,
        total=len(state.questions),
        duration_s=min(state.time_limit_s, elapsed_seconds(state, now)),
        completed_at=now,
    )


def record_daily_mistake(
    repository: Repository,
    consent: Consent,
    question: DailyQuestion,
    answer: str,
    now: datetime,
) -> None:
    """把每日挑战中的错题写入错题本。

    未开启错题本时直接返回；写入门被拦时只记审计。

    Args:
        repository: 仓储。
        consent: 授权状态。
        question: 当前题目。
        answer: 作答文本。
        now: 当前时间。
    """
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
    """保存每日挑战结果。

    Args:
        repository: 仓储。
        consent: 授权状态。
        state: 每日挑战状态。
        now: 当前时间。

    Returns:
        保存后的结果；写入门拒绝时返回 None。
    """
    try:
        assert_write_allowed("daily", consent=consent)
    except (WriteBlocked, ConfirmationRequired) as exc:
        repository.record_audit("daily", f"blocked:{exc.reason}")
        return None
    result = build_daily_result(state, now)
    repository.save_daily_result(result)
    repository.record_audit("daily", "ok")
    return result
