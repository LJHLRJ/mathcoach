"""叙事层：JSON schema、LLM 降级与验证拒绝。"""
import json

import pytest
from pydantic import ValidationError

from mathcoach.analytics import (
    AttributionReport,
    LLMNarrator,
    MathClaim,
    TemplateNarrator,
    attribution_report_schema,
    build_attribution,
    build_narrator,
)
from mathcoach.domain.models import ErrorType, Exercise, ExerciseKind


class _FakeClient:
    """记录输入并返回固定文本。"""

    def __init__(self, response: str) -> None:
        """保存固定响应。"""
        self.response = response
        self.prompts: list[str] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """记录模型输入并返回固定文本。"""
        self.prompts.append(user_prompt)
        return self.response


def _exercise() -> Exercise:
    """构造叙事测试用练习。"""
    return Exercise(
        id="card-1-e1",
        card_id="card-1",
        kind=ExerciseKind.CHOICE,
        stem="题干",
        answer="A",
        solution_outline="标准思路",
        options=("A", "B"),
    )


def _attribution():
    """构造提示依赖归因。"""
    return build_attribution(
        _exercise(),
        ["SECRET_WRONG"],
        ("step",),
        max_hint_level=4,
        attempt_count=2,
    )


def _payload(attribution) -> dict:
    """构造合法报告 JSON。"""
    return {
        "schema_version": "analysis-report/1",
        "scenario": "single_attempt",
        "error_type": attribution.error_type.value,
        "confidence": attribution.confidence,
        "underlying_cause": "模型解释",
        "suggested_next_action": {
            "kind": attribution.suggested_next_action.kind,
            "text": "先自己写出下一步",
            "target_card_id": (
                attribution.suggested_next_action.target_card_id
            ),
        },
        "evidence": [
            {
                "metric_id": "hint.max_level",
                "value": 4,
                "text": "最高提示 L4",
            }
        ],
        "caveats": [],
        "needs_verification": attribution.needs_verification,
        "source": "template",
    }


def test_schema_has_required_business_fields():
    """JSON schema 要求四个业务字段。"""
    schema = attribution_report_schema()
    required = set(schema["required"])

    assert {
        "error_type",
        "confidence",
        "underlying_cause",
        "suggested_next_action",
    } <= required


def test_schema_rejects_missing_or_extra_fields():
    """缺少字段或出现多余字段都校验失败。"""
    payload = _payload(_attribution())
    missing = dict(payload)
    missing.pop("underlying_cause")
    with pytest.raises(ValidationError):
        AttributionReport.model_validate(missing)

    extra = dict(payload)
    extra["extra"] = 1
    with pytest.raises(ValidationError):
        AttributionReport.model_validate(extra)


def test_without_api_key_uses_template(monkeypatch):
    """没有密钥时直接使用模板叙事。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    narrator = build_narrator()
    report = narrator.narrate(_attribution())

    assert isinstance(narrator, TemplateNarrator)
    assert report.source == "template"
    assert report.error_type is ErrorType.STEP_JUMP


def test_invalid_json_falls_back_to_template():
    """模型返回非 JSON 时降级。"""
    narrator = LLMNarrator(
        _FakeClient("not json"), TemplateNarrator()
    )
    report = narrator.narrate(_attribution())

    assert report.source == "template"


def test_missing_schema_field_falls_back_to_template():
    """模型 JSON 缺少必填字段时降级。"""
    payload = _payload(_attribution())
    payload.pop("underlying_cause")
    narrator = LLMNarrator(
        _FakeClient(json.dumps(payload, ensure_ascii=False)),
        TemplateNarrator(),
    )
    report = narrator.narrate(_attribution())

    assert report.source == "template"


def test_semantic_mismatch_falls_back_to_template():
    """模型改错因或置信度时降级。"""
    payload = _payload(_attribution())
    payload["error_type"] = ErrorType.CONCEPT.value
    narrator = LLMNarrator(
        _FakeClient(json.dumps(payload, ensure_ascii=False)),
        TemplateNarrator(),
    )
    report = narrator.narrate(_attribution())

    assert report.source == "template"


def test_valid_llm_report_is_used():
    """合法 JSON 通过校验后标记为 LLM 来源。"""
    payload = _payload(_attribution())
    narrator = LLMNarrator(
        _FakeClient(json.dumps(payload, ensure_ascii=False)),
        TemplateNarrator(),
    )
    report = narrator.narrate(_attribution())

    assert report.source == "llm"
    assert report.underlying_cause == "模型解释"


def test_llm_prompt_excludes_raw_answer():
    """模型输入只含归因摘要，不含原始作答。"""
    payload = _payload(_attribution())
    client = _FakeClient(json.dumps(payload, ensure_ascii=False))
    narrator = LLMNarrator(client, TemplateNarrator())

    narrator.narrate(_attribution())

    assert client.prompts
    assert "SECRET_WRONG" not in client.prompts[0]
    assert "hint.max_level" in client.prompts[0]


def test_verify_rejection_degrades_to_self_check():
    """验证拒绝时模板只提示自查，不输出等价性断言。"""
    attribution = build_attribution(
        _exercise(),
        ["SECRET_WRONG"],
        ("step",),
        max_hint_level=4,
        math_claim=MathClaim(
            "__import__('os')", "x", frozenset({"x"})
        ),
    )
    report = TemplateNarrator().narrate(attribution)

    assert report.needs_verification is True
    assert "建议自行核对" in report.underlying_cause
    assert "等价" not in report.underlying_cause
