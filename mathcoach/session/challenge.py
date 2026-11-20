"""挑战赛：10 题限时赛，结果写入本地最好成绩。"""
from __future__ import annotations

from datetime import datetime

from ..domain.models import ChallengeResult, Consent, KnowledgeCard
from ..memory.repository import Repository
from ..safety.redlines import (
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
)
from .daily import (
    DailyState,
    build_quiz_questions,
    elapsed_seconds,
)

CHALLENGE_QUESTION_COUNT = 10
CHALLENGE_TIME_LIMIT_S = 300


def build_challenge_state(
    cards: list[KnowledgeCard], now: datetime, seed: int
) -> DailyState:
    return DailyState(
        date_key=f"challenge-{seed}",
        questions=build_quiz_questions(
            cards, seed, count=CHALLENGE_QUESTION_COUNT
        ),
        started_at=now,
        time_limit_s=CHALLENGE_TIME_LIMIT_S,
    )


def save_challenge_result(
    repository: Repository,
    consent: Consent,
    state: DailyState,
    now: datetime,
) -> ChallengeResult | None:
    try:
        assert_write_allowed("challenge", consent=consent)
    except (WriteBlocked, ConfirmationRequired) as exc:
        repository.record_audit("challenge", f"blocked:{exc.reason}")
        return None
    result = repository.save_challenge_result(
        ChallengeResult(
            score=state.correct,
            total=len(state.questions),
            duration_s=min(state.time_limit_s, elapsed_seconds(state, now)),
            created_at=now,
        )
    )
    repository.record_audit("challenge", "ok")
    return result
