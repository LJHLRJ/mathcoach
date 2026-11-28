"""追问轻量判定：命中、部分命中、未命中与阈值边界。"""
import pytest

from mathcoach.tutor.dialog import SPECS, DialogOutcome, judge_follow_up


@pytest.mark.parametrize(
    ("exercise_id", "level", "answer", "expected"),
    [
        ("hs-trig-002-e1", 3, "1", DialogOutcome.HIT),
        ("hs-trig-002-e1", 3, "sin²x+cos²x=1", DialogOutcome.HIT),
        ("hs-trig-002-e1", 3, "sin²x+cos²x", DialogOutcome.PARTIAL),
        ("hs-trig-002-e1", 3, "不知道", DialogOutcome.MISS),
        ("hs-trig-002-e2", 3, "16/25", DialogOutcome.HIT),
        ("hs-trig-002-e2", 3, "0.64", DialogOutcome.HIT),
        ("hs-trig-002-e2", 3, "16", DialogOutcome.PARTIAL),
        ("hs-trig-002-e2", 3, "3/5", DialogOutcome.MISS),
        ("hs-trig-002-e2", 4, "1", DialogOutcome.HIT),
        ("hs-trig-002-e2", 4, "等于 1", DialogOutcome.HIT),
        ("hs-trig-002-e2", 4, "等于", DialogOutcome.PARTIAL),
        ("hs-trig-002-e2", 4, "16/25", DialogOutcome.MISS),
        ("hs-trig-002-e3", 3, "同角平方关系", DialogOutcome.HIT),
        ("hs-trig-002-e3", 3, "平方关系", DialogOutcome.PARTIAL),
        ("hs-trig-002-e3", 3, "平方", DialogOutcome.PARTIAL),
    ],
)
def test_judge_three_levels(
    exercise_id: str,
    level: int,
    answer: str,
    expected: DialogOutcome,
) -> None:
    """按可接受回答要点给出三档结果。"""
    spec = SPECS[(exercise_id, level)]

    assert judge_follow_up(spec, answer) is expected


def test_judge_treats_superscript_as_expression_not_answer() -> None:
    """指数 ² 不应被当成作答数字而误判命中。"""
    spec = SPECS[("hs-trig-002-e1", 3)]

    assert judge_follow_up(spec, "sin²x+cos²x") is DialogOutcome.PARTIAL


def test_judge_empty_answer_is_miss() -> None:
    """空回答直接判未命中。"""
    spec = SPECS[("hs-trig-002-e1", 3)]

    assert judge_follow_up(spec, "   ") is DialogOutcome.MISS
