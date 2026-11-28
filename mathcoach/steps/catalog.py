"""步骤元数据目录：从 ``content/steps/*.yaml`` 读取并做结构校验。

只读加载；单条元数据校验失败时跳过并记录错误，不阻断启动。
"""
from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from ..tutor.catalog import KC_BY_ID
from .models import StepSpec

INPUT_KINDS = frozenset({"expr", "number", "sign", "order", "pair"})


class StepCatalogError(RuntimeError):
    """步骤目录缺失或结构非法。"""


@dataclass(frozen=True)
class StepCatalog:
    """步骤元数据加载结果。

    Attributes:
        specs: ``exercise_id`` -> 按 index 排序的步骤。
        errors: 被跳过的条目或文件错误，供诊断使用。
    """

    specs: Mapping[str, tuple[StepSpec, ...]]
    errors: tuple[str, ...] = ()


class _StepModel(BaseModel):
    """YAML 中一个步骤的结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int
    prompt: str
    expected: str
    variables: list[str] = []
    kc_id: str
    step_tag: str = ""
    input_kind: str = "expr"
    acceptable: list[str] = []


class _StepFile(BaseModel):
    """一个步骤 YAML 文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    exercise_id: str
    card_id: str
    steps: list[_StepModel]


def _content_root() -> Path:
    """定位 content/：打包运行时优先用 ``sys._MEIPASS``。"""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "content"
    return Path(__file__).resolve().parents[2] / "content"


DEFAULT_STEP_DIR = _content_root() / "steps"


def _read_yaml(path: Path) -> Any:
    """读取 YAML；文件或语法错误统一转成目录错误。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise StepCatalogError(f"读取步骤文件失败：{path}") from exc


def load_step_catalog(directory: Path | None = None) -> StepCatalog:
    """加载步骤目录并做结构检查。

    Args:
        directory: 步骤目录；缺省使用 ``content/steps``。

    Returns:
        ``StepCatalog``；目录缺失时返回空目录并带错误说明。
    """
    target = Path(directory) if directory is not None else DEFAULT_STEP_DIR
    if not target.is_dir():
        return StepCatalog({}, (f"未找到步骤目录：{target}",))
    files = sorted(target.glob("*.yaml"))
    if not files:
        return StepCatalog({}, (f"步骤目录为空：{target}",))

    specs: dict[str, tuple[StepSpec, ...]] = {}
    errors: list[str] = []
    for path in files:
        try:
            bundle = _StepFile.model_validate(_read_yaml(path))
        except (StepCatalogError, ValidationError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if bundle.exercise_id in specs:
            errors.append(f"{path.name}: 重复题目 {bundle.exercise_id}")
            continue
        indexes = [step.index for step in bundle.steps]
        if len(set(indexes)) != len(indexes):
            errors.append(f"{path.name}: 步骤序号重复")
            continue
        if sorted(indexes) != list(range(1, len(indexes) + 1)):
            errors.append(f"{path.name}: 步骤序号必须从 1 连续编号")
            continue
        loaded: list[StepSpec] = []
        valid = True
        for step in sorted(bundle.steps, key=lambda item: item.index):
            if not step.prompt.strip() or not step.expected.strip():
                errors.append(
                    f"{path.name}: 第 {step.index} 步缺少 prompt/expected"
                )
                valid = False
                break
            if step.input_kind not in INPUT_KINDS:
                errors.append(
                    f"{path.name}: 第 {step.index} 步 input_kind 非法"
                )
                valid = False
                break
            if step.kc_id not in KC_BY_ID:
                errors.append(
                    f"{path.name}: 第 {step.index} 步引用未知 KC "
                    f"{step.kc_id}"
                )
                valid = False
                break
            if step.input_kind in {"sign", "order", "pair"} and not (
                step.acceptable or step.expected
            ):
                errors.append(
                    f"{path.name}: 第 {step.index} 步缺少可接受答案"
                )
                valid = False
                break
            loaded.append(
                StepSpec(
                    exercise_id=bundle.exercise_id,
                    index=step.index,
                    prompt=step.prompt.strip(),
                    expected=step.expected.strip(),
                    variables=tuple(step.variables),
                    kc_id=step.kc_id,
                    step_tag=step.step_tag,
                    input_kind=step.input_kind,
                    acceptable=tuple(step.acceptable),
                )
            )
        if valid:
            specs[bundle.exercise_id] = tuple(loaded)
    return StepCatalog(specs=specs, errors=tuple(errors))


CATALOG = load_step_catalog()
STEP_SPECS = CATALOG.specs
