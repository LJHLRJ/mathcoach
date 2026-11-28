"""KC 影子掌握度接入仪表盘：展示与下一步推荐。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.tutor.mastery_store import KCMasteryStore

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_shows_kc_progress_and_recommends(tmp_path, monkeypatch):
    """KC 影子掌握度在仪表盘展示，并进入下一步推荐。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3")
    )
    store = KCMasteryStore(tmp_path / "kc.sqlite3")
    try:
        store.set("kc-hs-trig-002-f1", 0.2, 3)
    finally:
        store.close()

    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    at.selectbox[1].select("仪表盘").run()

    assert not at.exception
    values = [markdown.value for markdown in at.markdown]
    assert "**KC 掌握度（步骤级影子）**" in values
    assert any("同角平方关系" in value for value in values)
    start = values.index("**下一步推荐**")
    assert values[start + 1].startswith("- hs-trig-002")
    assert any(
        "KC 影子掌握度 20%" in caption.value
        for caption in at.caption
        if "依据：" in caption.value
    )


def test_dashboard_shows_repair_plan(tmp_path, monkeypatch):
    """前置缺口在仪表盘给出修复建议，并排到下一步推荐首位。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3")
    )
    store = KCMasteryStore(tmp_path / "kc.sqlite3")
    try:
        store.set("kc-hs-trig-002-f1", 0.45, 3)
        store.set("kc-hs-trig-003-f1", 0.2, 3)
    finally:
        store.close()

    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    at.selectbox[1].select("仪表盘").run()

    assert not at.exception
    values = [markdown.value for markdown in at.markdown]
    assert "**前置修复建议**" in values
    assert any("先修「同角平方关系」" in value for value in values)
    assert any(
        button.label == "先修补先修：同角三角函数关系"
        for button in at.button
    )
    start = values.index("**下一步推荐**")
    assert values[start + 1].startswith("- hs-trig-002：先修补齐")


def test_learning_path_shows_weak_kc(tmp_path, monkeypatch):
    """学习路径页展示薄弱 KC 的掌握度与待补强标记。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    monkeypatch.setenv(
        "MATHCOACH_KC_DB", str(tmp_path / "kc.sqlite3")
    )
    store = KCMasteryStore(tmp_path / "kc.sqlite3")
    try:
        store.set("kc-hs-trig-002-f1", 0.2, 3)
    finally:
        store.close()

    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    at.selectbox[1].select("学习路径").run()

    assert not at.exception
    values = [markdown.value for markdown in at.markdown]
    assert "**KC 掌握度（步骤级影子）**" in values
    assert any(
        "同角平方关系" in value and "待补强" in value
        for value in values
    )
    assert any(
        "对应卡片" in caption.value for caption in at.caption
    )
