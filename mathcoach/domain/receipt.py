"""收据生成：只在独立做对或费曼复述通过时调用。"""
from datetime import datetime, timezone

from .basis import basis_for_receipt
from .hint_ladder import independence_for
from .models import Exercise, KnowledgeCard, Receipt


def build_receipt(
    card: KnowledgeCard,
    exercise: Exercise,
    goal: str,
    max_hint_level: int,
    duration_s: int,
    restatement_quality: str | None = None,
    judged: bool = True,
    verified: bool = True,
) -> Receipt:
    """生成一张收据。

    独立程度由 ``max_hint_level`` 推导（≤3 独立，≥4 半独立）；依据文字在创建时
    写入 ``basis``，展示层不再补算；时间统一用 UTC。

    Args:
        card: 当前知识卡片。
        exercise: 刚做对的题目。
        goal: 本次会话的目标。
        max_hint_level: 本题用到的最高提示层级。
        duration_s: 本题用时（秒）。
        restatement_quality: L6 复述质量；未走复述时为 None。
        judged: 是否通过判定；False 时依据写“未通过判定，不生成收据”。
        verified: 符号验证是否通过；False 时按半独立记录。

    Returns:
        不可变的 ``Receipt``。
    """
    return Receipt(
        card_id=card.id,
        stage=card.stage,
        course=card.course,
        exercise_type=exercise.kind,
        duration_s=duration_s,
        max_hint_level=max_hint_level,
        goal=goal,
        independence=independence_for(max_hint_level),
        created_at=datetime.now(timezone.utc),
        restatement_quality=restatement_quality,
        exercise_id=exercise.id,
        basis=basis_for_receipt(max_hint_level, judged, verified),
    )
