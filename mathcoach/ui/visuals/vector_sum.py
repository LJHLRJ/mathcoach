"""向量合成可视化：两个向量、平行四边形与和向量；只渲染，不参与判定。"""
from __future__ import annotations

import plotly.graph_objects as go

DEFAULT_AX = 1.0
DEFAULT_AY = 2.0
DEFAULT_BX = 3.0
DEFAULT_BY = 4.0


def build_vector_sum_figure(
    ax: float = DEFAULT_AX,
    ay: float = DEFAULT_AY,
    bx: float = DEFAULT_BX,
    by: float = DEFAULT_BY,
    *,
    show_parallelogram: bool = True,
) -> go.Figure:
    """构造向量加法图。

    Args:
        ax: 向量 a 的 x 分量。
        ay: 向量 a 的 y 分量。
        bx: 向量 b 的 x 分量。
        by: 向量 b 的 y 分量。
        show_parallelogram: 是否显示平行四边形辅助线。

    Returns:
        含 a、b、a+b 箭头与坐标标注的 Plotly 图。
    """
    sum_x = ax + bx
    sum_y = ay + by

    figure = go.Figure()
    if show_parallelogram:
        figure.add_trace(
            go.Scatter(
                x=[0.0, ax, sum_x, bx, 0.0],
                y=[0.0, ay, sum_y, by, 0.0],
                mode="lines",
                name="平行四边形",
                line={"color": "#CBD5E1", "width": 1, "dash": "dot"},
                fill="toself",
                fillcolor="rgba(79, 139, 249, 0.06)",
                hoverinfo="skip",
            )
        )

    _add_vector(figure, 0.0, 0.0, ax, ay, f"a=({ax:g}, {ay:g})", "#4F8BF9")
    _add_vector(figure, 0.0, 0.0, bx, by, f"b=({bx:g}, {by:g})", "#7C3AED")
    _add_vector(
        figure,
        0.0,
        0.0,
        sum_x,
        sum_y,
        f"a+b=({sum_x:g}, {sum_y:g})",
        "#DC3545",
    )

    limit = max(
        abs(ax), abs(ay), abs(bx), abs(by), abs(sum_x), abs(sum_y), 1.0
    ) * 1.3
    figure.update_layout(
        title="向量合成：a + b = (a.x+b.x, a.y+b.y)",
        xaxis={
            "title": "x",
            "range": [-limit, limit],
            "zeroline": True,
            "scaleanchor": "y",
            "scaleratio": 1.0,
        },
        yaxis={"title": "y", "range": [-limit, limit], "zeroline": True},
        height=380,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        showlegend=False,
        plot_bgcolor="white",
    )
    return figure


def _add_vector(
    figure: go.Figure,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    label: str,
    color: str,
) -> None:
    """用 annotation 箭头画一个从起点指向终点的向量。"""
    figure.add_annotation(
        x=end_x,
        y=end_y,
        ax=start_x,
        ay=start_y,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text=label,
        showarrow=True,
        arrowhead=3,
        arrowsize=1.2,
        arrowwidth=3,
        arrowcolor=color,
        font={"size": 13, "color": color},
        xanchor="left",
        yanchor="bottom",
    )
