"""情境化仿真数据结构：参数范围、观察提示与卡片绑定。"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScenarioParam:
    """一个可调参数。

    Attributes:
        name: 参数名，对应渲染器读取的键。
        label: 界面标签。
        minimum: 最小值。
        maximum: 最大值。
        step: 滑块步长。
        default: 默认值。
    """

    name: str
    label: str
    minimum: float
    maximum: float
    step: float
    default: float


@dataclass(frozen=True)
class ScenarioSpec:
    """一个卡片的情境探索配置。"""

    card_id: str
    title: str
    figure: str
    params: tuple[ScenarioParam, ...] = ()
    prompts: tuple[str, ...] = ()
    bridge: str = ""


@dataclass(frozen=True)
class ScenarioCatalog:
    """情境配置目录；``errors`` 保存被跳过的文件或条目。"""

    scenarios: Mapping[str, ScenarioSpec] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


def scenario_for(
    catalog: ScenarioCatalog, card_id: str
) -> ScenarioSpec | None:
    """按卡片返回情境配置；未登记返回 None。"""
    return catalog.scenarios.get(card_id)
