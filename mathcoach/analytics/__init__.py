"""分析层入口：只读统计、规则归因与受限叙事。

边界：
- 统计只读消费 receipts / mistakes / mastery / review_queue 的查询结果；
- 规则归因复用 domain.diagnosis 与 verify.symbolic，不另造判定；
- 叙事层只消费结构化归因，LLM 不可用时降级为模板；
- 不写 BKT、FSRS、错题或复习队列。
"""
from .attribution import (
    Attribution,
    Evidence,
    MathClaim,
    SuggestedAction,
    VerifiedClaim,
    build_attribution,
    resolve_error_code,
    verify_math_claim,
)
from .errors import (
    DEFAULT_CODE_BY_ERROR_TYPE,
    ERROR_CODE_SPECS,
    ErrorCode,
    ErrorCodeSpec,
    coerce_error_code,
    default_error_code,
    error_code_spec,
    error_type_for_code,
)
from .models import (
    ANALYSIS_SCHEMA_VERSION,
    AnalysisRepository,
    AnalysisScope,
    AnalysisSnapshot,
    AnalysisWindow,
    CardSnapshot,
    DataQuality,
    ErrorCount,
    ErrorTrendView,
    MasteryDelta,
    MetricValue,
)
from .narrative import (
    ANALYSIS_PROMPT_VERSION,
    SYSTEM_ANALYST,
    AttributionReport,
    LLMNarrator,
    Narrator,
    TemplateNarrator,
    attribution_report_schema,
    build_narrator,
    build_user_prompt,
)
from .stats import build_snapshot

__all__ = [
    "ANALYSIS_PROMPT_VERSION",
    "ANALYSIS_SCHEMA_VERSION",
    "DEFAULT_CODE_BY_ERROR_TYPE",
    "ERROR_CODE_SPECS",
    "SYSTEM_ANALYST",
    "AnalysisRepository",
    "AnalysisScope",
    "AnalysisSnapshot",
    "AnalysisWindow",
    "Attribution",
    "AttributionReport",
    "CardSnapshot",
    "DataQuality",
    "ErrorCode",
    "ErrorCodeSpec",
    "ErrorCount",
    "ErrorTrendView",
    "Evidence",
    "LLMNarrator",
    "MasteryDelta",
    "MathClaim",
    "MetricValue",
    "Narrator",
    "SuggestedAction",
    "TemplateNarrator",
    "VerifiedClaim",
    "attribution_report_schema",
    "build_attribution",
    "build_narrator",
    "build_snapshot",
    "build_user_prompt",
    "coerce_error_code",
    "default_error_code",
    "error_code_spec",
    "error_type_for_code",
    "resolve_error_code",
    "verify_math_claim",
]
