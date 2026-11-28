"""板书帧渲染：图形分派与失败降级。"""
import pytest

from mathcoach.board import (
    BoardFrameSpec,
    build_frame_figure,
    frame_for,
    CATALOG,
    render_frame,
)


def _wave_frame() -> BoardFrameSpec:
    frame = frame_for(CATALOG, "hs-trig-004-e1", 1)
    assert frame is not None
    return frame


def test_wave_frame_builds_curve() -> None:
    """振幅/周期帧复用正弦曲线图。"""
    figure = build_frame_figure(_wave_frame())
    names = {trace.name for trace in figure.data}

    assert "正弦曲线" in names


def test_cosine_frame_builds_triangle() -> None:
    """余弦定理帧构造三角形图。"""
    frame = frame_for(CATALOG, "hs-trig-005-e2", 1)
    assert frame is not None
    figure = build_frame_figure(frame)
    names = {trace.name for trace in figure.data}

    assert "三角形" in names
    assert "角 C" in names


def test_unknown_figure_raises() -> None:
    """未知图形在构建阶段报错，由渲染入口兜底。"""
    frame = BoardFrameSpec(
        exercise_id="hs-trig-004-e1",
        step_index=1,
        title="未知",
        narration="",
        figure="unknown",
    )
    with pytest.raises(ValueError):
        build_frame_figure(frame)
    assert render_frame(frame) == "failed"


def test_render_failure_is_contained(monkeypatch) -> None:
    """Streamlit 渲染异常返回 failed，不向步骤区抛出。"""
    import streamlit as st

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(st, "plotly_chart", boom)
    assert render_frame(_wave_frame()) == "failed"
