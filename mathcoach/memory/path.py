"""学习路径：按课程聚合卡片进度并给出下一张建议卡。"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain.models import KnowledgeCard, MistakeEntry, Receipt, ReviewState, Stage

STATUS_NOT_STARTED = "未开始"
STATUS_LEARNING = "学习中"
STATUS_REVIEW = "需复习"
STATUS_DONE = "已完成"


@dataclass(frozen=True)
class CardProgress:
    card: KnowledgeCard
    completed_exercises: int
    total_exercises: int
    status: str


@dataclass(frozen=True)
class CourseProgress:
    stage: Stage
    course: str
    cards: tuple[CardProgress, ...]
    completed_cards: int
    total_cards: int


@dataclass(frozen=True)
class LearningPath:
    courses: tuple[CourseProgress, ...]
    recommended_card: KnowledgeCard | None
    recommended_reason: str


def build_learning_path(
    cards: list[KnowledgeCard],
    receipts: list[Receipt],
    mistakes: list[MistakeEntry],
) -> LearningPath:
    completed_exercises = {
        receipt.exercise_id for receipt in receipts if receipt.exercise_id
    }
    open_mistake_cards = {
        mistake.card_id
        for mistake in mistakes
        if mistake.review_state is not ReviewState.MASTERED
    }

    progress: dict[str, CardProgress] = {}
    for card in cards:
        done = sum(
            1 for exercise in card.exercises if exercise.id in completed_exercises
        )
        total = len(card.exercises)
        if total > 0 and done == total and card.id not in open_mistake_cards:
            status = STATUS_DONE
        elif card.id in open_mistake_cards:
            status = STATUS_REVIEW
        elif done > 0:
            status = STATUS_LEARNING
        else:
            status = STATUS_NOT_STARTED
        progress[card.id] = CardProgress(card, done, total, status)

    grouped: dict[tuple[Stage, str], list[CardProgress]] = {}
    for card in cards:
        key = (card.stage, card.course)
        grouped.setdefault(key, []).append(progress[card.id])

    courses = tuple(
        CourseProgress(
            stage=stage,
            course=course,
            cards=tuple(items),
            completed_cards=sum(1 for item in items if item.status == STATUS_DONE),
            total_cards=len(items),
        )
        for (stage, course), items in grouped.items()
    )

    for preferred in (STATUS_REVIEW, STATUS_LEARNING, STATUS_NOT_STARTED):
        for card in cards:
            if progress[card.id].status == preferred:
                reason = {
                    STATUS_REVIEW: "优先处理未掌握的错题",
                    STATUS_LEARNING: "继续完成这张卡片",
                    STATUS_NOT_STARTED: "按课程顺序开始新卡片",
                }[preferred]
                return LearningPath(courses, card, reason)

    return LearningPath(courses, None, "全部卡片已完成，可进入复习巩固")
