"""叙事层：把规则归因转成受限 JSON 报告，LLM 不可用时走模板。"""
from __future__ import annotations

import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import ErrorType
from .attribution import Attribution
from .credentials import load_analysis_credentials

ANALYSIS_PROMPT_VERSION = "analysis-1"
REPORT_SCHEMA_VERSION = "analysis-report/1"

ActionKind = Literal[
    "review_prerequisite",
    "review_card",
    "practice_similar",
    "slow_down",
    "self_check",
]

SYSTEM_ANALYST = (
    f"prompt_version={ANALYSIS_PROMPT_VERSION} 你是数学学习数据分析助手。"
    "只能使用输入的归因摘要，不得读取或推测原始作答文本；"
    "不得改变判分、错因枚举、BKT 或 FSRS 状态；"
    "error_type 与 confidence 必须原样复制输入；"
    "suggested_next_action.kind 必须原样复制输入；"
    "不得输出数学等价性结论；"
    "只输出严格 JSON，不输出 Markdown。"
)


class EvidenceModel(BaseModel):
    """报告中的一条证据。"""

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(min_length=1, max_length=80)
    value: str | int | float | None = None
    text: str = Field(min_length=1, max_length=300)


class SuggestedActionModel(BaseModel):
    """报告中的下一步建议。"""

    model_config = ConfigDict(extra="forbid")

    kind: ActionKind
    text: str = Field(min_length=1, max_length=300)
    target_card_id: str | None = None


class AttributionReport(BaseModel):
    """单次作答归因报告的 JSON schema。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = REPORT_SCHEMA_VERSION
    scenario: Literal["single_attempt"] = "single_attempt"
    error_type: ErrorType
    confidence: float = Field(ge=0, le=1)
    underlying_cause: str = Field(min_length=1, max_length=500)
    suggested_next_action: SuggestedActionModel
    evidence: list[EvidenceModel]
    caveats: list[str]
    needs_verification: bool
    source: Literal["template", "llm"] = "template"


class Narrator(Protocol):
    """叙事接口：输入规则归因，输出受限报告。"""

    def narrate(self, attribution: Attribution) -> AttributionReport:
        """生成归因报告。"""
        ...


class AnalysisClient(Protocol):
    """叙事层需要的最小模型客户端。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """返回模型原始文本，期望为 JSON。"""
        ...


class TemplateNarrator:
    """确定性模板叙事；不联网、不推断新结论。"""

    def narrate(self, attribution: Attribution) -> AttributionReport:
        """把规则归因转换为报告。"""
        cause = attribution.underlying_cause
        if attribution.verified_claim is not None:
            cause = f"{cause} {attribution.verified_claim.text}"
        return AttributionReport(
            error_type=attribution.error_type,
            confidence=attribution.confidence,
            underlying_cause=cause,
            suggested_next_action=SuggestedActionModel(
                kind=attribution.suggested_next_action.kind,
                text=attribution.suggested_next_action.text,
                target_card_id=attribution.suggested_next_action.target_card_id,
            ),
            evidence=[
                EvidenceModel(
                    metric_id=item.metric_id,
                    value=item.value,
                    text=item.text,
                )
                for item in attribution.evidence
            ],
            caveats=list(attribution.caveats),
            needs_verification=attribution.needs_verification,
            source="template",
        )


class OpenAIChatClient:
    """OpenAI 兼容客户端；仅在配置了密钥时构造。"""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        """创建客户端；导入与网络调用都延迟到这里。"""
        from openai import OpenAI

        self.model = model or "gpt-4o-mini"
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or None,
            timeout=30.0,
            max_retries=1,
        )

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """调用模型并返回 JSON 文本。"""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


def build_user_prompt(attribution: Attribution) -> str:
    """构造只含归因摘要的输入，不包含原始作答。"""
    payload = {
        "task": "single_attempt_attribution",
        "schema_version": REPORT_SCHEMA_VERSION,
        "attribution": attribution.to_dict(),
        "required_fields": [
            "error_type",
            "confidence",
            "underlying_cause",
            "suggested_next_action",
        ],
        "constraints": [
            "error_type 与 confidence 必须与 attribution 一致",
            "suggested_next_action.kind 必须与 attribution 一致",
            "evidence.metric_id 只能来自 attribution.evidence",
            "needs_verification 必须与 attribution 一致",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


class LLMNarrator:
    """LLM 叙事；任何异常或校验失败都回落到模板。"""

    def __init__(self, client: AnalysisClient, fallback: Narrator) -> None:
        """保存模型客户端与降级叙事器。"""
        self.client = client
        self.fallback = fallback

    def narrate(self, attribution: Attribution) -> AttributionReport:
        """生成并校验报告；失败时使用模板。"""
        try:
            raw = self.client.complete(
                SYSTEM_ANALYST, build_user_prompt(attribution)
            )
            report = AttributionReport.model_validate_json(raw)
        except Exception:
            return self.fallback.narrate(attribution)
        if not self._matches(report, attribution):
            return self.fallback.narrate(attribution)
        return report.model_copy(update={"source": "llm"})

    def _matches(
        self, report: AttributionReport, attribution: Attribution
    ) -> bool:
        """检查报告是否遵守确定性约束。"""
        if report.error_type is not attribution.error_type:
            return False
        if abs(report.confidence - attribution.confidence) > 1e-6:
            return False
        if report.needs_verification != attribution.needs_verification:
            return False
        action = attribution.suggested_next_action
        if report.suggested_next_action.kind != action.kind:
            return False
        if report.suggested_next_action.target_card_id != action.target_card_id:
            return False
        if any(
            word in report.underlying_cause
            for word in ("等价", "相等", "等于")
        ) and (
            attribution.verified_claim is None
            or attribution.needs_verification
        ):
            return False
        allowed = {item.metric_id for item in attribution.evidence}
        return all(item.metric_id in allowed for item in report.evidence)


def build_narrator(
    *,
    enabled: bool = False,
    client: AnalysisClient | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> Narrator:
    """按独立开关与分析专用凭据装配叙事层。

    没有显式开启、没有分析专用密钥时都返回模板；教学 AI 的
    ``OPENAI_API_KEY`` 不参与这里的选择。

    Args:
        enabled: 是否允许在线学情分析。
        client: 测试注入的模型客户端。
        api_key: 显式分析密钥；None 时读取分析专用环境变量或文件。
        base_url: 兼容接口地址。
        model: 模型名。

    Returns:
        ``LLMNarrator`` 或 ``TemplateNarrator``。
    """
    fallback = TemplateNarrator()
    if client is not None:
        return LLMNarrator(client, fallback)
    if not enabled:
        return fallback
    stored_key, stored_base, stored_model = load_analysis_credentials()
    final_key = api_key if api_key is not None else stored_key
    if not final_key:
        return fallback
    final_base = base_url if base_url is not None else stored_base
    final_model = model if model is not None else stored_model
    try:
        return LLMNarrator(
            OpenAIChatClient(
                final_key, base_url=final_base, model=final_model
            ),
            fallback,
        )
    except Exception:
        return fallback


def attribution_report_schema() -> dict[str, Any]:
    """返回归因报告的 JSON schema。"""
    return AttributionReport.model_json_schema()
