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
    """构建 10 题、300 秒的挑战赛状态。

    Args:
        cards: 知识点卡。
        now: 开始时间。
        seed: 抽题种子，同时拼进 ``date_key``。

    Returns:
        ``DailyState``，题量与时限取挑战赛常量。
    """
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
    """保存挑战赛结果。

    写入门被拦时记录审计并返回 None；用时不超过时限。

    Args:
        repository: 仓储。
        consent: 授权状态。
        state: 挑战赛状态。
        now: 结束时间。

    Returns:
        保存后的 ``ChallengeResult``；被拦截时为 None。
    """
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
