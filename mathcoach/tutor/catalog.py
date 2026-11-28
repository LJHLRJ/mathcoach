"""KC 目录加载：从 ``content/kc/*.yaml`` 读取知识组件与教学单元。

目录数据只读；不修改现有题库 YAML、domain 模型或 BKT 表。
"""
from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from .models import KnowledgeComponent, TeachingUnit

KC_F1_ID = "kc-hs-trig-002-f1"
KC_R1_ID = "kc-hs-trig-002-r1"
KC_P1_ID = "kc-hs-trig-002-p1"


class KCCatalogError(RuntimeError):
    """KC 目录缺失、YAML 非法或引用不一致。"""


@dataclass(frozen=True)
class KCCatalog:
    """一个或多个 KC 文件的合并结果。"""

    kcs: Mapping[str, KnowledgeComponent]
    units: Mapping[str, TeachingUnit]
    exercise_kc: Mapping[str, tuple[str, ...]]


class _KCBundle(BaseModel):
    """单个 ``content/kc/*.yaml`` 文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    unit: TeachingUnit
    kcs: list[KnowledgeComponent]
    exercise_kc: dict[str, list[str]]


def _content_root() -> Path:
    """定位 content/：打包运行时优先用 ``sys._MEIPASS``。"""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "content"
    return Path(__file__).resolve().parents[2] / "content"


DEFAULT_KC_DIR = _content_root() / "kc"


def _read_yaml(path: Path) -> Any:
    """读取 YAML；文件或语法错误统一转成目录错误。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise KCCatalogError(f"读取 KC 文件失败：{path}") from exc


def load_catalog(directory: Path | None = None) -> KCCatalog:
    """加载 KC 目录并校验引用一致性。

    Args:
        directory: KC 目录；缺省使用 ``content/kc``。

    Returns:
        ``KCCatalog``。

    Raises:
        KCCatalogError: 目录不存在、没有 YAML、结构非法或引用缺失。
    """
    target = Path(directory) if directory is not None else DEFAULT_KC_DIR
    if not target.is_dir():
        raise KCCatalogError(f"未找到 KC 目录：{target}")
    files = sorted(target.glob("*.yaml"))
    if not files:
        raise KCCatalogError(f"KC 目录为空：{target}")
    kcs: dict[str, KnowledgeComponent] = {}
    units: dict[str, TeachingUnit] = {}
    exercise_kc: dict[str, tuple[str, ...]] = {}
    for path in files:
        data = _read_yaml(path)
        try:
            bundle = _KCBundle.model_validate(data)
        except ValidationError as exc:
            raise KCCatalogError(f"{path.name} 结构非法：{exc}") from exc
        for kc in bundle.kcs:
            if kc.id in kcs:
                raise KCCatalogError(f"KC ID 重复：{kc.id}")
            kcs[kc.id] = kc
        if bundle.unit.id in units:
            raise KCCatalogError(f"教学单元 ID 重复：{bundle.unit.id}")
        units[bundle.unit.id] = bundle.unit
        for exercise_id, kc_ids in bundle.exercise_kc.items():
            if exercise_id in exercise_kc:
                raise KCCatalogError(f"题目 KC 映射重复：{exercise_id}")
            exercise_kc[exercise_id] = tuple(kc_ids)
    for unit in units.values():
        missing = [
            kc_id for kc_id in unit.kc_ids if kc_id not in kcs
        ]
        if missing:
            raise KCCatalogError(
                f"教学单元 {unit.id} 引用不存在的 KC：{missing}"
            )
    for exercise_id, kc_ids in exercise_kc.items():
        missing = [kc_id for kc_id in kc_ids if kc_id not in kcs]
        if missing:
            raise KCCatalogError(
                f"题目 {exercise_id} 引用不存在的 KC：{missing}"
            )
    return KCCatalog(kcs=kcs, units=units, exercise_kc=exercise_kc)


CATALOG = load_catalog()
KC_BY_ID = CATALOG.kcs
UNIT_TRIG_002 = CATALOG.units["unit-hs-trig-002"]
EXERCISE_KC = CATALOG.exercise_kc

KC_F1 = KC_BY_ID[KC_F1_ID]
KC_R1 = KC_BY_ID[KC_R1_ID]
KC_P1 = KC_BY_ID[KC_P1_ID]
