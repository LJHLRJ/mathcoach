"""用假客户端测试，绝不联网。"""
from typing import NoReturn

from mathcoach.domain.models import Exercise, ExerciseKind
from mathcoach.llm import FallbackProvider, build_provider
from mathcoach.llm.base import ParsedAnswer, RenderTask, UNPARSED
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.llm.openai_provider import OpenAICompatibleProvider


class _Message:
    """模拟 SDK 消息对象。"""
    def __init__(self, content: str) -> None:
        """保存消息文本。"""
        self.content = content


class _Choice:
    """模拟 SDK 选择项。"""
    def __init__(self, content: str) -> None:
        """包装消息对象。"""
        self.message = _Message(content)


class _Response:
    """模拟 SDK 响应。"""
    def __init__(self, content: str) -> None:
        """保存单个选择项。"""
        self.choices = [_Choice(content)]


class _Completions:
    """模拟 completions 接口并记录调用参数。"""
    def __init__(self, content: str) -> None:
        """初始化内容与调用记录。"""
        self.content = content
        self.calls: list[dict] = []

    def create(self, **kwargs: object) -> _Response:
        """记录参数并返回固定响应。"""
        self.calls.append(kwargs)
        return _Response(self.content)


class _Chat:
    """模拟 chat 命名空间。"""
    def __init__(self, content: str) -> None:
        """挂载 completions 接口。"""
        self.completions = _Completions(content)


class _Client:
    """模拟 OpenAI 客户端。"""
    def __init__(self, content: str) -> None:
        """挂载 chat 命名空间。"""
        self.chat = _Chat(content)


def _exercise() -> Exercise:
    """构造解析测试用练习。"""
    return Exercise(
        id="hs-001-e1",
        card_id="hs-001",
        kind=ExerciseKind.CHOICE,
        stem="2 + 2 = ?",
        answer="4",
        solution_outline="相加",
        options=("3", "4"),
    )


def test_render_returns_model_text():
    """渲染返回模型文本且默认不流式。"""
    client = _Client("讲解内容")
    provider = OpenAICompatibleProvider(api_key="test", client=client)
    task = RenderTask(kind="explain", card_name="函数", content="素材")

    assert provider.render(task) == "讲解内容"
    assert client.chat.completions.calls[0]["model"] == "gpt-4o-mini"
    assert "stream" not in client.chat.completions.calls[0]


def test_parse_freeform_validates_json():
    """合法 JSON 解析为 ParsedAnswer。"""
    payload = '{"normalized_value": "4", "confidence": 0.9, "reason": "代入"}'
    provider = OpenAICompatibleProvider(api_key="test", client=_Client(payload))
    parsed = provider.parse_freeform("四", _exercise())
    assert isinstance(parsed, ParsedAnswer)
    assert parsed.normalized_value == "4"


def test_parse_freeform_bad_json_falls_back_to_unparsed():
    """非法 JSON 回退为未解析。"""
    provider = OpenAICompatibleProvider(api_key="test", client=_Client("不是 JSON"))
    assert provider.parse_freeform("四", _exercise()) == UNPARSED


class _BrokenProvider:
    """始终超时的假 Provider。"""
    def render(self, task: RenderTask) -> NoReturn:
        """抛出超时异常。"""
        raise TimeoutError("超时")

    def parse_freeform(self, text: str, exercise: Exercise) -> NoReturn:
        """抛出超时异常。"""
        raise TimeoutError("超时")


def test_fallback_provider_degrades_to_offline():
    """主 Provider 失败时降级到离线实现。"""
    provider = FallbackProvider(primary=_BrokenProvider(), fallback=OfflineProvider())
    task = RenderTask(kind="explain", card_name="函数", content="素材")
    assert provider.render(task) == "素材"
    assert provider.degraded is True


def test_build_provider_uses_offline_without_key(monkeypatch):
    """无 API key 时构建离线 Provider。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(build_provider(), OfflineProvider)
