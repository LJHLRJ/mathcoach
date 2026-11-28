"""召回效果信号：展示记录、结果回写与路径覆盖。"""
from datetime import datetime, timezone

from mathcoach.domain.models import (
    Difficulty,
    Exercise,
    ExerciseKind,
    KnowledgeCard,
    Stage,
)
from mathcoach.recall import (
    RecallStore,
    SimilarCandidate,
    recall_db_path,
)

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def _candidate(
    exercise_id: str, *, transfer: bool, score: float
) -> SimilarCandidate:
    """构造一条最小召回候选。"""
    card = KnowledgeCard(
        id="card-1",
        name="测试卡",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        chapter="函数概念",
        difficulty=Difficulty.BASIC,
        intuition="直觉",
        definition="定义",
        mistakes=(),
        example="例子",
        exercises=(),
        source="测试",
    )
    exercise = Exercise(
        id=exercise_id,
        card_id=card.id,
        kind=ExerciseKind.CHOICE,
        stem=f"题干 {exercise_id}",
        answer="答案",
        solution_outline="思路",
    )
    return SimilarCandidate(
        exercise=exercise,
        card=card,
        score=score,
        reasons=("同知识点",),
        is_transfer=transfer,
    )


def test_store_records_impression_and_outcome(tmp_path) -> None:
    """展示与作答结果都能落库。"""
    store = RecallStore(tmp_path / "recall.sqlite3")
    try:
        mapping = store.record_impression(
            "source-e1",
            [
                _candidate("c-e1", transfer=False, score=9.0),
                _candidate("c-e2", transfer=True, score=4.0),
            ],
            now=NOW,
        )
        assert set(mapping) == {"c-e1", "c-e2"}
        events = store.list_events()
        assert len(events) == 2
        assert all(event.attempted is False for event in events)
        assert {event.rank for event in events} == {1, 2}
        assert {event.is_transfer for event in events} == {False, True}

        assert store.record_outcome(mapping["c-e1"], True, now=NOW)
        assert store.record_outcome(mapping["c-e2"], None, now=NOW)

        events_by_id = {
            event.candidate_exercise_id: event
            for event in store.list_events()
        }
        assert events_by_id["c-e1"].attempted is True
        assert events_by_id["c-e1"].correct is True
        assert events_by_id["c-e2"].attempted is True
        assert events_by_id["c-e2"].correct is None
    finally:
        store.close()


def test_store_unknown_impression_returns_false(tmp_path) -> None:
    """未知展示 ID 不产生更新。"""
    store = RecallStore(tmp_path / "recall.sqlite3")
    try:
        assert store.record_outcome("missing", False, now=NOW) is False
    finally:
        store.close()


def test_recall_db_path_can_be_overridden(tmp_path, monkeypatch) -> None:
    """召回信号库路径可用环境变量覆盖。"""
    target = tmp_path / "signals.sqlite3"
    monkeypatch.setenv("MATHCOACH_RECALL_DB", str(target))

    assert recall_db_path() == target
