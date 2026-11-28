"""追问构建：元数据 -> verify 预检 -> LLM 问法 -> 可展示追问。"""
from __future__ import annotations

from .catalog import CATALOG, DialogCatalog, VerifyFn, default_verify
from .models import FollowUp, FollowUpBuild, FollowUpSpec
from .wording import (
    FollowUpClient,
    generate_follow_up_wording,
)
from ...verify.symbolic import SymbolicVerdict

_VERIFIED: dict[tuple[str, int], SymbolicVerdict] = {}


def _verify_spec(
    spec: FollowUpSpec, verify_fn: VerifyFn | None
) -> SymbolicVerdict:
    """验证追问数学内容；默认 verify 结果按题/层级缓存。"""
    if verify_fn is not None:
        return verify_fn(
            spec.expression, spec.expected, frozenset(spec.variables)
        )
    key = (spec.exercise_id, spec.level)
    cached = _VERIFIED.get(key)
    if cached is not None:
        return cached
    verdict = default_verify(
        spec.expression, spec.expected, frozenset(spec.variables)
    )
    _VERIFIED[key] = verdict
    return verdict


def build_follow_up(
    exercise_id: str,
    level: int,
    *,
    client: FollowUpClient | None,
    supplement: bool = False,
    catalog: DialogCatalog | None = None,
    verify_fn: VerifyFn | None = None,
) -> FollowUpBuild:
    """构建一条追问；任何失败都返回带原因的降级结果。

    Args:
        exercise_id: 当前题目 ID。
        level: 追问层级，只允许 3 或 4。
        client: 问法生成的 LLM 客户端；None 表示离线。
        supplement: 是否是部分命中后的补充追问。
        catalog: 追问目录；None 使用默认目录。
        verify_fn: 数学内容验证函数；None 使用离线 verify。

    Returns:
        ``FollowUpBuild``；``follow_up`` 为 None 时上层应回退陈述式提示。
    """
    source = catalog or CATALOG
    spec = source.specs.get((exercise_id, level))
    if spec is None:
        return FollowUpBuild(None, None, "no_spec")
    verdict = _verify_spec(spec, verify_fn)
    if verdict is not SymbolicVerdict.EQUIVALENT:
        return FollowUpBuild(None, spec, "verify_rejected", verdict.value)
    if client is None:
        return FollowUpBuild(None, spec, "llm_unavailable", verdict.value)
    wording, reason = generate_follow_up_wording(
        spec, supplement=supplement, client=client
    )
    if wording is None:
        return FollowUpBuild(None, spec, reason, verdict.value)
    return FollowUpBuild(
        FollowUp(spec=spec, prompt=wording.prompt, supplement=supplement),
        spec,
        "",
        verdict.value,
    )
