"""追问元数据目录：从 ``content/dialog/*.yaml`` 读取并做 verify 预检。

只读加载；单条元数据校验失败时跳过并记录错误，不阻断启动。
"""
from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from ...verify.symbolic import SymbolicVerdict, are_equivalent
from ..catalog import KC_BY_ID
from .models import FollowUpSpec

VerifyFn = Callable[[str, str, frozenset[str]], SymbolicVerdict]


class DialogCatalogError(RuntimeError):
    """追问目录缺失或结构非法。"""


@dataclass(frozen=True)
class DialogCatalog:
    """追问元数据加载结果。

    Attributes:
        specs: ``(exercise_id, level)`` -> 追问元数据。
        errors: 被跳过的条目或文件错误，供诊断使用。
    """

    specs: Mapping[tuple[str, int], FollowUpSpec]
    errors: tuple[str, ...] = ()


class _LevelModel(BaseModel):
    """YAML 中一级追问的结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: int
    kc_ids: list[str]
    expression: str
    expected: str
    variables: list[str] = []
    facts: dict[str, str] = {}
    acceptable: list[str]
    template_prompt: str
    supplement_prompt: str
    forbidden_in_prompt: list[str] = []


class _ExerciseModel(BaseModel):
    """一道题的两级追问。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    exercise_id: str
    levels: list[_LevelModel]


class _DialogFile(BaseModel):
    """一个追问 YAML 文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    unit_id: str
    card_id: str
    follow_ups: list[_ExerciseModel]


def _content_root() -> Path:
    """定位 content/：打包运行时优先用 ``sys._MEIPASS``。"""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "content"
    return Path(__file__).resolve().parents[3] / "content"


DEFAULT_DIALOG_DIR = _content_root() / "dialog"


def default_verify(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """用 verify 检查追问数学内容；输入受控，走离线等价检查。"""
    return are_equivalent(left, right, variables, timeout_s=None)


def _read_yaml(path: Path) -> Any:
    """读取 YAML；文件或语法错误统一转成目录错误。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DialogCatalogError(f"读取追问文件失败：{path}") from exc


def load_dialog_catalog(
    directory: Path | None = None,
    *,
    verify_fn: VerifyFn | None = None,
) -> DialogCatalog:
    """加载追问目录并做结构检查；可选逐条 verify 预检。

    Args:
        directory: 追问目录；缺省使用 ``content/dialog``。
        verify_fn: 传入时对每条数学内容做 verify 预检；None 只做结构检查，
            运行时由追问构建器再验证。

    Returns:
        ``DialogCatalog``；目录缺失时返回空目录并带错误说明。
    """
    target = Path(directory) if directory is not None else DEFAULT_DIALOG_DIR
    if not target.is_dir():
        return DialogCatalog({}, (f"未找到追问目录：{target}",))
    files = sorted(target.glob("*.yaml"))
    if not files:
        return DialogCatalog({}, (f"追问目录为空：{target}",))

    specs: dict[tuple[str, int], FollowUpSpec] = {}
    errors: list[str] = []
    for path in files:
        try:
            bundle = _DialogFile.model_validate(_read_yaml(path))
        except (DialogCatalogError, ValidationError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        for exercise in bundle.follow_ups:
            for level in exercise.levels:
                key = (exercise.exercise_id, level.level)
                if level.level not in (3, 4):
                    errors.append(
                        f"{path.name}: {exercise.exercise_id} "
                        f"层级 {level.level} 不是 L3/L4"
                    )
                    continue
                if not 2 <= len(level.acceptable) <= 4:
                    errors.append(
                        f"{path.name}: {exercise.exercise_id} L{level.level} "
                        "可接受回答要点必须是 2–4 条"
                    )
                    continue
                missing = [
                    kc_id for kc_id in level.kc_ids if kc_id not in KC_BY_ID
                ]
                if missing:
                    errors.append(
                        f"{path.name}: {exercise.exercise_id} L{level.level} "
                        f"引用未知 KC {missing}"
                    )
                    continue
                if verify_fn is not None:
                    verdict = verify_fn(
                        level.expression,
                        level.expected,
                        frozenset(level.variables),
                    )
                    if verdict is not SymbolicVerdict.EQUIVALENT:
                        errors.append(
                            f"{path.name}: {exercise.exercise_id} "
                            f"L{level.level} verify={verdict.value}"
                        )
                        continue
                if key in specs:
                    errors.append(
                        f"{path.name}: 重复追问 "
                        f"{exercise.exercise_id} L{level.level}"
                    )
                    continue
                specs[key] = FollowUpSpec(
                    exercise_id=exercise.exercise_id,
                    level=level.level,
                    kc_ids=tuple(level.kc_ids),
                    expression=level.expression,
                    expected=level.expected,
                    variables=tuple(level.variables),
                    facts=dict(level.facts),
                    acceptable=tuple(level.acceptable),
                    template_prompt=level.template_prompt,
                    supplement_prompt=level.supplement_prompt,
                    forbidden_in_prompt=tuple(level.forbidden_in_prompt),
                )
    return DialogCatalog(specs=specs, errors=tuple(errors))


CATALOG = load_dialog_catalog()
SPECS = CATALOG.specs
