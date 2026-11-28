"""场景 A：作答反馈页接入只读错因归因。"""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mathcoach.analytics import TemplateNarrator
from mathcoach.config import resolve_content_root
from mathcoach.content.loader import load_content
from mathcoach.session.daily import DailyQuestion, DailyState
from mathcoach.timeutil import local_day_key

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
CONTENT_ROOT = resolve_content_root(APP_PATH)


def _click(at: AppTest, label: str) -> None:
    """点击唯一匹配的按钮并运行。"""
    next(button for button in at.button if button.label == label).click().run()


def _single_question_state(date_key: str) -> DailyState:
    """用第一张卡的第一道选择题构造单题小测状态。"""
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card = next(item for item in cards if item.id == "hs-function-intro-001")
    return DailyState(
        date_key=date_key,
        questions=(DailyQuestion(card, card.exercises[0]),),
        started_at=datetime.now(timezone.utc),
    )


def _submit_wrong_answer(at: AppTest) -> None:
    """选卡、确认目标、开始小测并提交一个错误答案。"""
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数")
    _click(at, "确认目标")
    _click(at, "开始小测")
    at.radio[0].set_value("y² = x")
    _click(at, "提交答案")


def test_feedback_renders_template_attribution_when_switch_off(
    tmp_path, monkeypatch
):
    """开关关闭时展示模板归因，且不读取分析凭据。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "feedback.sqlite3"))

    def _unexpected() -> tuple[str, str, str]:
        raise AssertionError("开关关闭时不应读取分析凭据")

    monkeypatch.setattr(
        "mathcoach.analytics.narrative.load_analysis_credentials",
        _unexpected,
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    _submit_wrong_answer(at)

    assert not at.exception
    assert any(
        "错因归因（只读）" in markdown.value for markdown in at.markdown
    )
    assert any(
        "来源：本地规则模板" in caption.value for caption in at.caption
    )


def test_feedback_passes_analysis_switch_to_narrator(tmp_path, monkeypatch):
    """设置页开关打开后，归因按 analysis_online_enabled 装配叙事层。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "feedback-on.sqlite3"))
    calls: list[bool] = []

    def _record(**kwargs: object) -> TemplateNarrator:
        calls.append(bool(kwargs.get("enabled")))
        return TemplateNarrator()

    monkeypatch.setattr("mathcoach.analytics.build_narrator", _record)
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()
    toggle = next(
        item for item in at.toggle if item.label == "启用在线学情分析"
    )
    toggle.set_value(True)
    _click(at, "保存设置")
    at.session_state["main_tabs"] = "当前任务"
    at.run()
    _submit_wrong_answer(at)

    assert not at.exception
    assert calls and calls[-1] is True
    assert any(
        "错因归因（只读）" in markdown.value for markdown in at.markdown
    )


@pytest.mark.parametrize(
    ("mode", "state_key", "date_key"),
    [
        ("每日挑战", "daily_state", None),
        ("挑战赛", "challenge_state", "challenge-test"),
        ("智能复习包", "review_state", "review-test"),
    ],
)
def test_quiz_settlement_shows_attribution(
    tmp_path,
    monkeypatch,
    mode: str,
    state_key: str,
    date_key: str | None,
) -> None:
    """每日挑战、挑战赛与复习包结算后展示错题归因。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / f"{state_key}.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    key = local_day_key() if date_key is None else date_key
    at.session_state[state_key] = _single_question_state(key)
    at.session_state["app_mode"] = mode
    at.run()

    at.radio[0].set_value("y² = x")
    _click(at, "提交答案")

    assert not at.exception
    assert any(
        "错因归因（只读）" in markdown.value for markdown in at.markdown
    )
    assert any(
        "来源：本地规则模板" in caption.value for caption in at.caption
    )
