"""学习仪表盘：只读聚合与空状态。"""
from datetime import datetime, timezone

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    Stage,
)
from mathcoach.memory.dashboard import build_dashboard
from mathcoach.memory.repository import InMemoryRepository

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


def _receipt(identifier: str, independence: Independence, hint: int) -> Receipt:
    return Receipt(
        id=identifier,
        card_id="card-1",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=30,
        max_hint_level=hint,
        goal="练函数",
        independence=independence,
        created_at=NOW,
    )


def _mistake(
    identifier: str, exercise_id: str, course: str, error: ErrorType
) -> MistakeEntry:
    return MistakeEntry(
        id=identifier,
        exercise_id=exercise_id,
        card_id="card-1",
        stage=Stage.HIGH_SCHOOL,
        course=course,
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错答",
        correct_answer="正确",
        error_type=error,
        max_hint_level=1,
        created_at=NOW,
    )


def test_dashboard_aggregates_learning_data():
    repository = InMemoryRepository()
    repository.save_receipt(
        _receipt("r1", Independence.INDEPENDENT, 1), "e1"
    )
    repository.save_receipt(
        _receipt("r2", Independence.SEMI_INDEPENDENT, 4), "e2"
    )
    repository.save_mistake(_mistake("m1", "e1", "函数与导数", ErrorType.CONCEPT))
    repository.save_mistake(_mistake("m2", "e2", "高等数学", ErrorType.CALCULATION))
    repository.save_mistake(_mistake("m3", "e3", "函数与导数", ErrorType.FORMULA))

    repository.record_review("e1", True, NOW)
    repository.record_review("e1", True, NOW)
    repository.record_review("e2", True, NOW)

    summary = build_dashboard(repository, NOW)
    assert summary.receipts == 2
    assert summary.independent == 1
    assert summary.semi_independent == 1
    assert summary.average_hint_level == 2.5
    assert summary.mistakes == 3
    assert summary.unreviewed == 1
    assert summary.reviewing == 1
    assert summary.mastered == 1
    assert summary.due_today == 1
    assert dict(summary.top_errors) == {
        ErrorType.CONCEPT.value: 1,
        ErrorType.CALCULATION.value: 1,
        ErrorType.FORMULA.value: 1,
    }
    assert dict(summary.top_courses) == {"函数与导数": 2, "高等数学": 1}


def test_empty_dashboard_is_zeroed():
    summary = build_dashboard(InMemoryRepository(), NOW)
    assert summary.receipts == 0
    assert summary.mistakes == 0
    assert summary.due_today == 0
    assert summary.average_hint_level == 0.0
    assert summary.top_errors == ()
    assert summary.top_courses == ()
