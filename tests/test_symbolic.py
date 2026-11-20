"""符号验证拒绝门：恶意表达式必须全部被拒（设计文档 §7、§9）。"""
from mathcoach.verify.symbolic import (
    SymbolicVerdict,
    are_equivalent,
    expr_variables,
    validate_expression,
)

MALICIOUS = [
    "__import__('os')",
    "open('/etc/passwd')",
    "[Symbol('x')]",
    "Symbol(('x',))",
    "x.__class__",
    "x[0]",
    "lambda: 1",
    "f'{x}'",
    "'abc'",
    "x if x else 0",
    "x and y",
    "not x",
    "{'x': 1}",
    "(x, 1)",
]


def test_malicious_expressions_are_rejected():
    for expression in MALICIOUS:
        assert validate_expression(expression, {"x"}) is not None, expression


def test_safe_expression_passes():
    assert validate_expression("x**2 + sin(x) - 1/2", {"x"}) is None
    assert validate_expression("sqrt(x) + log(x, 2)", {"x"}) is None


def test_variable_whitelist_is_explicit():
    assert validate_expression("x + 1", {"x"}) is None
    assert validate_expression("y + 1", {"x"}) is not None


def test_expr_variables_excludes_function_names():
    assert expr_variables("x**2 + sin(y) + exp(z)") == {"x", "y", "z"}


def test_equivalence_verdicts():
    assert (
        are_equivalent("(x + 1)**2", "x**2 + 2*x + 1", {"x"}) is SymbolicVerdict.EQUIVALENT
    )
    assert (
        are_equivalent("x + 1", "x + 2", {"x"}) is SymbolicVerdict.NOT_EQUIVALENT
    )


def test_equivalence_rejects_malicious_input():
    assert (
        are_equivalent("__import__('os')", "x", {"x"}) is SymbolicVerdict.REJECTED
    )


def test_equivalence_timeout_is_unverified():
    verdict = are_equivalent("10**10**10", "0", {"x"}, timeout_s=0.01)
    assert verdict is SymbolicVerdict.UNVERIFIED
