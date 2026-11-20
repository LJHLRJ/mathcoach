"""AppTest 冒烟：首屏可渲染，并能完成一次闭环。"""
from streamlit.testing.v1 import AppTest


def test_app_renders_and_completes_one_loop():
    at = AppTest.from_file("app.py", default_timeout=15)
    at.run()
    assert not at.exception
    assert at.title[0].value == "数学陪练"

    at.text_input[0].set_value("搞懂函数的概念")
    at.button[0].click().run()
    assert not at.exception

    assert at.button[0].label == "开始小测"
    at.button[0].click().run()
    assert not at.exception

    at.radio[0].set_value("y = x²")
    at.button[0].click().run()
    assert not at.exception
    assert "收据已生成" in at.subheader[0].value
