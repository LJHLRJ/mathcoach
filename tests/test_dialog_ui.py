"""追问 UI：L4 追问渲染、回答提交与事件落库。"""
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.tutor.dialog import DialogStore

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class _TemplateClient:
    """返回追问模板的确定性假客户端。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """把 template_prompt 原样作为问法返回。"""
        payload = json.loads(user_prompt)
        return json.dumps(
            {"prompt": payload["template_prompt"]}, ensure_ascii=False
        )


def test_follow_up_renders_and_returns_to_quiz(tmp_path, monkeypatch) -> None:
    """L4 追问可渲染、提交命中后回到原题，并写入信号库。"""
    db = tmp_path / "mathcoach.sqlite3"
    signals = tmp_path / "dialog.sqlite3"
    monkeypatch.setenv("MATHCOACH_DB", str(db))
    monkeypatch.setenv("MATHCOACH_DIALOG_DB", str(signals))

    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.selectbox[0].select("hs-trig-002").run()
    at.text_input[0].set_value("搞懂同角关系")
    next(
        button for button in at.button if button.label == "确认目标"
    ).click().run()
    next(
        button for button in at.button if button.label == "开始小测"
    ).click().run()

    assert not at.exception
    engine = at.session_state["engine"]
    engine.dialog_client = _TemplateClient()
    next(
        button
        for button in at.button
        if button.label == "给步骤（最高 L4）"
    ).click().run()

    assert not at.exception
    assert any(box.label == "你的回答" for box in at.text_input)
    assert any(
        "sin²x + cos²x" in info.value for info in at.info
    )

    next(
        box for box in at.text_input if box.label == "你的回答"
    ).set_value("1")
    at.run()
    next(
        button
        for button in at.button
        if button.label == "提交追问回答"
    ).click().run()

    assert not at.exception
    assert any(radio.label == "选择答案" for radio in at.radio)

    store = DialogStore(signals)
    try:
        events = store.list_events()
    finally:
        store.close()
    assert events
    assert events[0].kind.value == "hit"
    assert events[0].answer == "1"
