"""加载占位与片段 rerun 兼容层。"""
import pytest
from streamlit.errors import StreamlitAPIException

from mathcoach.ui import components


def test_fragment_scope_api_error_is_recognized() -> None:
    """旧版 Streamlit 的片段 scope 错误被识别。"""
    exc = StreamlitAPIException(
        'scope="fragment" can only be specified from @st.fragment functions'
    )

    assert components.is_fragment_rerun_error(exc)


def test_unrelated_api_error_is_not_recognized() -> None:
    """其他 API 错误不应触发全局 rerun 回退。"""
    assert not components.is_fragment_rerun_error(
        StreamlitAPIException("other api error")
    )


def test_rerun_fragment_falls_back_to_global_rerun(monkeypatch) -> None:
    """旧版抛 API 错误时，兼容层改为全局 rerun。"""
    calls: list[str] = []

    def fake_rerun(*, scope: str = "app") -> None:
        """记录 scope；全局 rerun 用异常模拟控制流。"""
        calls.append(scope)
        if scope == "fragment":
            raise StreamlitAPIException(
                'scope="fragment" can only be specified from @st.fragment functions'
            )
        raise RuntimeError("full rerun")

    monkeypatch.setattr(components.st, "rerun", fake_rerun)

    with pytest.raises(RuntimeError, match="full rerun"):
        components.rerun_fragment()

    assert calls == ["fragment", "app"]
