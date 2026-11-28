"""追问事件信号库：写入、读取、脱敏与路径覆盖。"""
from datetime import datetime, timezone

from mathcoach.tutor.dialog import (
    DialogEvent,
    DialogEventKind,
    DialogStore,
    dialog_db_path,
)

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def _event(answer: str = "1") -> DialogEvent:
    """构造一条最小追问事件。"""
    return DialogEvent(
        exercise_id="hs-trig-002-e1",
        card_id="hs-trig-002",
        kc_ids=("kc-hs-trig-002-f1",),
        level=4,
        supplement=False,
        kind=DialogEventKind.HIT,
        downgraded=False,
        shown_at=NOW,
        resolved_at=NOW,
        answer=answer,
        reason="",
    )


def test_store_records_and_lists_event(tmp_path) -> None:
    """事件可写入并按时间倒序读取。"""
    store = DialogStore(tmp_path / "dialog.sqlite3")
    try:
        identifier = store.record(_event())
        events = store.list_events()

        assert len(events) == 1
        assert events[0].id == identifier
        assert events[0].exercise_id == "hs-trig-002-e1"
        assert events[0].kc_ids == ("kc-hs-trig-002-f1",)
        assert events[0].kind is DialogEventKind.HIT
        assert events[0].downgraded is False
    finally:
        store.close()


def test_store_sanitizes_answer(tmp_path) -> None:
    """学生回答中的手机号会脱敏后再落库。"""
    store = DialogStore(tmp_path / "dialog.sqlite3")
    try:
        store.record(_event("我的电话 13800138000"))
        events = store.list_events()

        assert "13800138000" not in events[0].answer
        assert "[已脱敏]" in events[0].answer
    finally:
        store.close()


def test_dialog_db_path_can_be_overridden(tmp_path, monkeypatch) -> None:
    """追问信号库路径可用环境变量覆盖。"""
    target = tmp_path / "signals.sqlite3"
    monkeypatch.setenv("MATHCOACH_DIALOG_DB", str(target))

    assert dialog_db_path() == target
