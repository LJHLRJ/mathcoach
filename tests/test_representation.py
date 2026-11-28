"""表示降级纯函数：单信号不降级，多信号降一级。"""
from mathcoach.domain.representation import (
    HINT_REQUEST_THRESHOLD,
    Representation,
    LoadSignals,
    choose_representation,
)


def test_single_signal_keeps_formula():
    """只有一类信号时不改变讲解形态。"""
    decision = choose_representation(
        Representation.FORMULA, LoadSignals(consecutive_wrong=2)
    )
    assert not decision.downgraded
    assert decision.target is Representation.FORMULA
    assert decision.reasons == ()


def test_two_signal_kinds_downgrade_to_worked_example():
    """连续错误 + 请求提示时降到具体例子。"""
    decision = choose_representation(
        Representation.FORMULA,
        LoadSignals(consecutive_wrong=2, hint_requests=1),
    )
    assert decision.downgraded
    assert decision.target is Representation.WORKED_EXAMPLE
    assert "连续错误=2" in decision.reasons
    assert any("提示请求" in reason for reason in decision.reasons)


def test_dialog_miss_and_elapsed_downgrade():
    """追问未命中与耗时异常组合也触发降级。"""
    decision = choose_representation(
        Representation.FORMULA,
        LoadSignals(dialog_misses=1, elapsed_ratio=1.8),
    )
    assert decision.target is Representation.WORKED_EXAMPLE


def test_abandoned_downgrades_immediately():
    """放弃属于硬信号，单条即可降级。"""
    decision = choose_representation(
        Representation.FORMULA, LoadSignals(abandoned=True)
    )
    assert decision.downgraded
    assert decision.target is Representation.WORKED_EXAMPLE


def test_two_missing_steps_downgrade():
    """连续缺失两步属于硬信号。"""
    decision = choose_representation(
        Representation.FORMULA, LoadSignals(missing_steps=2)
    )
    assert decision.downgraded


def test_one_missing_step_is_only_soft_signal():
    """单步缺失需要与其他信号组合才降级。"""
    single = choose_representation(
        Representation.FORMULA, LoadSignals(missing_steps=1)
    )
    combined = choose_representation(
        Representation.FORMULA,
        LoadSignals(consecutive_wrong=2, missing_steps=1),
    )
    assert not single.downgraded
    assert combined.downgraded


def test_visual_allowed_moves_to_concrete_visual():
    """已在使用具体例子且允许配图时，再降一级到图形。"""
    decision = choose_representation(
        Representation.WORKED_EXAMPLE,
        LoadSignals(consecutive_wrong=2, dialog_misses=1),
        allow_visual=True,
    )
    assert decision.target is Representation.CONCRETE_VISUAL


def test_visual_disabled_stops_at_worked_example():
    """没有配图能力时停在具体例子，不产生不可用形态。"""
    decision = choose_representation(
        Representation.WORKED_EXAMPLE,
        LoadSignals(consecutive_wrong=2, dialog_misses=1),
        allow_visual=False,
    )
    assert not decision.downgraded
    assert decision.target is Representation.WORKED_EXAMPLE


def test_hint_threshold_constant_matches_rule():
    """提示请求阈值是软信号门槛，保持 1 次。"""
    assert HINT_REQUEST_THRESHOLD == 1
