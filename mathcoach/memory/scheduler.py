"""复习调度：纯函数，可单测。

规则（设计文档 §6）：
- 新错题当天进入复习清单；
- 独立做对一次 → 明天再复习；连续两次独立做对 → 已掌握并退出清单；
- 半独立做对 → 连续独立计数清零，三天后再复习；
- 清单按“今天 / 明天 / 三天后”分档，每档不超过 3 项。
"""
from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import yaml

from ..domain.fsrs import DEFAULT_PARAMS, FsrsParams, params_from_mapping
from ..domain.models import KnowledgeCard, MistakeEntry, ReviewItem, ReviewState
from ..domain.review_pack import compose
from ..domain.spaced_repetition import Bucket, bucket_for
from ..timeutil import end_of_local_day, start_of_local_day_after

if TYPE_CHECKING:
    from ..session.daily import DailyQuestion

REVIEW_LIMIT = 3
MASTERY_STREAK = 2


def scheduler_mode() -> str:
    """读取调度器实现；只有显式 sm2 才回退，其余情况默认 FSRS。"""
    value = os.environ.get("MATHCOACH_SCHEDULER", "fsrs").strip().lower()
    return "sm2" if value == "sm2" else "fsrs"


@lru_cache(maxsize=1)
def fsrs_params() -> FsrsParams:
    """读取 content/fsrs_params.yaml；文件缺失时回落到内置默认参数。"""
    path = Path(__file__).resolve().parents[2] / "content" / "fsrs_params.yaml"
    if not path.exists():
        return DEFAULT_PARAMS
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return params_from_mapping(data)


@dataclass(frozen=True)
class ReviewPlan:
    today: tuple[ReviewItem, ...]
    tomorrow: tuple[ReviewItem, ...]
    in_three_days: tuple[ReviewItem, ...]


def next_review(
    entry: MistakeEntry, independent: bool, now: datetime
) -> tuple[ReviewState, int, int, datetime | None]:
    """返回 (新复习状态, 复习次数, 连续独立做对次数, 下次到期时间)。"""
    if entry.review_state is ReviewState.MASTERED:
        return ReviewState.MASTERED, entry.review_count, entry.consecutive_correct, None

    review_count = entry.review_count + 1
    if independent:
        streak = entry.consecutive_correct + 1
        if streak >= MASTERY_STREAK:
            return ReviewState.MASTERED, review_count, streak, None
        return (
            ReviewState.REVIEWING,
            review_count,
            streak,
            start_of_local_day_after(now, 1),
        )

    return (
        ReviewState.REVIEWING,
        review_count,
        0,
        start_of_local_day_after(now, 3),
    )


def build_plan(
    items: Iterable[ReviewItem], now: datetime, limit: int = REVIEW_LIMIT
) -> ReviewPlan:
    """把待复习项分到三档，每档最多 limit 项。"""
    today_end = end_of_local_day(now)
    tomorrow_end = end_of_local_day(now + timedelta(days=1))
    three_day_end = end_of_local_day(now + timedelta(days=3))
    buckets: dict[str, list[ReviewItem]] = {
        "today": [],
        "tomorrow": [],
        "in_three_days": [],
    }

    for item in sorted(items, key=lambda current: current.due_at):
        if item.mistake.review_state is ReviewState.MASTERED:
            continue
        if item.due_at <= today_end:
            bucket = "today"
        elif item.due_at <= tomorrow_end:
            bucket = "tomorrow"
        elif item.due_at <= three_day_end:
            bucket = "in_three_days"
        else:
            continue
        if len(buckets[bucket]) < limit:
            buckets[bucket].append(item)

    return ReviewPlan(
        today=tuple(buckets["today"]),
        tomorrow=tuple(buckets["tomorrow"]),
        in_three_days=tuple(buckets["in_three_days"]),
    )


def build_review_queue(repo, now: datetime) -> dict[Bucket, list[MistakeEntry]]:
    """只返回 next_review_at <= now 的条目，按 interval_days 映射到三档。"""
    queue: dict[Bucket, list[MistakeEntry]] = defaultdict(list)
    for item in repo.list_due_mistakes(now):
        queue[bucket_for(item.interval_days)].append(item)
    return dict(queue)


def build_review_pack(
    repository,
    cards: list[KnowledgeCard],
    now: datetime,
    priority_card_ids: set[str] | None = None,
    total: int = 5,
    new_ratio: int = 0,
) -> list[DailyQuestion]:
    """混合复习包：缺口 1 + 变式 1 固定，其余按新卡占比分配到到期/新卡。"""
    # 延迟导入，避免 scheduler -> daily -> repository 的循环依赖
    from ..session.daily import DailyQuestion

    by_exercise = {
        exercise.id: (card, exercise)
        for card in cards
        for exercise in card.exercises
    }
    due_questions: list[DailyQuestion] = []
    for item in sorted(repository.list_review_items(), key=lambda current: current.due_at):
        pair = by_exercise.get(item.mistake.exercise_id)
        if pair is not None:
            due_questions.append(DailyQuestion(card=pair[0], exercise=pair[1]))

    cards_by_id = {card.id: card for card in cards}
    gap_questions: list[DailyQuestion] = []
    for card_id in sorted(priority_card_ids or set()):
        card = cards_by_id.get(card_id)
        if card is not None and card.exercises:
            gap_questions.append(DailyQuestion(card=card, exercise=card.exercises[0]))

    variant_questions: list[DailyQuestion] = []
    for mistake in repository.list_mistakes(limit=None):
        card = cards_by_id.get(mistake.card_id)
        if card is None:
            continue
        for exercise in card.exercises:
            if exercise.id != mistake.exercise_id:
                variant_questions.append(DailyQuestion(card=card, exercise=exercise))
                break

    seen_card_ids = {
        receipt.card_id for receipt in repository.list_receipts(limit=None)
    } | {
        mistake.card_id for mistake in repository.list_mistakes(limit=None)
    }
    excluded = seen_card_ids | set(priority_card_ids or ())
    new_questions = [
        DailyQuestion(card=card, exercise=card.exercises[0])
        for card in cards
        if card.id not in excluded and card.exercises
    ]

    if not (
        due_questions or gap_questions or variant_questions or new_questions
    ):
        return []

    selected = compose(
        due_questions,
        gap_questions,
        variant_questions,
        total,
        new=new_questions,
        new_ratio=new_ratio,
    )
    if len(selected) < total:
        # 混合队列不足时从全卡池补齐，保证首期固定 5 题
        seen = {question.exercise.id for question in selected}
        for card in cards:
            for exercise in card.exercises:
                if exercise.id in seen:
                    continue
                selected.append(DailyQuestion(card=card, exercise=exercise))
                seen.add(exercise.id)
                if len(selected) >= total:
                    return selected
    return selected
