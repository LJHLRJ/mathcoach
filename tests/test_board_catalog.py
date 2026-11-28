"""板书目录：步骤对齐、图形参数与 verify 预检。"""
from pathlib import Path

from mathcoach.board import (
    BOARD_FRAMES,
    CATALOG,
    frame_for,
    frames_for,
    load_board_catalog,
)
from mathcoach.verify.symbolic import SymbolicVerdict

CONTENT_DIR = Path(__file__).resolve().parents[1] / "content"


def test_default_catalog_loads_all_frames():
    """仓库自带四道题共八帧，且没有结构错误。"""
    assert CATALOG.errors == ()
    assert set(BOARD_FRAMES) == {
        "hs-trig-004-e1",
        "hs-trig-004-e2",
        "hs-trig-005-e1",
        "hs-trig-005-e2",
    }
    assert len(frames_for(CATALOG, "hs-trig-004-e1")) == 2
    frame = frame_for(CATALOG, "hs-trig-004-e1", 1)
    assert frame is not None
    assert frame.figure == "wave"
    assert frame.dialog_level == 3


def test_frames_are_sorted_by_step():
    """同一题的帧按步骤序号排序。"""
    indexes = [
        frame.step_index
        for frame in frames_for(CATALOG, "hs-trig-005-e2")
    ]
    assert indexes == [1, 2]


def test_misaligned_step_is_skipped(tmp_path):
    """步骤序号不在步骤元数据中时跳过并记录。"""
    directory = tmp_path / "board"
    directory.mkdir()
    (directory / "bad.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "exercise_id: hs-trig-004-e1",
                "card_id: hs-trig-004",
                "frames:",
                "  - step_index: 9",
                "    title: 越界",
                "    figure: wave",
            ]
        ),
        encoding="utf-8",
    )

    catalog = load_board_catalog(directory, verify_fn=None)
    assert catalog.frames == {}
    assert any("没有第 9 步" in error for error in catalog.errors)


def test_unknown_figure_and_params_are_rejected(tmp_path):
    """未知图形与拼错参数不会进入目录。"""
    directory = tmp_path / "board"
    directory.mkdir()
    (directory / "bad.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "exercise_id: hs-trig-004-e1",
                "card_id: hs-trig-004",
                "frames:",
                "  - step_index: 1",
                "    title: 图形不存在",
                "    figure: unknown",
                "  - step_index: 2",
                "    title: 参数拼错",
                "    figure: wave",
                "    params: {amplitud: 2}",
            ]
        ),
        encoding="utf-8",
    )

    catalog = load_board_catalog(directory, verify_fn=None)
    assert catalog.frames == {}
    assert any("未知图形" in error for error in catalog.errors)
    assert any("参数不识别" in error for error in catalog.errors)


def test_verify_rejection_skips_frame(tmp_path):
    """帧内数学声明未通过 verify 时不渲染。"""
    directory = tmp_path / "board"
    directory.mkdir()
    (directory / "bad.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "exercise_id: hs-trig-004-e1",
                "card_id: hs-trig-004",
                "frames:",
                "  - step_index: 1",
                "    title: 验证失败",
                "    figure: wave",
                "    params: {amplitude: 1, omega: 2}",
                "    verify:",
                '      expression: "1"',
                '      expected: "2"',
            ]
        ),
        encoding="utf-8",
    )

    catalog = load_board_catalog(
        directory, verify_fn=lambda *args: SymbolicVerdict.NOT_EQUIVALENT
    )
    assert catalog.frames == {}
    assert any("verify=not_equivalent" in error for error in catalog.errors)


def test_valid_frame_loads_with_fake_verify(tmp_path):
    """结构正确且 verify 通过时帧可加载。"""
    directory = tmp_path / "board"
    directory.mkdir()
    (directory / "ok.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "exercise_id: hs-trig-004-e1",
                "card_id: hs-trig-004",
                "frames:",
                "  - step_index: 1",
                "    title: 测试帧",
                "    narration: 说明",
                "    figure: wave",
                "    params: {amplitude: 2, omega: 1}",
                "    highlight: amplitude",
                "    kc_id: kc-hs-trig-004-f1",
                "    dialog_level: 3",
                "    verify:",
                '      expression: "2/2"',
                '      expected: "1"',
            ]
        ),
        encoding="utf-8",
    )

    catalog = load_board_catalog(
        directory, verify_fn=lambda *args: SymbolicVerdict.EQUIVALENT
    )
    assert catalog.errors == ()
    frame = frame_for(catalog, "hs-trig-004-e1", 1)
    assert frame is not None
    assert frame.params["amplitude"] == 2.0
    assert frame.verify_expression == "2/2"
