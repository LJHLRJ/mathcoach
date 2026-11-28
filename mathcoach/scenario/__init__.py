"""情境化仿真入口：参数可调图、观察提示与卡片绑定。"""
from .catalog import (
    CATALOG,
    DEFAULT_SCENARIO_DIR,
    SCENARIOS,
    ScenarioCatalogError,
    load_scenario_catalog,
)
from .models import (
    ScenarioCatalog,
    ScenarioParam,
    ScenarioSpec,
    scenario_for,
)
from .render import build_scenario_figure, render_scenario

__all__ = [
    "CATALOG",
    "DEFAULT_SCENARIO_DIR",
    "SCENARIOS",
    "ScenarioCatalog",
    "ScenarioCatalogError",
    "ScenarioParam",
    "ScenarioSpec",
    "build_scenario_figure",
    "load_scenario_catalog",
    "render_scenario",
    "scenario_for",
]
