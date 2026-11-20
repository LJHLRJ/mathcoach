"""每日挑战：确定性选题、限时、判题、错题与结果持久化。"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from mathcoach.content.loader import load_content
from mathcoach.domain.judge import evaluate
from mathcoach.domain.models import (
    Consent,
    Difficulty,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    Stage,
)
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.session.daily import (
    DailyQuestion,
    DailyState,
    build_daily_questions,
    record_daily_mistake,
    remaining_seconds,
    save_daily_result,
    submit_daily_answer,
)

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def _card() -> KnowledgeCard:
    exercise = Exercise(
        id="test-e1",
        card_id="test-card",
        kind=ExerciseKind.CHOICE,
        stem="2+2=?",
        answer="4",
        solution_outline="直接相加",
        options=("3", "4"),
        variants=("3+3=?",),
    )
    return KnowledgeCard(
        id="test-card",
        name="测试卡片",
        stage=Stage.HIGH_SCHOOL,
        course="测试课",
        chapter="测试",
        difficulty=Difficulty.BASIC,
        intuition="",
        definition="",
        mistakes=(),
        example="",
        exercises=(exercise,),
        source="智能体生成",
    )


def _state(started_at: datetime = NOW) -> DailyState:
    card = _card()
    return DailyState(
        date_key=NOW.date().isoformat(),
        questions=(DailyQuestion(card, card.exercises[0]),),
        started_at=started_at,
    )


def test_daily_questions_are_deterministic_and_cover_stages():
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    day = date(2026, 11, 20)
    first = build_daily_questions(cards, day)
    second = build_daily_questions(cards, day)

    assert len(first) == 5
    assert [item.exercise.id for item in first] == [
        item.exercise.id for item in second
    ]
    assert len({item.card.id for item in first}) == 5
    assert {item.card.stage for item in first} == {
        Stage.HIGH_SCHOOL,
        Stage.UNDERGRADUATE,
        Stage.GRADUATE,
    }
    assert all(evaluate(item.exercise, item.exercise.answer).correct for item in first)


def test_correct_answer_advances_and_finishes():
    state = _state()
    submission = submit_daily_answer(state, "4", NOW + timedelta(seconds=10))

    assert submission is not None
    assert submission.correct is True
    assert state.correct == 1
    assert state.index == 1
    assert state.finished is True


def test_wrong_answer_reports_solution():
    state = _state()
    submission = submit_daily_answer(state, "3", NOW + timedelta(seconds=10))

    assert submission is not None
    assert submission.correct is False
    assert "标准思路" in submission.feedback


def test_injection_answer_is_not_counted_or_advanced():
    state = _state()
    submission = submit_daily_answer(
        state, "x = __import__('os')", NOW + timedelta(seconds=10)
    )

    assert submission is not None
    assert submission.correct is None
    assert state.index == 0
    assert state.correct == 0
    assert "不能执行" in submission.feedback


def test_timeout_ends_challenge_without_scoring():
    state = _state(NOW - timedelta(seconds=301))
    assert remaining_seconds(state, NOW) == 0

    submission = submit_daily_answer(state, "4", NOW)
    assert submission is None
    assert state.finished is True
    assert state.timed_out is True


def test_wrong_daily_answer_enters_mistake_book_with_variants():
    repository = InMemoryRepository()
    card = _card()
    question = DailyQuestion(card, card.exercises[0])

    record_daily_mistake(repository, Consent(), question, "3", NOW)

    mistakes = repository.list_mistakes()
    assert len(mistakes) == 1
    assert mistakes[0].user_answer == "3"
    assert mistakes[0].exercise_snapshot["variants"] == ["3+3=?"]
    assert any(entry.op == "mistake" for entry in repository.list_audit())


def test_daily_result_is_persisted():
    repository = InMemoryRepository()
    state = _state()
    submit_daily_answer(state, "4", NOW + timedelta(seconds=30))

    result = save_daily_result(repository, Consent(), state, NOW + timedelta(seconds=30))
    assert result is not None
    assert result.correct == 1
    assert result.total == 1
    assert repository.get_daily_result(state.date_key) == result
    assert any(entry.op == "daily" and entry.result == "ok" for entry in repository.list_audit())


def test_daily_result_is_not_written_without_memory_consent():
    repository = InMemoryRepository()
    state = _state()
    submit_daily_answer(state, "4", NOW + timedelta(seconds=30))

    result = save_daily_result(
        repository,
        Consent(memory=False, mistake_book=True),
        state,
        NOW + timedelta(seconds=30),
    )
    assert result is None
    assert repository.get_daily_result(state.date_key) is None
    assert any(entry.result.startswith("blocked") for entry in repository.list_audit())
