"""表示降级信号库：决策与下一次作答结果可回填。"""
from datetime import datetime, timezone

from mathcoach.domain.representation import Representation
from mathcoach.representation import (
    REPRESENTATION_DB_ENV,
    RepresentationEvent,
    RepresentationStore,
    RepresentationStoreRecorder,
    as_recorder,
)


def _event() -> RepresentationEvent:
    return RepresentationEvent(
        exercise_id="hs-function-intro-001-e1",
        card_id="hs-function-intro-001",
        from_repr=Representation.FORMULA,
        to_repr=Representation.WORKED_EXAMPLE,
        triggers=("连续错误=2", "提示请求=1"),
        shown_at=datetime(2026, 11, 28, tzinfo=timezone.utc),
    )


def test_record_and_list_event(tmp_path):
    """降级事件写入后可读回，触发原因保持顺序。"""
    with RepresentationStore(tmp_path / "signals.sqlite3") as store:
        event = _event()
        assert store.record(event) == event.id
        events = store.list_events()
    assert len(events) == 1
    assert events[0].to_repr is Representation.WORKED_EXAMPLE
    assert events[0].triggers == ("连续错误=2", "提示请求=1")
    assert events[0].next_correct is None
    assert events[0].resolved_at is None


def test_record_outcome_backfills_three_state(tmp_path):
    """回填结果支持正确/无法判定/错误三种状态。"""
    with RepresentationStore(tmp_path / "signals.sqlite3") as store:
        event = _event()
        store.record(event)
        assert store.record_outcome(
            event.id, correct=True, hint_level=3
        )
        stored = store.list_events()[0]
        assert stored.next_correct is True
        assert stored.next_hint_level == 3
        assert stored.resolved_at is not None

        assert store.record_outcome(
            event.id, correct=None, hint_level=4
        )
        assert store.list_events()[0].next_correct is None


def test_record_outcome_unknown_id_returns_false(tmp_path):
    """未知事件不写入，返回 False。"""
    with RepresentationStore(tmp_path / "signals.sqlite3") as store:
        assert not store.record_outcome(
            "missing", correct=False, hint_level=2
        )


def test_store_recorder_uses_env_path(tmp_path, monkeypatch):
    """短连接记录器按环境变量定位独立信号库。"""
    path = tmp_path / "recorder.sqlite3"
    monkeypatch.setenv(REPRESENTATION_DB_ENV, str(path))
    recorder = RepresentationStoreRecorder()
    event = _event()
    recorder.record(event)
    recorder.record_outcome(event.id, correct=False, hint_level=2)

    with RepresentationStore(path) as store:
        events = store.list_events()
    assert len(events) == 1
    assert events[0].next_correct is False


def test_as_recorder_adapter(tmp_path):
    """适配器复用已有连接，便于测试与上层注入。"""
    with RepresentationStore(tmp_path / "signals.sqlite3") as store:
        recorder = as_recorder(store)
        event = _event()
        recorder.record(event)
        recorder.record_outcome(event.id, correct=True, hint_level=1)
        assert store.list_events()[0].next_correct is True
