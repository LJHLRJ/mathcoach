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
    """先修节点的最小展示信息。

    Attributes:
        id: 知识点 ID。
        name: 知识点名称。
    """

    id: str
    name: str


@dataclass(frozen=True)
class Explanation:
    """一道题的解析内容，全部来自卡片与题目已有字段。

    Attributes:
        knowledge_point_id: 知识点卡 ID。
        knowledge_point_name: 知识点名称，知识点树优先。
        course: 课程名。
        definition: 定义。
        answer: 答案。
        solution_outline: 解题提纲。
        common_mistakes: 常见错误。
        prerequisites: 先修节点，按 BFS 顺序。
    """

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
    """错因落到知识点后的展示数据。

    Attributes:
        error_type: 错因类型。
        reason: 错因说明，未传入时用默认文案。
        knowledge_point_id: 当前知识点卡 ID。
        knowledge_point_name: 当前知识点名称。
        course: 课程名。
        prerequisites: 先修节点。
        review_id: 建议回看的知识点 ID；概念错和跳步错取最先修节点。
        review_name: 建议回看的知识点名称。
        suggestion: 复习建议。
    """

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
    """取知识点树上指定深度内的先修节点；没有树时返回空。"""
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
    """用卡片和题目现有字段拼出解析，不调用模型。

    Args:
        card: 知识点卡。
        exercise: 当前题目。
        tree: 知识点树，用来补名称与先修链；缺省时用卡片自身信息。
        max_depth: 先修链的 BFS 深度上限。

    Returns:
        ``Explanation``。
    """
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
    """把已确认的错因落到知识点与先修链上。

    概念错和跳步错回看最先修节点，其余错因留在当前卡；没有先修时换成
    针对性的通用建议。错因说明为空时用 ``ERROR_REASONS`` 的默认文案。

    Args:
        card: 知识点卡。
        error_type: 已确认的错因。
        tree: 知识点树，缺省时没有先修信息。
        reason: 自定义错因说明。
        max_depth: 先修链的 BFS 深度上限。

    Returns:
        ``ErrorLocalization``。
    """
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
