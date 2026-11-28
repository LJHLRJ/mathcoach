"""语音口语规范化：中文数字、分数、三角函数与判定衔接。"""
from mathcoach.tutor.dialog import (
    DialogOutcome,
    FollowUpSpec,
    judge_follow_up,
)
from mathcoach.voice.normalize import normalize_spoken_math


def test_empty_text_stays_empty():
    """空输入不产生内容。"""
    assert normalize_spoken_math("") == ""
    assert normalize_spoken_math("   ") == ""


def test_chinese_number_after_equal():
    """等于/是/为/得后的中文数字转成阿拉伯数字。"""
    assert normalize_spoken_math("等于一") == "等于1"
    assert normalize_spoken_math("结果是五") == "结果是5"
    assert normalize_spoken_math("答案为十二") == "答案为12"


def test_fraction_and_pi():
    """X分之Y 转成 Y/X，派转成 π。"""
    assert normalize_spoken_math("十六分之二十五") == "25/16"
    assert normalize_spoken_math("三分之二") == "2/3"
    assert normalize_spoken_math("二分之派") == "π/2"


def test_square_and_sqrt():
    """平方口语与根号转成常见数学写法。"""
    assert normalize_spoken_math("sin平方x") == "sin^2(x)"
    assert normalize_spoken_math("x的平方") == "x^2"
    assert normalize_spoken_math("根号五") == "sqrt(5)"


def test_fillers_are_removed():
    """填充词与句末语气词被去掉。"""
    assert normalize_spoken_math("嗯，那个，结果是五吧") == "结果是5"


def test_plain_chinese_is_preserved():
    """不含数学口语的中文保持原样，避免误改题意。"""
    assert normalize_spoken_math("同角平方关系") == "同角平方关系"
    assert normalize_spoken_math("三角形") == "三角形"


def test_normalized_answer_hits_follow_up_spec():
    """语音规范化后的表达式可命中现有追问要点。"""
    spec = FollowUpSpec(
        exercise_id="hs-trig-002-e1",
        level=3,
        kc_ids=("kc-hs-trig-002-f1",),
        expression="sin(x)**2+cos(x)**2",
        expected="1",
        variables=("x",),
        acceptable=("1", "等于 1", "sin²x+cos²x=1"),
        template_prompt="同角平方关系是什么？",
        supplement_prompt="再看一次平方和关系。",
    )

    normalized = normalize_spoken_math(
        "嗯 sin平方x加cos平方x等于一"
    )

    assert judge_follow_up(spec, normalized) is DialogOutcome.HIT
