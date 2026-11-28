"""KC 前置关系图：只读加载、校验与查询。"""
from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .catalog import KC_BY_ID

DEFAULT_GRAPH_FILE = "kc_prerequisites.yaml"


class KCGraphError(RuntimeError):
    """KC 前置图缺失或结构非法。"""


@dataclass(frozen=True)
class KCEdge:
    """一条 KC 前置边：from 是先修，to 是后继。"""

    from_kc: str
    to_kc: str
    strength: Literal["required", "recommended"] = "required"
    source: Literal["manual", "inferred"] = "manual"
    confidence: float = 1.0


@dataclass(frozen=True)
class KCGraph:
    """按后继 KC 索引的前置图。"""

    prerequisites: Mapping[str, tuple[KCEdge, ...]]
    errors: tuple[str, ...] = ()

    def prerequisites_of(self, kc_id: str) -> tuple[KCEdge, ...]:
        """返回某 KC 的直接先修边。"""
        return self.prerequisites.get(kc_id, ())


class _EdgeModel(BaseModel):
    """YAML 中一条前置边的结构。"""

    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True
    )

    from_kc: str = Field(alias="from")
    to: str
    strength: Literal["required", "recommended"] = "required"
    source: Literal["manual", "inferred"] = "manual"
    confidence: float = 1.0


class _GraphFile(BaseModel):
    """前置图 YAML 的顶层结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    edges: list[_EdgeModel]


def _content_root() -> Path:
    """定位 content/：打包运行时优先用 ``sys._MEIPASS``。"""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "content"
    return Path(__file__).resolve().parents[2] / "content"


DEFAULT_GRAPH_PATH = _content_root() / DEFAULT_GRAPH_FILE


def _read_yaml(path: Path) -> Any:
    """读取 YAML；文件或语法错误统一转成图错误。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise KCGraphError(f"读取前置图失败：{path}") from exc


def _has_cycle(edges: list[KCEdge]) -> bool:
    """用 DFS 检查前置边是否成环。"""
    children: dict[str, list[str]] = {}
    for edge in edges:
        children.setdefault(edge.from_kc, []).append(edge.to_kc)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in children.get(node, ()):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in list(children))


def load_kc_graph(path: Path | None = None) -> KCGraph:
    """加载并校验 KC 前置图；非法边跳过，成环时返回空图。"""
    target = Path(path) if path is not None else DEFAULT_GRAPH_PATH
    if not target.is_file():
        return KCGraph({}, (f"未找到 KC 前置图：{target}",))
    try:
        data = _GraphFile.model_validate(_read_yaml(target))
    except (KCGraphError, ValidationError) as exc:
        return KCGraph({}, (f"{target.name}: {exc}",))

    edges: list[KCEdge] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for item in data.edges:
        from_kc = item.from_kc
        if from_kc not in KC_BY_ID or item.to not in KC_BY_ID:
            errors.append(
                f"{target.name}: 未知 KC {from_kc} -> {item.to}"
            )
            continue
        if from_kc == item.to:
            errors.append(f"{target.name}: 自指边 {from_kc}")
            continue
        key = (from_kc, item.to)
        if key in seen:
            errors.append(f"{target.name}: 重复边 {from_kc} -> {item.to}")
            continue
        if not 0.0 <= item.confidence <= 1.0:
            errors.append(f"{target.name}: confidence 越界 {key}")
            continue
        seen.add(key)
        edges.append(
            KCEdge(
                from_kc=from_kc,
                to_kc=item.to,
                strength=item.strength,
                source=item.source,
                confidence=item.confidence,
            )
        )
    if _has_cycle(edges):
        return KCGraph({}, (*errors, f"{target.name}: 前置关系存在环"))
    by_target: dict[str, list[KCEdge]] = {}
    for edge in edges:
        by_target.setdefault(edge.to_kc, []).append(edge)
    return KCGraph(
        {
            kc_id: tuple(sorted(items, key=lambda edge: edge.from_kc))
            for kc_id, items in by_target.items()
        },
        tuple(errors),
    )


KC_GRAPH = load_kc_graph()
