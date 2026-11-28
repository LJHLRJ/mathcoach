"""只读统计快照的指标口径与空数据行为。"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from mathcoach.analytics import (
    ANALYSIS_SCHEMA_VERSION,
    AnalysisRepository,
    build_snapshot,
)
from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    Stage,
)
from mathcoach.memory.repository import InMemoryRepository

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _receipt(
    identifier: str,
    card_id: str,
    independence: Independence,
    max_hint_level: int,
    days_ago: int,
) -> Receipt:
    """构造收据样例。"""
    return Receipt(
        id=identifier,
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=20,
        max_hint_level=max_hint_level,
        goal="练函数",
        independence=independence,
        created_at=NOW - timedelta(days=days_ago),
    )


def _mistake(
    identifier: str,
    card_id: str,
    error_type: ErrorType,
    days_ago: int,
) -> MistakeEntry:
    """构造错题样例。"""
    return MistakeEntry(
        id=identifier,
        exercise_id=f"{card_id}-{identifier}",
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错答",
        correct_answer="正确",
        error_type=error_type,
        max_hint_level=1,
        created_at=NOW - timedelta(days=days_ago),
    )


def _repository() -> InMemoryRepository:
    """构造跨两周、覆盖两张卡片的仓储。"""
    repository = InMemoryRepository()
    repository.set_mastery("card-1", 0.40, NOW - timedelta(days=8))
    repository.set_mastery("card-2", 0.50, NOW - timedelta(days=8))
    repository.save_receipt(
        _receipt(
            "r1", "card-1", Independence.INDEPENDENT, 1, 1
        ),
        "card-1-e1",
    )
    repository.save_receipt(
        _receipt(
            "r2", "card-2", Independence.SEMI_INDEPENDENT, 4, 2
        ),
        "card-2-e1",
    )
    repository.save_mistake(
        _mistake("m1", "card-1", ErrorType.CONCEPT, 1)
    )
    repository.save_mistake(
        _mistake("m2", "card-2", ErrorType.CALCULATION, 3)
    )
    repository.save_mistake(
        _mistake("m3", "card-1", ErrorType.CONCEPT, 9)
    )
    repository.save_mistake(
        _mistake("m4", "card-2", ErrorType.CALCULATION, 8)
    )
    repository.set_mastery("card-1", 0.60, NOW - timedelta(days=1))
    return repository


class _ReadOnlyRepository:
    """只暴露读接口，验证统计层不会调用写入方法。"""

    def __init__(self, inner: AnalysisRepository) -> None:
        """保存内部仓储。"""
        self._inner = inner

    def list_receipts(self, limit: int | None = 50):
        return self._inner.list_receipts(limit)

    def list_mistakes(self, limit: int | None = 50, include_mastered: bool = True):
        return self._inner.list_mistakes(limit, include_mastered)

    def list_review_items(self):
        return self._inner.list_review_items()

    def list_mastery_history(self, card_id: str | None = None):
        return self._inner.list_mastery_history(card_id)

    def get_mastery(self, card_id: str):
        return self._inner.get_mastery(card_id)


def test_snapshot_metrics_from_existing_tables():
    """收据、错题、复习与掌握度按既定口径聚合。"""
    snapshot = build_snapshot(_repository(), NOW)

    assert snapshot.schema_version == ANALYSIS_SCHEMA_VERSION
    assert snapshot.metrics["receipts.count"].value == 2
    assert snapshot.metrics["receipts.independent_rate"].value == 0.5
    assert (
        snapshot.metrics["receipts.semi_independent_rate"].value == 0.5
    )
    assert snapshot.metrics["hints.average_max_level"].value == 2.5
    assert snapshot.metrics["hints.dependency_rate"].value == 0.5
    assert snapshot.metrics["mistakes.count"].value == 2
    assert snapshot.metrics["mistakes.concept_share"].value == 0.5
    assert snapshot.metrics["review.due_today"].value == 4
    assert snapshot.metrics["activity.active_days"].value == 3
    assert snapshot.metrics["mastery.changed_cards"].value >= 1

    assert snapshot.errors
    assert snapshot.errors[0].error_type is ErrorType.CONCEPT
    assert snapshot.errors[0].count == 1
    assert snapshot.errors[0].share == 0.5


def test_snapshot_trend_and_mastery_delta():
    """周环比与掌握度变化复用现有口径。"""
    snapshot = build_snapshot(_repository(), NOW)

    this_week = dict(snapshot.error_trend.this_week)
    last_week = dict(snapshot.error_trend.last_week)
    assert this_week == {
        ErrorType.CONCEPT.value: 1,
        ErrorType.CALCULATION.value: 1,
    }
    assert last_week == {
        ErrorType.CONCEPT.value: 1,
        ErrorType.CALCULATION.value: 1,
    }

    changes = {item.card_id: item for item in snapshot.mastery_changes}
    assert changes["card-1"].before == 0.40
    assert changes["card-1"].after == 0.60
    assert changes["card-1"].delta == 0.20


def test_snapshot_by_card_scope():
    """单卡汇总与课程信息来自窗口内数据。"""
    snapshot = build_snapshot(_repository(), NOW)
    cards = {item.card_id: item for item in snapshot.by_card}

    assert cards["card-1"].receipts == 1
    assert cards["card-1"].mistakes == 1
    assert cards["card-1"].independent == 1
    assert cards["card-1"].top_error is ErrorType.CONCEPT
    assert cards["card-2"].receipts == 1
    assert cards["card-2"].mistakes == 1
    assert cards["card-2"].top_error is ErrorType.CALCULATION


def test_snapshot_card_filter_limits_all_metrics():
    """限定卡片后只统计该卡。"""
    snapshot = build_snapshot(_repository(), NOW, card_id="card-1")

    assert snapshot.scope.card_id == "card-1"
    assert snapshot.metrics["receipts.count"].value == 1
    assert snapshot.metrics["mistakes.count"].value == 1
    assert [item.card_id for item in snapshot.by_card] == ["card-1"]
    assert snapshot.metrics["review.due_today"].value == 2

def test_snapshot_empty_repository_is_stable():
    """空仓储不抛异常，比例指标为 None。"""
    snapshot = build_snapshot(InMemoryRepository(), NOW)

    assert snapshot.metrics["receipts.count"].value == 0
    assert snapshot.metrics["receipts.independent_rate"].value is None
    assert snapshot.metrics["hints.average_max_level"].value is None
    assert snapshot.metrics["review.due_today"].value == 0
    assert snapshot.errors == ()
    assert snapshot.error_trend.this_week == ()
    assert snapshot.by_card == ()
    assert snapshot.data_quality.sample_size == 0
    assert snapshot.data_quality.minimum_sample_met is False


def test_snapshot_serializes_to_json():
    """快照映射可直接 JSON 序列化。"""
    payload = build_snapshot(_repository(), NOW).to_dict()

    text = json.dumps(payload, ensure_ascii=False)
    assert "analysis-snapshot/1" in text
    assert payload["errors"][0]["code"] is None
    assert payload["data_quality"]["attempt_events_available"] is False


def test_snapshot_only_requires_read_methods():
    """只读仓储即可完成统计。"""
    snapshot = build_snapshot(
        _ReadOnlyRepository(_repository()), NOW
    )

    assert snapshot.metrics["receipts.count"].value == 2
    assert snapshot.metrics["mistakes.count"].value == 2


def test_snapshot_rejects_invalid_window():
    """窗口天数必须为正。"""
    with pytest.raises(ValueError):
        build_snapshot(InMemoryRepository(), NOW, days=0)
