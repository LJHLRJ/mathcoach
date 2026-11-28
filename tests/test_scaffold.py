"""REMSJ 阶段映射：提示层级到认知阶段的只读展示。"""
from mathcoach.domain.scaffold import (
    STAGES,
    ScaffoldStage,
    stage_for_level,
)


def test_each_level_maps_to_stage():
    """L1–L6 全部有对应阶段。"""
    assert stage_for_level(1).key is ScaffoldStage.RESTATE
    assert stage_for_level(2).key is ScaffoldStage.EXTRACT
    assert stage_for_level(3).key is ScaffoldStage.MAP
    assert stage_for_level(4).key is ScaffoldStage.SOLVE
    assert stage_for_level(5).key is ScaffoldStage.SOLVE
    assert stage_for_level(6).key is ScaffoldStage.JUSTIFY


def test_unknown_levels_fall_back():
    """L0 及负数回退复述，超出 L6 回退说明理由。"""
    assert stage_for_level(0).key is ScaffoldStage.RESTATE
    assert stage_for_level(-1).key is ScaffoldStage.RESTATE
    assert stage_for_level(7).key is ScaffoldStage.JUSTIFY


def test_stage_metadata_is_complete():
    """五个阶段都有中文标签与说明，且覆盖 L1–L6。"""
    assert len(STAGES) == 5
    covered = {
        level for stage in STAGES for level in stage.hint_levels
    }
    assert covered == {1, 2, 3, 4, 5, 6}
    assert all(stage.label and stage.description for stage in STAGES)
