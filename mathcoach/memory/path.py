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
    """单张卡的完成情况。

    Attributes:
        card: 知识点卡。
        completed_exercises: 已有收据的题目数。
        total_exercises: 题目总数。
        status: 状态，取 ``STATUS_*`` 常量之一。
    """

    card: KnowledgeCard
    completed_exercises: int
    total_exercises: int
    status: str


@dataclass(frozen=True)
class CourseProgress:
    """按学段与课程聚合的进度。

    Attributes:
        stage: 学段。
        course: 课程名。
        cards: 课程内的卡片进度。
        completed_cards: 已完成的卡片数。
        total_cards: 卡片总数。
    """

    stage: Stage
    course: str
    cards: tuple[CardProgress, ...]
    completed_cards: int
    total_cards: int


@dataclass(frozen=True)
class LearningPath:
    """学习路径与下一张建议卡。

    Attributes:
        courses: 各课程进度。
        recommended_card: 建议学习的卡；全部完成时为 None。
        recommended_reason: 建议理由。
    """

    courses: tuple[CourseProgress, ...]
    recommended_card: KnowledgeCard | None
    recommended_reason: str


def build_learning_path(
    cards: list[KnowledgeCard],
    receipts: list[Receipt],
    mistakes: list[MistakeEntry],
) -> LearningPath:
    """按收据与未掌握错题计算卡片状态，并给出下一张建议卡。

    状态优先级：有未掌握错题记“需复习”，未完成且已开始记“学习中”，
    没做过记“未开始”，全部题有收据且无未掌握错题记“已完成”。
    建议卡按“需复习 → 学习中 → 未开始”的顺序取第一张。

    Args:
        cards: 全部知识点卡。
        receipts: 收据，用来统计已完成的题目。
        mistakes: 错题，未掌握状态会阻止卡片标记为完成。

    Returns:
        ``LearningPath``。
    """
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
