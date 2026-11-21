"""题目解析与错因定位：组合现有内容与知识点树，不做判定。"""
from __future__ import annotations

from dataclasses import dataclass

from .knowledge_tree import KnowledgeTree
from .models import ErrorType, Exercise, KnowledgeCard

ERROR_REASONS = {
    ErrorType.CONCEPT: "概念或前提还没理清",
    ErrorType.FORMULA: "公式结构或适用条件记混",
    ErrorType.CALCULATION: "数值或符号计算出现偏差",
    ErrorType.READING: "题干条件或选项读漏、看反",
    ErrorType.STEP_JUMP: "解题路径不完整或跳步",
}
ERROR_SUGGESTIONS = {
    ErrorType.CONCEPT: "先补齐先修概念，再回看当前知识点的定义与学习卡片。",
    ErrorType.FORMULA: "对照公式结构与适用条件，确认没有记混。",
    ErrorType.CALCULATION: "保留草稿逐步复算，重点检查代入与符号。",
    ErrorType.READING: "重读题干，标出已知条件和所求，再匹配当前知识点。",
    ErrorType.STEP_JUMP: "把解题步骤写全，按先修顺序逐步补齐。",
}
NO_PREREQUISITE_CONCEPT = (
    "回看当前知识点的定义与学习卡片，用自己的话复述关键条件。"
)
NO_PREREQUISITE_STEP = "把解题步骤写全，避免跳步。"


@dataclass(frozen=True)
class PrerequisiteRef:
    id: str
    name: str


@dataclass(frozen=True)
class Explanation:
    knowledge_point_id: str
    knowledge_point_name: str
    course: str
    definition: str
    answer: str
    solution_outline: str
    common_mistakes: tuple[str, ...]
    prerequisites: tuple[PrerequisiteRef, ...]


@dataclass(frozen=True)
class ErrorLocalization:
    error_type: ErrorType
    reason: str
    knowledge_point_id: str
    knowledge_point_name: str
    course: str
    prerequisites: tuple[PrerequisiteRef, ...]
    review_id: str
    review_name: str
    suggestion: str


def _knowledge_point(
    card: KnowledgeCard, tree: KnowledgeTree | None
) -> tuple[str, str]:
    """优先用知识点树的名称；树缺失时回退到卡片自身。"""
    node = tree.node(card.id) if tree is not None else None
    if node is None:
        return card.name, card.course
    return node.name, card.course


def _prerequisites(
    card: KnowledgeCard,
    tree: KnowledgeTree | None,
    max_depth: int,
) -> tuple[PrerequisiteRef, ...]:
    if tree is None:
        return ()
    refs: list[PrerequisiteRef] = []
    for node_id in tree.prerequisite_chain(card.id, max_depth=max_depth):
        node = tree.node(node_id)
        if node is not None:
            refs.append(PrerequisiteRef(id=node.id, name=node.name))
    return tuple(refs)


def build_explanation(
    card: KnowledgeCard,
    exercise: Exercise,
    tree: KnowledgeTree | None = None,
    *,
    max_depth: int = 2,
) -> Explanation:
    """按题目现有字段生成解析；不调用模型，也不推断新内容。"""
    name, course = _knowledge_point(card, tree)
    return Explanation(
        knowledge_point_id=card.id,
        knowledge_point_name=name,
        course=course,
        definition=card.definition,
        answer=exercise.answer,
        solution_outline=exercise.solution_outline,
        common_mistakes=tuple(card.mistakes),
        prerequisites=_prerequisites(card, tree, max_depth),
    )


def locate_error(
    card: KnowledgeCard,
    error_type: ErrorType,
    tree: KnowledgeTree | None = None,
    *,
    reason: str = "",
    max_depth: int = 2,
) -> ErrorLocalization:
    """把已确认的错因落到知识点与先修链上，只给复习建议。"""
    name, course = _knowledge_point(card, tree)
    prerequisites = _prerequisites(card, tree, max_depth)
    review = (
        prerequisites[0]
        if prerequisites
        and error_type in (ErrorType.CONCEPT, ErrorType.STEP_JUMP)
        else PrerequisiteRef(id=card.id, name=name)
    )
    suggestion = ERROR_SUGGESTIONS[error_type]
    if not prerequisites and error_type is ErrorType.CONCEPT:
        suggestion = NO_PREREQUISITE_CONCEPT
    elif not prerequisites and error_type is ErrorType.STEP_JUMP:
        suggestion = NO_PREREQUISITE_STEP
    return ErrorLocalization(
        error_type=error_type,
        reason=reason or ERROR_REASONS[error_type],
        knowledge_point_id=card.id,
        knowledge_point_name=name,
        course=course,
        prerequisites=prerequisites,
        review_id=review.id,
        review_name=review.name,
        suggestion=suggestion,
    )
