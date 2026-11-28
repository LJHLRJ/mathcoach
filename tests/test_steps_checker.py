"""单步判定：表达式、数值、符号、顺序、配对与 verify 降级。"""
from mathcoach.steps import StepSpec, StepVerdict, check_step
from mathcoach.verify.symbolic import SymbolicVerdict


def _spec(**overrides) -> StepSpec:
    """构造一个默认为表达式步骤的规格。"""
    data = {
        "exercise_id": "hs-trig-002-e2",
        "index": 1,
        "prompt": "测试",
        "expected": "16/25",
        "kc_id": "kc-hs-trig-002-f1",
        "input_kind": "expr",
    }
    data.update(overrides)
    return StepSpec(**data)


def test_expression_correct_and_incorrect() -> None:
    """表达式步骤按等价判定。"""
    spec = _spec()

    assert check_step(spec, "16/25") is StepVerdict.CORRECT
    assert check_step(spec, "9/25") is StepVerdict.INCORRECT


def test_expression_rejects_unsafe_input() -> None:
    """白名单拒绝的输入直接判 REJECTED。"""
    assert check_step(_spec(), "__import__('os')") is StepVerdict.REJECTED


def test_expression_unverified_is_not_wrong() -> None:
    """verify 无法确认时记 UNVERIFIABLE，而不是判错。"""
    spec = _spec()

    verdict = check_step(
        spec,
        "16/25",
        verify_fn=lambda left, right, variables: SymbolicVerdict.UNVERIFIED,
    )

    assert verdict is StepVerdict.UNVERIFIABLE


def test_number_accepts_equivalent_decimal() -> None:
    """数值步骤接受等值小数，拒绝未算完的中间值。"""
    spec = _spec(input_kind="number", expected="16/25")

    assert check_step(spec, "0.64") is StepVerdict.CORRECT
    assert check_step(spec, "16") is StepVerdict.INCORRECT
    assert check_step(spec, "abc") is StepVerdict.REJECTED


def test_sign_matches_acceptable_variants() -> None:
    """符号步骤按可接受写法匹配。"""
    spec = _spec(
        input_kind="sign",
        expected="正",
        acceptable=("正", "+", "取正"),
    )

    assert check_step(spec, "取正") is StepVerdict.CORRECT
    assert check_step(spec, "负") is StepVerdict.INCORRECT


def test_order_and_pair() -> None:
    """顺序与配对步骤做确定性完全比较。"""
    order = _spec(input_kind="order", expected="1,2,3")
    pair = _spec(input_kind="pair", expected="A=1;B=2")

    assert check_step(order, "1,2,3") is StepVerdict.CORRECT
    assert check_step(order, "1,3,2") is StepVerdict.INCORRECT
    assert check_step(order, "a,b") is StepVerdict.REJECTED
    assert check_step(pair, "A=1;B=2") is StepVerdict.CORRECT
    assert check_step(pair, "A=1;B=3") is StepVerdict.INCORRECT


def test_empty_answer_is_incorrect() -> None:
    """空输入不算对。"""
    assert check_step(_spec(), "   ") is StepVerdict.INCORRECT
