"""挑战赛：10 题限时、结果持久化与本地最好成绩。"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mathcoach.content.loader import load_content
from mathcoach.domain.models import ChallengeResult, Consent
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.session.challenge import (
    CHALLENGE_QUESTION_COUNT,
    CHALLENGE_TIME_LIMIT_S,
    build_challenge_state,
    save_challenge_result,
)

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def _cards():
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    return cards


def test_challenge_state_has_ten_questions_and_five_minutes():
    state = build_challenge_state(_cards(), NOW, seed=7)
    assert len(state.questions) == CHALLENGE_QUESTION_COUNT == 10
    assert state.time_limit_s == CHALLENGE_TIME_LIMIT_S == 300
    assert len({question.card.id for question in state.questions}) == 10


def test_save_challenge_result_records_score_and_audit():
    repository = InMemoryRepository()
    state = build_challenge_state(_cards(), NOW, seed=7)
    state.correct = 7

    result = save_challenge_result(
        repository, Consent(), state, NOW + timedelta(seconds=120)
    )

    assert result is not None
    assert result.score == 7
    assert result.total == 10
    assert result.duration_s == 120
    best = repository.list_challenge_results()
    assert best[0].id == result.id
    assert any(
        entry.op == "challenge" and entry.result == "ok"
        for entry in repository.list_audit()
    )


def test_challenge_result_blocked_without_memory_consent():
    repository = InMemoryRepository()
    state = build_challenge_state(_cards(), NOW, seed=7)

    result = save_challenge_result(
        repository,
        Consent(memory=False, mistake_book=True),
        state,
        NOW + timedelta(seconds=10),
    )

    assert result is None
    assert repository.list_challenge_results() == []
    assert any(
        entry.result.startswith("blocked") for entry in repository.list_audit()
    )


def test_best_scores_sort_by_score_then_duration():
    repository = InMemoryRepository()
    repository.save_challenge_result(
        ChallengeResult(5, 10, 200, NOW)
    )
    repository.save_challenge_result(
        ChallengeResult(7, 10, 300, NOW)
    )
    repository.save_challenge_result(
        ChallengeResult(7, 10, 250, NOW)
    )

    best = repository.list_challenge_results(limit=3)
    assert [(entry.score, entry.duration_s) for entry in best] == [
        (7, 250),
        (7, 300),
        (5, 200),
    ]
