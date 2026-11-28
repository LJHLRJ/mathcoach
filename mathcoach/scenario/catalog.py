"""情境配置目录：从 ``content/scenario/*.yaml`` 读取参数与观察提示。

只读加载；单条配置非法时跳过并记录错误，不阻断启动。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from .models import ScenarioCatalog, ScenarioParam, ScenarioSpec

FIGURES = frozenset({"tangent_slope", "vector_sum"})
FIGURE_PARAMS = {
    "tangent_slope": frozenset({"x0"}),
    "vector_sum": frozenset({"ax", "ay", "bx", "by"}),
}


class ScenarioCatalogError(RuntimeError):
    """情境目录缺失、YAML 非法或参数不一致。"""


class _ParamModel(BaseModel):
    """YAML 中一个可调参数的结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    label: str = ""
    min: float
    max: float
    step: float = 0.1
    default: float


class _ScenarioFile(BaseModel):
    """一个情境 YAML 文件的顶层结构。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    card_id: str
    title: str
    figure: str
    params: list[_ParamModel] = []
    prompts: list[str] = []
    bridge: str = ""


def _content_root() -> Path:
    """定位 content/：打包运行时优先用 ``sys._MEIPASS``。"""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "content"
    return Path(__file__).resolve().parents[2] / "content"


DEFAULT_SCENARIO_DIR = _content_root() / "scenario"


def _read_yaml(path: Path) -> Any:
    """读取 YAML；文件或语法错误统一转成目录错误。"""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ScenarioCatalogError(
            f"读取情境文件失败：{path}（{exc}）"
        ) from exc


def _validate_param(path: Path, param: _ParamModel) -> str | None:
    """校验单个参数的范围与步长。"""
    if param.min >= param.max:
        return f"{path.name}: 参数 {param.name} 的最小值必须小于最大值"
    if param.step <= 0:
        return f"{path.name}: 参数 {param.name} 的步长必须大于 0"
    if not param.min <= param.default <= param.max:
        return f"{path.name}: 参数 {param.name} 的默认值不在范围内"
    return None


def load_scenario_catalog(
    directory: Path | None = None,
) -> ScenarioCatalog:
    """加载情境目录并校验图形、参数集合与数值范围。"""
    target = (
        Path(directory) if directory is not None else DEFAULT_SCENARIO_DIR
    )
    if not target.is_dir():
        return ScenarioCatalog({}, (f"未找到情境目录：{target}",))
    files = sorted(target.glob("*.yaml"))
    if not files:
        return ScenarioCatalog({}, (f"情境目录为空：{target}",))

    scenarios: dict[str, ScenarioSpec] = {}
    errors: list[str] = []
    for path in files:
        try:
            bundle = _ScenarioFile.model_validate(_read_yaml(path))
        except (ScenarioCatalogError, ValidationError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if bundle.card_id in scenarios:
            errors.append(f"{path.name}: 重复卡片 {bundle.card_id}")
            continue
        if bundle.figure not in FIGURES:
            errors.append(f"{path.name}: 未知图形 {bundle.figure}")
            continue
        names = {param.name for param in bundle.params}
        if names != FIGURE_PARAMS[bundle.figure]:
            errors.append(
                f"{path.name}: {bundle.figure} 需要参数 "
                f"{sorted(FIGURE_PARAMS[bundle.figure])}，实际 {sorted(names)}"
            )
            continue
        param_errors = [
            error
            for param in bundle.params
            if (error := _validate_param(path, param)) is not None
        ]
        if param_errors:
            errors.extend(param_errors)
            continue
        scenarios[bundle.card_id] = ScenarioSpec(
            card_id=bundle.card_id,
            title=bundle.title,
            figure=bundle.figure,
            params=tuple(
                ScenarioParam(
                    name=param.name,
                    label=param.label,
                    minimum=param.min,
                    maximum=param.max,
                    step=param.step,
                    default=param.default,
                )
                for param in bundle.params
            ),
            prompts=tuple(bundle.prompts),
            bridge=bundle.bridge,
        )
    return ScenarioCatalog(scenarios, tuple(errors))


CATALOG = load_scenario_catalog()
SCENARIOS = CATALOG.scenarios
