"""路径检查点：复用步骤判定与 verify。"""
from mathcoach.paths import PATHS, PathCheckpoint, check_checkpoint
from mathcoach.steps import StepVerdict


def _checkpoint(input_kind: str = "number") -> PathCheckpoint:
    """构造一个简单检查点。"""
    return PathCheckpoint(
        index=1,
        prompt="邻边是多少？",
        expected="4",
        input_kind=input_kind,
        acceptable=("4",),
    )


def test_number_checkpoint_accepts_equivalent_number() -> None:
    """数值检查点接受等值分数。"""
    verdict = check_checkpoint(_checkpoint(), "4/1")

    assert verdict is StepVerdict.CORRECT


def test_number_checkpoint_rejects_wrong_value() -> None:
    """数值检查点对错误值返回 INCORRECT。"""
    verdict = check_checkpoint(_checkpoint(), "5")

    assert verdict is StepVerdict.INCORRECT


def test_number_checkpoint_rejects_non_number() -> None:
    """纯数值检查点拒绝表达式输入。"""
    verdict = check_checkpoint(_checkpoint(), "sqrt(16)")

    assert verdict is StepVerdict.REJECTED


def test_sign_checkpoint_uses_acceptable_spellings() -> None:
    """文字检查点按可接受写法匹配。"""
    checkpoint = PathCheckpoint(
        index=1,
        prompt="斜边还是直角边？",
        expected="斜边",
        input_kind="sign",
        acceptable=("斜边", "hypotenuse"),
    )

    assert check_checkpoint(checkpoint, "斜边") is StepVerdict.CORRECT
    assert check_checkpoint(checkpoint, "直角边") is StepVerdict.INCORRECT


def test_expression_checkpoint_uses_verify() -> None:
    """表达式检查点通过 verify 判断等价。"""
    checkpoint = PathCheckpoint(
        index=1,
        prompt="写出邻边",
        expected="4",
        variables=(),
        input_kind="expr",
        verify_expected="sqrt(5**2-3**2)",
    )

    assert check_checkpoint(checkpoint, "sqrt(16)") is StepVerdict.CORRECT
    assert check_checkpoint(checkpoint, "3") is StepVerdict.INCORRECT


def test_default_catalog_checkpoints_are_answerable() -> None:
    """默认路径的第一检查点可以用学生答案通过。"""
    paths = PATHS["hs-trig-005-e2"]
    checkpoint = paths[0].checkpoints[0]

    verdict = check_checkpoint(checkpoint, "斜边")

    assert verdict is StepVerdict.CORRECT
