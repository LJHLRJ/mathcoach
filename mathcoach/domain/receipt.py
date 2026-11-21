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
