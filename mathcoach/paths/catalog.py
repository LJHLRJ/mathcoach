"""路径目录：从 ``content/paths/*.yaml`` 读取并做 verify 预检。"""
from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from ..steps.catalog import INPUT_KINDS
from ..tutor.catalog import EXERCISE_KC, KC_BY_ID
from ..verify.symbolic import SymbolicVerdict, are_equivalent
from .models import PathCheckpoint, SolutionPath

PathVerifyFn = Callable[[str, str, frozenset[str]], SymbolicVerdict]


class PathCatalogError(RuntimeError):
    """路径目录缺失或结构非法。"""


@dataclass(frozen=True)
class PathCatalog:
    """路径加载结果；``paths`` 按题目 ID 分组。"""

    paths: Mapping[str, tuple[SolutionPath, ...]]
    errors: tuple[str, ...] = ()


class _CheckpointModel(BaseModel):
    """YAML 中一个检查点的结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int
    prompt: str
    expected: str
    variables: list[str] = []
    input_kind: str = "expr"
    acceptable: list[str] = []
    verify_expected: str = ""


class _PathModel(BaseModel):
    """YAML 中一条路径的结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    summary: str
    final_answer: str
    kc_ids: list[str] = []
    verify_expression: str = ""
    verify_expected: str = ""
    variables: list[str] = []
    checkpoints: list[_CheckpointModel]


class _PathFile(BaseModel):
    """一个路径 YAML 文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    exercise_id: str
    card_id: str
    paths: list[_PathModel]


def _content_root() -> Path:
    """定位 content/：打包运行时优先用 ``sys._MEIPASS``。"""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "content"
    return Path(__file__).resolve().parents[2] / "content"


DEFAULT_PATH_DIR = _content_root() / "paths"


def default_verify(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """用 verify 检查路径数学内容；输入受控，走离线等价检查。"""
    return are_equivalent(left, right, variables, timeout_s=None)


def _read_yaml(path: Path) -> Any:
    """读取 YAML；文件或语法错误统一转成目录错误。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise PathCatalogError(f"读取路径文件失败：{path}") from exc


def _build_path(
    model: _PathModel,
    exercise_id: str,
    verify_fn: PathVerifyFn,
) -> SolutionPath | None:
    """校验单条路径；失败时返回 None 并由调用方记录错误。"""
    if not model.checkpoints:
        return None
    indexes = [item.index for item in model.checkpoints]
    if sorted(indexes) != list(range(1, len(indexes) + 1)):
        return None
    for checkpoint in model.checkpoints:
        if not checkpoint.prompt.strip() or not checkpoint.expected.strip():
            return None
        if checkpoint.input_kind not in INPUT_KINDS:
            return None
        if checkpoint.input_kind == "expr":
            if not checkpoint.verify_expected.strip():
                return None
            verdict = verify_fn(
                checkpoint.expected,
                checkpoint.verify_expected,
                frozenset(checkpoint.variables),
            )
            if verdict is not SymbolicVerdict.EQUIVALENT:
                return None
    if not model.verify_expression.strip() or not model.verify_expected.strip():
        return None
    verdict = verify_fn(
        model.verify_expression,
        model.verify_expected,
        frozenset(model.variables),
    )
    if verdict is not SymbolicVerdict.EQUIVALENT:
        return None
    return SolutionPath(
        exercise_id=exercise_id,
        path_id=model.id,
        name=model.name,
        summary=model.summary,
        checkpoints=tuple(
            PathCheckpoint(
                index=item.index,
                prompt=item.prompt,
                expected=item.expected,
                variables=tuple(item.variables),
                input_kind=item.input_kind,
                acceptable=tuple(item.acceptable),
                verify_expected=item.verify_expected,
            )
            for item in model.checkpoints
        ),
        final_answer=model.final_answer,
        kc_ids=tuple(model.kc_ids),
        verify_expression=model.verify_expression,
        verify_expected=model.verify_expected,
        variables=tuple(model.variables),
    )


def load_path_catalog(
    directory: Path | None = None,
    *,
    verify_fn: PathVerifyFn | None = None,
) -> PathCatalog:
    """加载路径目录并校验数学内容；失败条目跳过，不阻断启动。"""
    target = Path(directory) if directory is not None else DEFAULT_PATH_DIR
    if not target.is_dir():
        return PathCatalog({}, (f"未找到路径目录：{target}",))
    files = sorted(target.glob("*.yaml"))
    if not files:
        return PathCatalog({}, (f"路径目录为空：{target}",))

    verify = verify_fn or default_verify
    grouped: dict[str, list[SolutionPath]] = {}
    seen: dict[str, set[str]] = {}
    errors: list[str] = []
    for path in files:
        try:
            bundle = _PathFile.model_validate(_read_yaml(path))
        except (PathCatalogError, ValidationError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if bundle.exercise_id not in EXERCISE_KC:
            errors.append(
                f"{path.name}: 题目 {bundle.exercise_id} 没有 KC 映射"
            )
            continue
        for model in bundle.paths:
            missing = [
                kc_id for kc_id in model.kc_ids if kc_id not in KC_BY_ID
            ]
            if missing:
                errors.append(
                    f"{path.name}: {bundle.exercise_id} 引用未知 KC {missing}"
                )
                continue
            if not model.id.strip() or not model.name.strip():
                errors.append(
                    f"{path.name}: {bundle.exercise_id} 路径缺少 id/name"
                )
                continue
            if not model.final_answer.strip():
                errors.append(
                    f"{path.name}: {bundle.exercise_id} 路径 {model.id} "
                    "缺少最终答案"
                )
                continue
            if model.id in seen.setdefault(bundle.exercise_id, set()):
                errors.append(
                    f"{path.name}: 重复路径 "
                    f"{bundle.exercise_id}/{model.id}"
                )
                continue
            loaded = _build_path(model, bundle.exercise_id, verify)
            if loaded is None:
                errors.append(
                    f"{path.name}: 路径 {bundle.exercise_id}/{model.id} "
                    "结构或 verify 预检失败"
                )
                continue
            seen[bundle.exercise_id].add(model.id)
            grouped.setdefault(bundle.exercise_id, []).append(loaded)
    return PathCatalog(
        {
            exercise_id: tuple(paths)
            for exercise_id, paths in grouped.items()
        },
        tuple(errors),
    )


PATHS = load_path_catalog().paths
