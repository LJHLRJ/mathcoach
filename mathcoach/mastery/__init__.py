"""掌握度增强：速度观测权重、KC 影子视图与弱正确判定；不修改 BKT 公式。"""
from .kc_view import (
    MAX_PROGRESS,
    WEAK_KC_THRESHOLD,
    KCProgress,
    build_kc_progress,
    kc_card_ids,
    weak_kc_recommendations,
)
from .repair import (
    RepairItem,
    RepairPlan,
    build_repair_plan,
)
from .speed import (
    DEFAULT_FLOOR_WEIGHT,
    DEFAULT_MAX_DURATION_S,
    DEFAULT_MIN_SAMPLES,
    DEFAULT_POLICY,
    DEFAULT_REFERENCE_S,
    DEFAULT_WEAK_RATIO,
    SpeedPolicy,
    is_weak_correct,
    load_speed_policy,
    normalize_duration,
    observation_weight,
    quality_for_correct,
    reference_seconds_from_history,
)

__all__ = [
    "DEFAULT_FLOOR_WEIGHT",
    "DEFAULT_MAX_DURATION_S",
    "DEFAULT_MIN_SAMPLES",
    "DEFAULT_POLICY",
    "DEFAULT_REFERENCE_S",
    "DEFAULT_WEAK_RATIO",
    "MAX_PROGRESS",
    "WEAK_KC_THRESHOLD",
    "KCProgress",
    "RepairItem",
    "RepairPlan",
    "SpeedPolicy",
    "build_kc_progress",
    "build_repair_plan",
    "is_weak_correct",
    "kc_card_ids",
    "load_speed_policy",
    "normalize_duration",
    "observation_weight",
    "quality_for_correct",
    "reference_seconds_from_history",
    "weak_kc_recommendations",
]
