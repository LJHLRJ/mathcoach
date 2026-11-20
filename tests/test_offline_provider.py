"""离线 Provider 必须确定、不联网、且严格拒绝多余字段。"""
import pytest
from pydantic import ValidationError

from mathcoach.domain.models import Exercise, ExerciseKind
from mathcoach.llm.base import ParsedAnswer, RenderTask, UNPARSED
from mathcoach.llm.offline_provider import OfflineProvider


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


def test_render_returns_content_verbatim():
    provider = OfflineProvider()
    task = RenderTask(kind="explain", card_name="函数", content="直觉：输入唯一输出")
    assert provider.render(task) == "直觉：输入唯一输出"


def test_parse_freeform_is_unparsed():
    provider = OfflineProvider()
    assert provider.parse_freeform("等于四", _exercise()) == UNPARSED


def test_parsed_answer_forbids_extra_fields():
    with pytest.raises(ValidationError):
        ParsedAnswer.model_validate(
            {"normalized_value": "4", "confidence": 0.9, "reason": "ok", "extra": 1}
        )
