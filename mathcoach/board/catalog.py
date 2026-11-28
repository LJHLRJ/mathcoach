"""板书帧目录：从 ``content/board/*.yaml`` 读取并做结构校验与 verify 预检。

只读加载；单帧校验失败时跳过并记录错误，不阻断启动。
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from ..steps import STEP_SPECS
from ..tutor.catalog import KC_BY_ID
from ..verify.symbolic import SymbolicVerdict, are_equivalent
from .models import BoardCatalog, BoardFrameSpec

FIGURES = frozenset({"wave", "cosine_rule"})
FIGURE_PARAMS = {
    "wave": frozenset({"amplitude", "omega"}),
    "cosine_rule": frozenset({"a", "b", "angle_c"}),
}
HIGHLIGHTS = {
    "wave": frozenset({"", "amplitude", "omega", "period"}),
    "cosine_rule": frozenset({"", "minus", "angle", "side_c"}),
}
DIALOG_LEVELS = frozenset({3, 4})
VerifyFn = Callable[[str, str, frozenset[str]], SymbolicVerdict]


def _default_verify(
    expression: str, expected: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """仓库内静态内容在当前进程验证，避免 Windows 子进程启动开销。"""
    return are_equivalent(
        expression, expected, variables, timeout_s=None
    )


class BoardCatalogError(RuntimeError):
    """板书目录缺失、YAML 非法或引用不一致。"""


class _VerifyModel(BaseModel):
    """帧内数学声明，加载时交给 verify 预检。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expression: str
    expected: str
    variables: list[str] = []


class _FrameModel(BaseModel):
    """YAML 中一帧的结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_index: int
    title: str
    narration: str = ""
    figure: str
    params: dict[str, float] = {}
    highlight: str = ""
    kc_id: str = ""
    dialog_level: int | None = None
    verify: _VerifyModel | None = None


class _BoardFile(BaseModel):
    """一个板书 YAML 文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    exercise_id: str
    card_id: str
    frames: list[_FrameModel]


def _content_root() -> Path:
    """定位 content/：打包运行时优先用 ``sys._MEIPASS``。"""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "content"
    return Path(__file__).resolve().parents[2] / "content"


DEFAULT_BOARD_DIR = _content_root() / "board"


def _read_yaml(path: Path) -> Any:
    """读取 YAML；文件或语法错误统一转成目录错误。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise BoardCatalogError(f"读取板书文件失败：{path}") from exc


def _validate_frame(
    path: Path,
    exercise_id: str,
    frame: _FrameModel,
    step_indexes: set[int],
    seen: set[int],
    verify_fn: VerifyFn | None,
) -> BoardFrameSpec | str:
    """校验单帧；通过时返回帧模型，失败时返回错误说明。"""
    if frame.step_index not in step_indexes:
        return (
            f"{path.name}: {exercise_id} 没有第 {frame.step_index} 步"
        )
    if frame.step_index in seen:
        return f"{path.name}: {exercise_id} 第 {frame.step_index} 步重复"
    if frame.figure not in FIGURES:
        return f"{path.name}: 未知图形 {frame.figure}"
    unknown_params = set(frame.params) - FIGURE_PARAMS[frame.figure]
    if unknown_params:
        return (
            f"{path.name}: {exercise_id} 第 {frame.step_index} 步"
            f"参数不识别 {sorted(unknown_params)}"
        )
    if frame.highlight not in HIGHLIGHTS[frame.figure]:
        return (
            f"{path.name}: {exercise_id} 第 {frame.step_index} 步"
            f"高亮元素不识别 {frame.highlight}"
        )
    if frame.kc_id and frame.kc_id not in KC_BY_ID:
        return f"{path.name}: 未知 KC {frame.kc_id}"
    if (
        frame.dialog_level is not None
        and frame.dialog_level not in DIALOG_LEVELS
    ):
        return (
            f"{path.name}: {exercise_id} 第 {frame.step_index} 步"
            f"追问层级只能是 L3/L4"
        )
    verify_expression = ""
    verify_expected = ""
    verify_variables: tuple[str, ...] = ()
    if frame.verify is not None:
        if verify_fn is not None:
            verdict = verify_fn(
                frame.verify.expression,
                frame.verify.expected,
                frozenset(frame.verify.variables),
            )
            if verdict is not SymbolicVerdict.EQUIVALENT:
                return (
                    f"{path.name}: {exercise_id} 第 {frame.step_index} 步"
                    f" verify={verdict.value}"
                )
        verify_expression = frame.verify.expression
        verify_expected = frame.verify.expected
        verify_variables = tuple(frame.verify.variables)
    return BoardFrameSpec(
        exercise_id=exercise_id,
        step_index=frame.step_index,
        title=frame.title,
        narration=frame.narration,
        figure=frame.figure,
        params=dict(frame.params),
        highlight=frame.highlight,
        kc_id=frame.kc_id,
        dialog_level=frame.dialog_level,
        verify_expression=verify_expression,
        verify_expected=verify_expected,
        verify_variables=verify_variables,
    )


def load_board_catalog(
    directory: Path | None = None,
    *,
    verify_fn: VerifyFn | None = _default_verify,
) -> BoardCatalog:
    """加载板书目录并校验步骤对齐、图形参数与帧内数学声明。

    Args:
        directory: 板书目录；缺省使用 ``content/board``。
        verify_fn: 帧内数学声明预检函数；None 表示只做结构检查。

    Returns:
        ``BoardCatalog``；目录缺失时返回空目录并带错误说明。
    """
    target = Path(directory) if directory is not None else DEFAULT_BOARD_DIR
    if not target.is_dir():
        return BoardCatalog({}, (f"未找到板书目录：{target}",))
    files = sorted(target.glob("*.yaml"))
    if not files:
        return BoardCatalog({}, (f"板书目录为空：{target}",))

    frames: dict[str, list[BoardFrameSpec]] = {}
    errors: list[str] = []
    for path in files:
        try:
            bundle = _BoardFile.model_validate(_read_yaml(path))
        except (BoardCatalogError, ValidationError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        specs = STEP_SPECS.get(bundle.exercise_id)
        if not specs:
            errors.append(f"{path.name}: 未知题目 {bundle.exercise_id}")
            continue
        step_indexes = {spec.index for spec in specs}
        seen: set[int] = set()
        for frame in bundle.frames:
            result = _validate_frame(
                path,
                bundle.exercise_id,
                frame,
                step_indexes,
                seen,
                verify_fn,
            )
            if isinstance(result, str):
                errors.append(result)
                continue
            seen.add(frame.step_index)
            frames.setdefault(bundle.exercise_id, []).append(result)

    ordered = {
        exercise_id: tuple(
            sorted(value, key=lambda item: item.step_index)
        )
        for exercise_id, value in frames.items()
    }
    return BoardCatalog(ordered, tuple(errors))


CATALOG = load_board_catalog()
BOARD_FRAMES = CATALOG.frames
