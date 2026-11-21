"""切线可视化：曲线 + 切线两条 trace，斜率数值验证，顶层不依赖 Streamlit。"""
import numpy as np
import pytest

from mathcoach.ui.visuals.tangent import build_tangent_figure


def test_figure_contains_curve_and_tangent():
    figure = build_tangent_figure(lambda x: x**2, x0=1.0)

    assert len(figure.data) == 2
    assert figure.data[0].name == "曲线"
    assert figure.data[1].name == "切线"

    xs = np.asarray(figure.data[1].x, dtype=float)
    ys = np.asarray(figure.data[1].y, dtype=float)
    # 数值斜率应接近 f'(1)=2
    slope = (ys[-1] - ys[0]) / (xs[-1] - xs[0])
    assert slope == pytest.approx(2.0, rel=1e-3)
    # 切线应经过 (1, 1)；网格最近点有约 0.03 的 x 偏差
    index = int(np.argmin(np.abs(xs - 1.0)))
    assert ys[index] == pytest.approx(1.0, abs=0.05)


def test_module_does_not_import_streamlit_at_top_level():
    import mathcoach.ui.visuals.tangent as tangent

    assert "streamlit" not in tangent.__dict__
    assert "st" not in tangent.__dict__
