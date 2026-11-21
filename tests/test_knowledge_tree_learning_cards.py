"""学习卡片：文件覆盖、填充状态、非法 ID、开关与答题入口。"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.content.loader import load_content
from mathcoach.domain.knowledge_tree import (
    LEARNING_CARDS_DIR,
    learning_card_is_filled,
    learning_card_path,
    load_learning_card,
)
from mathcoach.domain.models import Consent
from mathcoach.ui.knowledge_browser import (
    load_learning_cards_enabled,
    save_learning_cards_enabled,
)

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
PERSISTENT = Consent(memory=True, mistake_book=True)
FILLED_SECTIONS = ("## 概念", "## 直觉", "## 常见误区", "## 诊断例题")


def _card_ids() -> list[str]:
    cards, result = load_content(ROOT / "content", strict=False)
    assert result.ok
    return [card.id for card in cards]


def _click(at, label: str) -> None:
    next(button for button in at.button if button.label == label).click().run()


def test_every_card_has_a_learning_card_file():
    card_ids = _card_ids()
    files = {path.stem for path in LEARNING_CARDS_DIR.glob("*.md")}

    assert len(card_ids) == 122
    assert set(card_ids) == files


def test_card_files_are_filled_or_marked_as_template():
    filled: list[str] = []
    for card_id in _card_ids():
        text = load_learning_card(card_id)
        assert text is not None
        if learning_card_is_filled(text):
            filled.append(card_id)
            assert "状态：已填充" in text
            for section in FILLED_SECTIONS:
                assert section in text, f"{card_id} 缺少 {section}"
        else:
            assert "状态：待填充" in text
            assert "待填充" in text

    assert len(filled) >= 5
    assert "hs-function-intro-001" in filled


def test_learning_card_path_rejects_missing_or_unsafe_ids():
    assert learning_card_path("") is None
    assert learning_card_path("..") is None
    assert learning_card_path("../app") is None
    assert learning_card_path("sub/card") is None

    assert load_learning_card("") is None
    assert load_learning_card("not-a-card") is None
    assert load_learning_card("../app") is None


def test_learning_cards_toggle_persists_in_settings_store(tmp_path):
    path = tmp_path / "learning-cards.sqlite3"

    assert load_learning_cards_enabled(PERSISTENT, path) is True
    assert save_learning_cards_enabled(PERSISTENT, False, path) is True
    assert load_learning_cards_enabled(PERSISTENT, path) is False
    assert save_learning_cards_enabled(PERSISTENT, True, path) is True
    assert load_learning_cards_enabled(PERSISTENT, path) is True


def test_answer_page_entry_opens_learning_card(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "learning-cards-ui.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()

    assert not at.exception
    _click(at, "先学习此知识点")

    assert not at.exception
    assert at.subheader[0].value == "知识点浏览"
    assert any(
        "函数的概念" in markdown.value for markdown in at.markdown
    )
    assert any("常见误区" in markdown.value for markdown in at.markdown)

    _click(at, "返回当前任务")
    assert not at.exception
    assert any(button.label == "开始小测" for button in at.button)


def test_knowledge_browser_can_start_practice_for_focused_card(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "learning-cards-practice.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()

    _click(at, "先学习此知识点")
    _click(at, "开始练习此知识点")

    assert not at.exception
    assert any(button.label == "确认目标" for button in at.button)


def test_settings_page_shows_learning_cards_toggle(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "learning-cards-settings.sqlite3")
    )
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    toggle = next(
        box for box in at.toggle if box.label == "显示学习卡片"
    )
    assert toggle.value is True


def test_disabled_learning_cards_hide_entry(tmp_path, monkeypatch):
    path = tmp_path / "learning-cards-hidden.sqlite3"
    assert save_learning_cards_enabled(PERSISTENT, False, path) is True
    monkeypatch.setenv("MATHCOACH_DB", str(path))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()

    assert not at.exception
    assert not any(
        button.label == "先学习此知识点" for button in at.button
    )
