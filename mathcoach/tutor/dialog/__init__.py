"""追问引擎：L3–L4 追问、三档判定与效果信号。

边界：
- 追问数学内容来自 ``content/dialog/*.yaml``，并经 verify 预检；
- LLM 只改写问法，数字/表达式/答案不得由模型自由生成；
- 判定独立于 domain/judge，不改判分、BKT、FSRS 或错题复习。
"""
from .builder import build_follow_up
from .catalog import (
    CATALOG,
    DEFAULT_DIALOG_DIR,
    SPECS,
    DialogCatalog,
    DialogCatalogError,
    VerifyFn,
    default_verify,
    load_dialog_catalog,
)
from .judge import (
    HIT_COVERAGE,
    PARTIAL_COVERAGE,
    PARTIAL_RELATIVE,
    judge_follow_up,
)
from .models import (
    DialogEvent,
    DialogEventKind,
    DialogOutcome,
    FollowUp,
    FollowUpBuild,
    FollowUpSpec,
    FollowUpWording,
)
from .store import (
    DIALOG_DB_ENV,
    DIALOG_DB_NAME,
    DIALOG_TABLE,
    DialogStore,
    dialog_db_path,
)
from .wording import (
    MAX_PROMPT_CHARS,
    PROMPT_VERSION,
    SYSTEM_FOLLOW_UP,
    FollowUpClient,
    build_follow_up_client,
    build_follow_up_prompt,
    generate_follow_up_wording,
    validate_follow_up_wording,
)

__all__ = [
    "CATALOG",
    "DEFAULT_DIALOG_DIR",
    "DIALOG_DB_ENV",
    "DIALOG_DB_NAME",
    "DIALOG_TABLE",
    "HIT_COVERAGE",
    "MAX_PROMPT_CHARS",
    "PARTIAL_COVERAGE",
    "PARTIAL_RELATIVE",
    "PROMPT_VERSION",
    "SPECS",
    "SYSTEM_FOLLOW_UP",
    "DialogCatalog",
    "DialogCatalogError",
    "DialogEvent",
    "DialogEventKind",
    "DialogOutcome",
    "DialogStore",
    "FollowUp",
    "FollowUpBuild",
    "FollowUpClient",
    "FollowUpSpec",
    "FollowUpWording",
    "VerifyFn",
    "build_follow_up",
    "build_follow_up_client",
    "build_follow_up_prompt",
    "default_verify",
    "dialog_db_path",
    "generate_follow_up_wording",
    "judge_follow_up",
    "load_dialog_catalog",
    "validate_follow_up_wording",
]
