"""8 种题型判定器：每种至少正例、反例、边界。"""
from mathcoach.domain.judge import evaluate, judge
from mathcoach.domain.models import Exercise, ExerciseKind


def _exercise(kind: ExerciseKind, answer: str, **fields) -> Exercise:
    """构造判定测试用练习。"""
    return Exercise(
        id="hs-001-e1",
        card_id="hs-001",
        kind=kind,
        stem="题干",
        answer=answer,
        solution_outline="标准思路",
        **fields,
    )


def test_choice_exact_match():
    """选择题忽略空白后精确匹配。"""
    exercise = _exercise(ExerciseKind.CHOICE, "y = x²", options=("y = x²", "x = 1"))
    assert judge(exercise, "y = x²") is True
    assert judge(exercise, " y =  x² ") is True  # 仅忽略空白
    assert judge(exercise, "x = 1") is False


def test_multi_set_equality():
    """多选题按集合比较并去重。"""
    exercise = _exercise(ExerciseKind.MULTI, "A,C", options=("A", "B", "C"))
    assert judge(exercise, "C, A") is True
    assert judge(exercise, "A,C,A") is True  # 重复项按集合处理
    assert judge(exercise, "A") is False
    assert judge(exercise, "A,B,C") is False


def test_truefalse_accepts_common_literals():
    """判断题接受常见真假字面量。"""
    true_exercise = _exercise(ExerciseKind.TRUEFALSE, "True")
    false_exercise = _exercise(ExerciseKind.TRUEFALSE, "False")
    assert judge(true_exercise, "对") is True
    assert judge(true_exercise, "true") is True
    assert judge(true_exercise, "错") is False
    assert judge(false_exercise, "0") is True
    assert judge(false_exercise, "不知道") is False  # 无法解析按错答处理


def test_fill_normalized_exact_and_numeric_tolerance():
    """填空题支持规范化文本与数值容差。"""
    text_exercise = _exercise(ExerciseKind.FILL, "x ≥ 2")
    assert judge(text_exercise, "x≥2") is True
    assert judge(text_exercise, "x > 2") is False

    numeric = _exercise(ExerciseKind.FILL, "1/2")
    assert judge(numeric, "0.5") is True
    assert judge(numeric, "0.5000001") is True
    assert judge(numeric, "0.6") is False


def test_expr_uses_symbolic_equivalence():
    """表达式题用符号等价判定。"""
    exercise = _exercise(ExerciseKind.EXPR, "x**2 - 1")
    assert judge(exercise, "(x + 1)*(x - 1)") is True
    assert judge(exercise, "x**2 + 1") is False


def test_expr_rejected_input_needs_manual_check():
    """表达式含恶意输入时转人工复核。"""
    exercise = _exercise(ExerciseKind.EXPR, "x**2 - 1")
    result = evaluate(exercise, "__import__('os')")
    assert result.correct is None
    assert result.needs_manual_check is True
    assert "白名单" in result.reason


def test_expr_unknown_variable_needs_manual_check():
    """表达式含白名单外变量时转人工复核。"""
    exercise = _exercise(ExerciseKind.EXPR, "x**2 - 1")
    result = evaluate(exercise, "y**2 - 1")
    assert result.correct is None
    assert "白名单" in result.reason


def test_proof_order_allows_one_adjacent_swap():
    """证明排序允许一次相邻交换。"""
    exercise = _exercise(ExerciseKind.PROOF_ORDER, "1,2,3,4")
    assert judge(exercise, "1,2,3,4") is True
    assert judge(exercise, "1,3,2,4") is True  # 等价相邻
    assert judge(exercise, "3,1,2,4") is False
    assert judge(exercise, "1,2,3") is False


def test_find_error_exact_step():
    """找错题按步骤精确匹配。"""
    exercise = _exercise(ExerciseKind.FIND_ERROR, "3", options=("1", "2", "3"))
    assert judge(exercise, "3") is True
    assert judge(exercise, "2") is False


def test_match_requires_complete_mapping():
    """匹配题要求完整映射。"""
    exercise = _exercise(ExerciseKind.MATCH, "A=1;B=2")
    assert judge(exercise, "A:1, B:2") is True
    assert judge(exercise, "A=1") is False
    assert judge(exercise, "A=1;B=3") is False
    assert judge(exercise, "A=1;B=2;C=3") is False


def test_accepted_alternative_is_respected():
    """显式接受值参与判定。"""
    exercise = _exercise(ExerciseKind.FILL, "1/2", accepted=("0.5",))
    assert judge(exercise, "0.5") is True


def test_evaluate_returns_bool_for_regular_kinds():
    """常规题型返回布尔结果且无需人工复核。"""
    exercise = _exercise(ExerciseKind.CHOICE, "A", options=("A", "B"))
    assert evaluate(exercise, "B").correct is False
    assert evaluate(exercise, "A").needs_manual_check is False
