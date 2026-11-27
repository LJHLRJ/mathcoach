"""知识点层级查询：只读 knowledge_tree.yaml，不改判定或内容。

节点 ID 与现有 card_id / exercise_id 对齐；先修边只复用
content/prerequisites.yaml，不在这里新增或推断。
"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_TREE_PATH = (
    Path(__file__).resolve().parents[2] / "content" / "knowledge_tree.yaml"
)
LEARNING_CARDS_DIR = (
    Path(__file__).resolve().parents[2] / "content" / "learning_cards"
)
UNMAPPED = "unmapped"


class KnowledgeTreeError(RuntimeError):
    """知识点树结构或绑定不合法。"""


@dataclass(frozen=True)
class KnowledgeNode:
    """知识点树节点。

    Attributes:
        id: 节点 ID，与卡片 ID 对齐。
        name: 名称。
        parent_id: 父节点 ID，根节点为 None。
        prerequisites: 直接先修节点 ID。
        description: 说明。
    """

    id: str
    name: str
    parent_id: str | None
    prerequisites: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class ProblemBinding:
    """题目到知识点的绑定。

    Attributes:
        exercise_id: 题目 ID。
        knowledge_point_id: 知识点 ID；未映射时为 ``unmapped``。
        problem_schema: 题目结构标识。
    """

    exercise_id: str
    knowledge_point_id: str
    problem_schema: str


@dataclass(frozen=True)
class KnowledgeTree:
    """只读知识点树与题目绑定。

    Attributes:
        nodes: 节点 ID -> 节点。
        bindings: 题目 ID -> 绑定。
    """

    nodes: Mapping[str, KnowledgeNode]
    bindings: Mapping[str, ProblemBinding]

    def node(self, node_id: str) -> KnowledgeNode | None:
        """按 ID 取节点；不存在时返回 None。"""
        return self.nodes.get(node_id)

    def children(self, node_id: str) -> tuple[KnowledgeNode, ...]:
        """返回直接子节点，按 ID 排序。"""
        return tuple(
            sorted(
                (
                    node
                    for node in self.nodes.values()
                    if node.parent_id == node_id
                ),
                key=lambda node: node.id,
            )
        )

    def prerequisite_chain(
        self, node_id: str, max_depth: int | None = None
    ) -> tuple[str, ...]:
        """按先修边 BFS 返回祖先节点。

        去重后按 BFS 顺序返回；``max_depth=1`` 只返回直接先修，
        ``max_depth=None`` 一直追到根。

        Args:
            node_id: 起点节点。
            max_depth: 最大层数；≤ 0 返回空。

        Returns:
            先修节点 ID 元组；起点不存在时为空。
        """
        if node_id not in self.nodes:
            return ()
        if max_depth is not None and max_depth <= 0:
            return ()
        seen: set[str] = set()
        queue = deque(
            (parent, 1)
            for parent in self.nodes[node_id].prerequisites
        )
        result: list[str] = []
        while queue:
            current, depth = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            result.append(current)
            if max_depth is not None and depth >= max_depth:
                continue
            for parent in self.nodes[current].prerequisites:
                if parent not in seen:
                    queue.append((parent, depth + 1))
        return tuple(result)

    def problems_for(
        self, knowledge_point_id: str
    ) -> tuple[ProblemBinding, ...]:
        """返回绑定到该知识点的题目，按题目 ID 排序。"""
        return tuple(
            sorted(
                (
                    binding
                    for binding in self.bindings.values()
                    if binding.knowledge_point_id == knowledge_point_id
                ),
                key=lambda binding: binding.exercise_id,
            )
        )

    def problem_for(self, exercise_id: str) -> ProblemBinding | None:
        """按题目 ID 取绑定；未登记时返回 None。"""
        return self.bindings.get(exercise_id)

    def unmapped_problems(self) -> tuple[ProblemBinding, ...]:
        """返回知识点为 ``unmapped`` 的绑定，按题目 ID 排序。"""
        return tuple(
            sorted(
                (
                    binding
                    for binding in self.bindings.values()
                    if binding.knowledge_point_id == UNMAPPED
                ),
                key=lambda binding: binding.exercise_id,
            )
        )


def _require_str(raw: Mapping[str, Any], key: str, context: str) -> str:
    """取必填字符串字段；缺失、空白或类型不对时抛错。"""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeTreeError(f"{context} 缺少有效字段 {key}")
    return value


def _str_list(
    raw: Mapping[str, Any], key: str, context: str
) -> tuple[str, ...]:
    """取字符串列表字段；缺省为空，元素必须是非空字符串。"""
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise KnowledgeTreeError(f"{context} 的 {key} 必须是字符串列表")
    return tuple(value)


def _parse_nodes(raw_nodes: object) -> dict[str, KnowledgeNode]:
    """解析节点并校验父节点、先修引用与两类环。"""
    if not isinstance(raw_nodes, list):
        raise KnowledgeTreeError("knowledge_tree.yaml 的 nodes 必须是列表")
    nodes: dict[str, KnowledgeNode] = {}
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            raise KnowledgeTreeError(f"nodes[{index}] 必须是字典")
        context = f"nodes[{index}]"
        node_id = _require_str(raw, "id", context)
        if node_id in nodes:
            raise KnowledgeTreeError(f"知识点 ID 重复：{node_id}")
        parent_id = raw.get("parent_id")
        if parent_id is not None and not isinstance(parent_id, str):
            raise KnowledgeTreeError(f"{node_id} 的 parent_id 必须是字符串或 null")
        nodes[node_id] = KnowledgeNode(
            id=node_id,
            name=_require_str(raw, "name", context),
            parent_id=parent_id,
            prerequisites=_str_list(raw, "prerequisites", context),
            description=_require_str(raw, "description", context),
        )
    for node in nodes.values():
        if node.parent_id is not None and node.parent_id not in nodes:
            raise KnowledgeTreeError(
                f"知识点 {node.id} 的父节点不存在：{node.parent_id}"
            )
        if node.parent_id == node.id:
            raise KnowledgeTreeError(f"知识点 {node.id} 不能以自身为父节点")
        for parent in node.prerequisites:
            if parent not in nodes:
                raise KnowledgeTreeError(
                    f"知识点 {node.id} 的先修节点不存在：{parent}"
                )
            if parent == node.id:
                raise KnowledgeTreeError(f"知识点 {node.id} 不能依赖自身")
    _ensure_acyclic(nodes)
    _ensure_parents_acyclic(nodes)
    return nodes


def _ensure_acyclic(nodes: Mapping[str, KnowledgeNode]) -> None:
    """DFS 检查先修关系是否有环；有环时带路径抛错。"""
    state: dict[str, int] = {}

    def visit(node_id: str, stack: list[str]) -> None:
        """递归访问先修边，发现回边时抛错。"""
        state[node_id] = 1
        for parent in nodes[node_id].prerequisites:
            if state.get(parent) == 1:
                cycle = " -> ".join(stack + [parent])
                raise KnowledgeTreeError(f"先修关系存在环：{cycle}")
            if state.get(parent, 0) == 0:
                visit(parent, stack + [parent])
        state[node_id] = 2

    for node_id in nodes:
        if state.get(node_id, 0) == 0:
            visit(node_id, [node_id])


def _ensure_parents_acyclic(nodes: Mapping[str, KnowledgeNode]) -> None:
    """沿 parent_id 向上检查父级链是否有环。"""
    for node_id in nodes:
        seen: set[str] = set()
        current: str | None = node_id
        while current is not None:
            if current in seen:
                raise KnowledgeTreeError(f"知识点父级存在环：{node_id}")
            seen.add(current)
            current = nodes[current].parent_id


def _parse_bindings(
    raw_bindings: object, nodes: Mapping[str, KnowledgeNode]
) -> dict[str, ProblemBinding]:
    """解析题目绑定，检查题目 ID 重复与知识点是否存在。"""
    if not isinstance(raw_bindings, list):
        raise KnowledgeTreeError("knowledge_tree.yaml 的 bindings 必须是列表")
    bindings: dict[str, ProblemBinding] = {}
    for index, raw in enumerate(raw_bindings):
        if not isinstance(raw, dict):
            raise KnowledgeTreeError(f"bindings[{index}] 必须是字典")
        context = f"bindings[{index}]"
        exercise_id = _require_str(raw, "exercise_id", context)
        if exercise_id in bindings:
            raise KnowledgeTreeError(f"题目绑定重复：{exercise_id}")
        knowledge_point_id = _require_str(
            raw, "knowledge_point_id", context
        )
        if (
            knowledge_point_id != UNMAPPED
            and knowledge_point_id not in nodes
        ):
            raise KnowledgeTreeError(
                f"题目 {exercise_id} 的知识点不存在：{knowledge_point_id}"
            )
        bindings[exercise_id] = ProblemBinding(
            exercise_id=exercise_id,
            knowledge_point_id=knowledge_point_id,
            problem_schema=_require_str(raw, "problem_schema", context),
        )
    return bindings


def load_knowledge_tree(path: Path | None = None) -> KnowledgeTree:
    """加载并校验知识点树。

    Args:
        path: 树文件路径，缺省用仓库内的 ``content/knowledge_tree.yaml``。

    Returns:
        ``KnowledgeTree``。

    Raises:
        KnowledgeTreeError: 文件缺失、YAML 非法、节点或绑定结构不合法。
    """
    target = Path(path) if path is not None else DEFAULT_TREE_PATH
    if not target.exists():
        raise KnowledgeTreeError(f"未找到知识点树：{target}")
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise KnowledgeTreeError(f"读取知识点树失败：{target}") from exc
    if not isinstance(data, dict):
        raise KnowledgeTreeError("knowledge_tree.yaml 顶层必须是字典")
    nodes = _parse_nodes(data.get("nodes"))
    bindings = _parse_bindings(data.get("bindings"), nodes)
    return KnowledgeTree(nodes=nodes, bindings=bindings)


def learning_card_path(knowledge_point_id: str) -> Path | None:
    """拼出知识点学习卡片路径。

    含路径分隔符、``.``、``..`` 或空 ID 一律返回 None，挡住路径穿越。

    Args:
        knowledge_point_id: 知识点 ID。

    Returns:
        卡片路径；ID 非法时为 None。
    """
    if (
        not knowledge_point_id
        or knowledge_point_id in {".", ".."}
        or "/" in knowledge_point_id
        or "\\" in knowledge_point_id
    ):
        return None
    return LEARNING_CARDS_DIR / f"{knowledge_point_id}.md"


def load_learning_card(knowledge_point_id: str) -> str | None:
    """读取知识点学习卡片。

    Args:
        knowledge_point_id: 知识点 ID。

    Returns:
        卡片文本；路径非法、文件缺失或读取失败时为 None。
    """
    path = learning_card_path(knowledge_point_id)
    if path is None or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def learning_card_is_filled(text: str) -> bool:
    """卡片正文含“状态：已填充”时返回 True。"""
    return "状态：已填充" in text
