"""里程碑庆祝：连对 5 题、复习完成、错题清空。"""
from types import SimpleNamespace

from mathcoach.domain.models import Consent
from mathcoach.ui import milestones

PERSISTENT = Consent(memory=True, mistake_book=True)


def _engine(attempts):
    return SimpleNamespace(
        card=SimpleNamespace(id="card-1"),
        state=SimpleNamespace(attempts=attempts),
    )


def test_five_correct_celebrates_once(monkeypatch):
    calls = []
    monkeypatch.setattr(
        milestones,
        "st",
        SimpleNamespace(session_state={}),
    )
    monkeypatch.setattr(
        milestones,
        "queue_celebration",
        lambda kind, consent: calls.append(kind),
    )
    engine = _engine([{"correct": True}] * 5)

    assert milestones.celebrate_five_correct(engine, PERSISTENT) is True
    assert milestones.celebrate_five_correct(engine, PERSISTENT) is False
    assert calls == ["five-correct"]


def test_five_correct_requires_unbroken_streak(monkeypatch):
    calls = []
    monkeypatch.setattr(
        milestones,
        "st",
        SimpleNamespace(session_state={}),
    )
    monkeypatch.setattr(
        milestones,
        "queue_celebration",
        lambda kind, consent: calls.append(kind),
    )
    engine = _engine(
        [{"correct": True}] * 4
        + [{"correct": False}]
        + [{"correct": True}] * 4
    )

    assert milestones.celebrate_five_correct(engine, PERSISTENT) is False
    assert calls == []


def test_review_complete_celebrates_once(monkeypatch):
    calls = []
    monkeypatch.setattr(
        milestones,
        "st",
        SimpleNamespace(session_state={}),
    )
    monkeypatch.setattr(
        milestones,
        "queue_celebration",
        lambda kind, consent: calls.append(kind),
    )
    state = SimpleNamespace(finished=True, date_key="review-1")

    assert milestones.celebrate_review_complete(state, PERSISTENT) is True
    assert milestones.celebrate_review_complete(state, PERSISTENT) is False
    assert calls == ["review-complete"]


def test_mistakes_cleared_celebrates_only_with_removed_rows(monkeypatch):
    calls = []
    monkeypatch.setattr(
        milestones,
        "st",
        SimpleNamespace(session_state={}),
    )
    monkeypatch.setattr(
        milestones,
        "queue_celebration",
        lambda kind, consent: calls.append(kind),
    )

    assert milestones.celebrate_mistakes_cleared(PERSISTENT, 0) is False
    assert milestones.celebrate_mistakes_cleared(PERSISTENT, 2) is True
    assert milestones.celebrate_mistakes_cleared(PERSISTENT, 1) is False
    assert calls == ["mistakes-cleared"]
