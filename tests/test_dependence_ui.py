"""依赖度防护 UI：提示上限横幅、恢复与独立验证入口。"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import (
    Consent,
    ExerciseKind,
    Independence,
    Receipt,
    Stage,
)
from mathcoach.memory.repository import build_repository

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
NOW = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)


def _seed_history(path: Path) -> None:
    """写入三张半独立收据，并把掌握度抬到收紧阈值以上。"""
    repository = build_repository(Consent(), path)
    try:
        for index, level in enumerate((4, 5, 4)):
            repository.save_receipt(
                Receipt(
                    card_id="hs-trig-002",
                    stage=Stage.HIGH_SCHOOL,
                    course="三角函数",
                    exercise_type=ExerciseKind.FILL,
                    duration_s=60,
                    max_hint_level=level,
                    goal="测试",
                    independence=Independence.SEMI_INDEPENDENT,
                    created_at=NOW + timedelta(minutes=index),
                ),
                f"hs-trig-002-e{index + 1}",
            )
        repository.set_mastery("hs-trig-002", 0.8, NOW)
    finally:
        repository.close()


def _prepare(tmp_path, monkeypatch) -> None:
    """统一设置独立数据库路径并写入历史。"""
    db_path = tmp_path / "mathcoach.sqlite3"
    _seed_history(db_path)
    monkeypatch.setenv("MATHCOACH_DB", str(db_path))
    monkeypatch.setenv(
        "MATHCOACH_STEP_DB", str(tmp_path / "steps.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_DIALOG_DB", str(tmp_path / "dialog.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3")
    )


def _start(at: AppTest) -> None:
    """选择同角关系卡并进入小测。"""
    at.selectbox[0].select("hs-trig-002").run()
    at.text_input[0].set_value("搞懂同角关系")
    next(
        button for button in at.button if button.label == "确认目标"
    ).click().run()
    next(
        button for button in at.button if button.label == "开始小测"
    ).click().run()


def _click(at: AppTest, label: str) -> None:
    """按按钮文本点击并重跑。"""
    next(button for button in at.button if button.label == label).click().run()
    assert not at.exception


def test_tighten_signal_shows_banner_and_caps_hint(
    tmp_path, monkeypatch
) -> None:
    """依赖度达标时展示横幅，主动请求只到 L2。"""
    _prepare(tmp_path, monkeypatch)
    at = AppTest.from_file(APP_PATH, default_timeout=20).run()
    _start(at)

    infos = " ".join(item.value for item in at.info)
    assert "先自己试一步" in infos
    assert any(
        button.label == "恢复完整提示" for button in at.button
    )

    _click(at, "给步骤（最高 L4）")

    engine = at.session_state["engine"]
    assert engine.state.hint_level == 2
    assert engine.hint_ceiling_active is True


def test_manual_release_restores_full_hint_ladder(
    tmp_path, monkeypatch
) -> None:
    """点击恢复后主动请求回到 L4。"""
    _prepare(tmp_path, monkeypatch)
    at = AppTest.from_file(APP_PATH, default_timeout=20).run()
    _start(at)

    _click(at, "恢复完整提示")
    engine = at.session_state["engine"]
    assert engine.hint_ceiling_active is False

    _click(at, "给步骤（最高 L4）")

    assert engine.state.hint_level == 4


def test_receipt_shows_independent_verification_invitation(
    tmp_path, monkeypatch
) -> None:
    """收据页提供无提示独立验证邀请。"""
    _prepare(tmp_path, monkeypatch)
    at = AppTest.from_file(APP_PATH, default_timeout=20).run()
    _start(at)

    next(
        radio for radio in at.radio if radio.label == "选择答案"
    ).set_value("sin²x+cos²x=1")
    _click(at, "提交答案")

    markdown = " ".join(item.value for item in at.markdown)
    captions = " ".join(item.value for item in at.caption)
    assert "独立验证（可选）" in markdown
    assert "学习自主度观察" in captions
