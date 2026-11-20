"""仓库内真实内容必须能通过严格模式校验。"""
from pathlib import Path

from mathcoach.content.loader import load_content

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def test_real_content_loads_in_strict_mode():
    cards, result = load_content(CONTENT_ROOT, strict=True)
    assert result.ok
    assert len(cards) >= 1
    card = cards[0]
    assert card.id == "hs-function-intro-001"
    assert len(card.exercises) == 3
    assert all(exercise.kind.value == "choice" for exercise in card.exercises)
