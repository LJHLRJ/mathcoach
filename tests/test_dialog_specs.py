"""追问元数据：目录加载、verify 预检、问法校验与降级。"""
import json

import yaml

from mathcoach.tutor.dialog import (
    CATALOG,
    SPECS,
    build_follow_up,
    default_verify,
    load_dialog_catalog,
)
from mathcoach.verify.symbolic import SymbolicVerdict


class _TemplateClient:
    """返回输入模板的确定性假客户端。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """把 template_prompt 原样作为问法返回。"""
        payload = json.loads(user_prompt)
        return json.dumps(
            {"prompt": payload["template_prompt"]}, ensure_ascii=False
        )


class _BadNumberClient:
    """返回带未授权数字的问法。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """固定返回一个新增数字。"""
        return json.dumps({"prompt": "请计算 5/13 的值。"}, ensure_ascii=False)


class _LeakClient:
    """返回包含答案数值的问法。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """固定返回同角平方关系的完整等式。"""
        return json.dumps(
            {"prompt": "sin²x + cos²x = 1，对吗？"}, ensure_ascii=False
        )


class _VagueClient:
    """返回不含任何题目内容的问法。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """固定返回一句空泛追问。"""
        return json.dumps({"prompt": "答案是什么？"}, ensure_ascii=False)


def test_catalog_loads_pilot_specs() -> None:
    """试点范围只覆盖单一 KC：三道题各有 L3/L4 两个追问。"""
    assert CATALOG.errors == ()
    assert len(SPECS) == 6
    for spec in SPECS.values():
        assert 2 <= len(spec.acceptable) <= 4
        assert spec.template_prompt
        assert spec.supplement_prompt
        assert spec.kc_ids == ("kc-hs-trig-002-f1",)


def test_catalog_rejects_invalid_verify(tmp_path) -> None:
    """verify 不通过的追问元数据会被跳过并记录错误。"""
    payload = {
        "version": 1,
        "unit_id": "unit-hs-trig-002",
        "card_id": "hs-trig-002",
        "follow_ups": [
            {
                "exercise_id": "hs-trig-002-e1",
                "levels": [
                    {
                        "level": 3,
                        "kc_ids": ["kc-hs-trig-002-f1"],
                        "expression": "1/0",
                        "expected": "1",
                        "variables": [],
                        "facts": {},
                        "acceptable": ["1", "等于 1"],
                        "template_prompt": "测试问法",
                        "supplement_prompt": "补充问法",
                        "forbidden_in_prompt": [],
                    }
                ],
            }
        ],
    }
    (tmp_path / "invalid.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
    )

    catalog = load_dialog_catalog(tmp_path, verify_fn=default_verify)

    assert catalog.specs == {}
    assert any("verify=" in error for error in catalog.errors)


def test_build_follow_up_uses_template_and_verifies_content() -> None:
    """正常路径返回 LLM 问法并带 verify 结论。"""
    result = build_follow_up(
        "hs-trig-002-e1", 3, client=_TemplateClient()
    )

    assert result.follow_up is not None
    assert result.verify_verdict == "equivalent"
    assert "sin²x + cos²x" in result.follow_up.prompt


def test_build_follow_up_verify_rejection_falls_back() -> None:
    """verify 拒绝时返回降级原因，不生成追问。"""
    result = build_follow_up(
        "hs-trig-002-e1",
        3,
        client=_TemplateClient(),
        verify_fn=lambda left, right, variables: SymbolicVerdict.REJECTED,
    )

    assert result.follow_up is None
    assert result.fallback_reason == "verify_rejected"
    assert result.spec is not None


def test_build_follow_up_without_llm_falls_back() -> None:
    """没有 LLM 时不生成追问。"""
    result = build_follow_up("hs-trig-002-e1", 3, client=None)

    assert result.follow_up is None
    assert result.fallback_reason == "llm_unavailable"


def test_build_follow_up_rejects_new_numbers() -> None:
    """LLM 新增数字时拒绝问法。"""
    result = build_follow_up(
        "hs-trig-002-e2", 3, client=_BadNumberClient()
    )

    assert result.follow_up is None
    assert result.fallback_reason.startswith("llm_rejected")


def test_build_follow_up_rejects_answer_leak() -> None:
    """LLM 在问法中泄露答案时拒绝。"""
    result = build_follow_up(
        "hs-trig-002-e1", 3, client=_LeakClient()
    )

    assert result.follow_up is None
    assert result.fallback_reason.startswith("llm_rejected")


def test_build_follow_up_rejects_vague_question() -> None:
    """LLM 未保留任何题目内容时拒绝。"""
    result = build_follow_up(
        "hs-trig-002-e1", 3, client=_VagueClient()
    )

    assert result.follow_up is None
    assert "未保留追问的数学内容" in result.fallback_reason
