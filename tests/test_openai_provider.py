"""用假客户端测试，绝不联网。"""
from mathcoach.domain.models import Exercise, ExerciseKind
from mathcoach.llm import FallbackProvider, build_provider
from mathcoach.llm.base import ParsedAnswer, RenderTask, UNPARSED
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.llm.openai_provider import OpenAICompatibleProvider


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.content)


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class _Client:
    def __init__(self, content: str) -> None:
        self.chat = _Chat(content)


def _exercise() -> Exercise:
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
    client = _Client("讲解内容")
    provider = OpenAICompatibleProvider(api_key="test", client=client)
    task = RenderTask(kind="explain", card_name="函数", content="素材")

    assert provider.render(task) == "讲解内容"
    assert client.chat.completions.calls[0]["model"] == "gpt-4o-mini"
    assert "stream" not in client.chat.completions.calls[0]


def test_parse_freeform_validates_json():
    payload = '{"normalized_value": "4", "confidence": 0.9, "reason": "代入"}'
    provider = OpenAICompatibleProvider(api_key="test", client=_Client(payload))
    parsed = provider.parse_freeform("四", _exercise())
    assert isinstance(parsed, ParsedAnswer)
    assert parsed.normalized_value == "4"


def test_parse_freeform_bad_json_falls_back_to_unparsed():
    provider = OpenAICompatibleProvider(api_key="test", client=_Client("不是 JSON"))
    assert provider.parse_freeform("四", _exercise()) == UNPARSED


class _BrokenProvider:
    def render(self, task):
        raise TimeoutError("超时")

    def parse_freeform(self, text, exercise):
        raise TimeoutError("超时")


def test_fallback_provider_degrades_to_offline():
    provider = FallbackProvider(primary=_BrokenProvider(), fallback=OfflineProvider())
    task = RenderTask(kind="explain", card_name="函数", content="素材")
    assert provider.render(task) == "素材"
    assert provider.degraded is True


def test_build_provider_uses_offline_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(build_provider(), OfflineProvider)
