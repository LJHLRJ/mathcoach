"""向量合成图：箭头、平行四边形与坐标标注。"""
from mathcoach.ui.visuals.vector_sum import build_vector_sum_figure


def _texts(figure) -> set[str]:
    return {annotation.text for annotation in figure.layout.annotations}


def test_default_sum_is_four_six() -> None:
    """默认 a=(1,2)、b=(3,4)，合向量为 (4,6)。"""
    figure = build_vector_sum_figure(1.0, 2.0, 3.0, 4.0)
    texts = _texts(figure)

    assert "a=(1, 2)" in texts
    assert "b=(3, 4)" in texts
    assert "a+b=(4, 6)" in texts


def test_parallelogram_can_be_hidden() -> None:
    """关闭辅助线时不生成平行四边形 trace。"""
    visible = build_vector_sum_figure(1.0, 2.0, 3.0, 4.0)
    hidden = build_vector_sum_figure(
        1.0, 2.0, 3.0, 4.0, show_parallelogram=False
    )

    assert any(trace.name == "平行四边形" for trace in visible.data)
    assert not any(trace.name == "平行四边形" for trace in hidden.data)


def test_negative_and_zero_vectors_do_not_raise() -> None:
    """负分量与零向量仍可渲染。"""
    figure = build_vector_sum_figure(-2.0, 0.0, 2.0, 0.0)

    assert "a+b=(0, 0)" in _texts(figure)


def test_module_does_not_import_streamlit_at_top_level() -> None:
    """可视化模块在顶层保持与 Streamlit 解耦。"""
    import mathcoach.ui.visuals.vector_sum as module

    assert "streamlit" not in module.__dict__
    assert "st" not in module.__dict__
