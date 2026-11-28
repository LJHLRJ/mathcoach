"""情境渲染：图形构造与失败降级。"""
import pytest

from mathcoach.scenario import (
    CATALOG,
    ScenarioSpec,
    build_scenario_figure,
    render_scenario,
    scenario_for,
)


def test_tangent_scenario_builds_slope_figure() -> None:
    """斜率情境复用切线图，标题带当前斜率。"""
    spec = scenario_for(CATALOG, "hs-func-004")
    assert spec is not None
    figure = build_scenario_figure(spec, {"x0": 1.0})

    assert "切线" in figure.layout.title.text
    assert "斜率" in figure.layout.title.text


def test_vector_scenario_builds_sum_figure() -> None:
    """向量情境构造合成图。"""
    spec = scenario_for(CATALOG, "hs-vector-002")
    assert spec is not None
    figure = build_scenario_figure(
        spec, {"ax": 1.0, "ay": 2.0, "bx": 3.0, "by": 4.0}
    )
    texts = {annotation.text for annotation in figure.layout.annotations}

    assert "a+b=(4, 6)" in texts


def test_unknown_figure_raises() -> None:
    """未知图形在构建阶段报错。"""
    spec = ScenarioSpec(card_id="x", title="x", figure="unknown")
    with pytest.raises(ValueError):
        build_scenario_figure(spec, {})


def test_render_failure_is_contained(monkeypatch) -> None:
    """Streamlit 控件异常时返回 failed，不阻断讲解。"""
    import streamlit as st

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(st, "slider", boom)
    spec = ScenarioSpec(
        card_id="x",
        title="x",
        figure="tangent_slope",
    )
    assert render_scenario(spec) == "failed"
