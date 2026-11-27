"""年级/难度元数据索引：只读 content/，不参与判定或调度。"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content"
DEFAULT_TREE_PATH = DEFAULT_CONTENT_ROOT / "knowledge_tree.yaml"
STAGE_DIRS = ("highschool", "undergraduate", "graduate")

K12_GRADES = tuple(f"g{index}" for index in range(1, 13))
UNDERGRADUATE_GRADES = tuple(f"u{index}" for index in range(1, 5))
GRADUATE_GRADES = tuple(f"m{index}" for index in range(1, 4))
GRADE_VALUES = K12_GRADES + UNDERGRADUATE_GRADES + GRADUATE_GRADES + (
    "mixed",
)
DIFFICULTY_VALUES = ("basic", "intermediate", "advanced", "challenge")
UNCLASSIFIED = "unclassified"
VALID_GRADES = frozenset(GRADE_VALUES) | {UNCLASSIFIED}
VALID_DIFFICULTIES = frozenset(DIFFICULTY_VALUES) | {UNCLASSIFIED}


class GradeIndexError(RuntimeError):
    """元数据缺失、重复或结构非法。"""


@dataclass(frozen=True)
class GradeRecord:
    """一道题的年级与难度。

    Attributes:
        exercise_id: 题目 ID。
        card_id: 所属知识点卡 ID。
        grade: 年级代码，非法值记 unclassified。
        difficulty: 难度代码，非法值记 unclassified。
    """

    exercise_id: str
    card_id: str
    grade: str
    difficulty: str


@dataclass(frozen=True)
class GradeIndex:
    """题目级索引，按题目 ID 存记录。

    Attributes:
        records: 题目 ID -> 记录。
    """

    records: Mapping[str, GradeRecord]

    def by_grade(self, grade: str) -> tuple[GradeRecord, ...]:
        """按年级筛选，按题目 ID 排序。"""
        return tuple(
            sorted(
                (
                    record
                    for record in self.records.values()
                    if record.grade == grade
                ),
                key=lambda record: record.exercise_id,
            )
        )

    def by_difficulty(
        self, difficulty: str
    ) -> tuple[GradeRecord, ...]:
        """按难度筛选，按题目 ID 排序。"""
        return tuple(
            sorted(
                (
                    record
                    for record in self.records.values()
                    if record.difficulty == difficulty
                ),
                key=lambda record: record.exercise_id,
            )
        )

    def filter(
        self,
        grade: str | None = None,
        difficulty: str | None = None,
    ) -> tuple[GradeRecord, ...]:
        """按年级和难度筛选；参数为 None 表示不限制。"""
        records: Iterable[GradeRecord] = self.records.values()
        if grade is not None:
            records = [record for record in records if record.grade == grade]
        if difficulty is not None:
            records = [
                record
                for record in records
                if record.difficulty == difficulty
            ]
        return tuple(
            sorted(records, key=lambda record: record.exercise_id)
        )

    def card_ids(
        self,
        grade: str | None = None,
        difficulty: str | None = None,
    ) -> tuple[str, ...]:
        """返回筛选结果里的卡 ID，按首次出现去重。"""
        return tuple(
            dict.fromkeys(
                record.card_id
                for record in self.filter(grade, difficulty)
            )
        )

    def grade_counts(self) -> dict[str, int]:
        """统计各年级题目数并补 0；``unclassified`` 单独一档。"""
        counts = {value: 0 for value in GRADE_VALUES}
        counts[UNCLASSIFIED] = 0
        for record in self.records.values():
            counts[record.grade] = counts.get(record.grade, 0) + 1
        return counts

    def difficulty_counts(self) -> dict[str, int]:
        """统计各难度题目数并补 0；``unclassified`` 单独一档。"""
        counts = {value: 0 for value in DIFFICULTY_VALUES}
        counts[UNCLASSIFIED] = 0
        for record in self.records.values():
            counts[record.difficulty] = (
                counts.get(record.difficulty, 0) + 1
            )
        return counts


def _normalize(value: object, valid: frozenset[str]) -> str:
    """合法值原样返回，其余统一记 unclassified。"""
    if isinstance(value, str) and value in valid:
        return value
    return UNCLASSIFIED


def build_grade_index(
    cards: Iterable[Mapping[str, Any]],
) -> GradeIndex:
    """从原始卡片字典建立题目级索引。

    Args:
        cards: 卡片字典，每张卡带 ``id`` 和 ``exercises``。

    Returns:
        以题目 ID 为键的 ``GradeIndex``。

    Raises:
        GradeIndexError: 卡片或题目缺 id、题目不是字典、题目 ID 重复。
    """
    records: dict[str, GradeRecord] = {}
    for card in cards:
        card_id = str(card.get("id") or "").strip()
        if not card_id:
            raise GradeIndexError("卡片缺少 id，无法建立年级索引")
        for exercise in card.get("exercises") or []:
            if not isinstance(exercise, Mapping):
                raise GradeIndexError(
                    f"卡片 {card_id} 的题目必须是字典"
                )
            exercise_id = str(exercise.get("id") or "").strip()
            if not exercise_id:
                raise GradeIndexError(
                    f"卡片 {card_id} 存在缺少 id 的题目"
                )
            if exercise_id in records:
                raise GradeIndexError(
                    f"题目 ID 重复：{exercise_id}"
                )
            records[exercise_id] = GradeRecord(
                exercise_id=exercise_id,
                card_id=card_id,
                grade=_normalize(exercise.get("grade"), VALID_GRADES),
                difficulty=_normalize(
                    exercise.get("difficulty"), VALID_DIFFICULTIES
                ),
            )
    return GradeIndex(records=records)


def _iter_card_dicts(root: Path) -> Iterable[Mapping[str, Any]]:
    """遍历三个学段目录下的一层 YAML，逐个产出卡片字典。

    单个文件可以是卡片列表，也可以是单张卡片字典；读取或解析失败直接抛错。
    """
    for stage in STAGE_DIRS:
        for path in sorted((root / stage).glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
                raise GradeIndexError(
                    f"读取题目元数据失败：{path}"
                ) from exc
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, Mapping):
                        yield item
            elif isinstance(data, Mapping):
                yield data


def load_grade_index(root: Path | None = None) -> GradeIndex:
    """读取全部学段卡片并建立题目级索引。

    Args:
        root: 内容根目录，缺省用仓库的 ``content/``。

    Returns:
        ``GradeIndex``。

    Raises:
        GradeIndexError: YAML 读取失败或卡片结构非法。
    """
    target = Path(root) if root is not None else DEFAULT_CONTENT_ROOT
    return build_grade_index(_iter_card_dicts(target))


def load_grade_spans(
    tree_path: Path | None = None,
) -> dict[str, tuple[str, ...]]:
    """读取知识点树的 grade_span。

    ``grade_span`` 可以是字符串或列表；缺失记 ``("unclassified",)``，
    空列表同样回落 ``unclassified``。

    Args:
        tree_path: ``knowledge_tree.yaml`` 路径，缺省用仓库内的文件。

    Returns:
        知识点 ID -> 年级元组。

    Raises:
        GradeIndexError: 文件缺失、YAML 非法、节点结构或年级值不合法。
    """
    target = (
        Path(tree_path) if tree_path is not None else DEFAULT_TREE_PATH
    )
    if not target.exists():
        raise GradeIndexError(f"未找到知识点树：{target}")
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise GradeIndexError(f"读取知识点树失败：{target}") from exc
    if not isinstance(data, Mapping):
        raise GradeIndexError("knowledge_tree.yaml 顶层必须是字典")
    spans: dict[str, tuple[str, ...]] = {}
    for node in data.get("nodes") or []:
        if not isinstance(node, Mapping):
            raise GradeIndexError("知识点节点必须是字典")
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            raise GradeIndexError("知识点节点缺少 id")
        raw = node.get("grade_span")
        if raw is None:
            spans[node_id] = (UNCLASSIFIED,)
            continue
        if isinstance(raw, str):
            values = (raw,)
        elif isinstance(raw, list):
            values = tuple(raw)
        else:
            raise GradeIndexError(
                f"知识点 {node_id} 的 grade_span 必须是字符串或列表"
            )
        invalid = [
            value
            for value in values
            if not isinstance(value, str) or value not in VALID_GRADES
        ]
        if invalid:
            raise GradeIndexError(
                f"知识点 {node_id} 的 grade_span 非法：{invalid}"
            )
        spans[node_id] = tuple(values) or (UNCLASSIFIED,)
    return spans


def node_ids_for_grade(
    spans: Mapping[str, tuple[str, ...]], grade: str
) -> tuple[str, ...]:
    """返回 grade_span 包含指定年级的节点 ID，按 ID 排序。

    Args:
        spans: ``load_grade_spans`` 的结果。
        grade: 年级代码。

    Returns:
        匹配的节点 ID 元组。
    """
    return tuple(
        sorted(
            node_id
            for node_id, values in spans.items()
            if grade in values
        )
    )
