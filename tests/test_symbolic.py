"""符号验证拒绝门：恶意表达式必须全部被拒（设计文档 §7、§9）。"""
import sys
import types
from pathlib import Path

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
    """恶意表达式全部被拒绝。"""
    for expression in MALICIOUS:
        assert validate_expression(expression, {"x"}) is not None, expression


def test_safe_expression_passes():
    """安全表达式通过校验。"""
    assert validate_expression("x**2 + sin(x) - 1/2", {"x"}) is None
    assert validate_expression("sqrt(x) + log(x, 2)", {"x"}) is None


def test_variable_whitelist_is_explicit():
    """变量白名单之外的名字被拒绝。"""
    assert validate_expression("x + 1", {"x"}) is None
    assert validate_expression("y + 1", {"x"}) is not None


def test_expr_variables_excludes_function_names():
    """变量提取排除函数名。"""
    assert expr_variables("x**2 + sin(y) + exp(z)") == {"x", "y", "z"}


def test_equivalence_verdicts():
    """等价与不等价判定正确。"""
    assert (
        are_equivalent("(x + 1)**2", "x**2 + 2*x + 1", {"x"}) is SymbolicVerdict.EQUIVALENT
    )
    assert (
        are_equivalent("x + 1", "x + 2", {"x"}) is SymbolicVerdict.NOT_EQUIVALENT
    )


def test_equivalence_rejects_malicious_input():
    """恶意输入返回拒绝状态。"""
    assert (
        are_equivalent("__import__('os')", "x", {"x"}) is SymbolicVerdict.REJECTED
    )


def test_equivalence_ignores_streamlit_fake_main(monkeypatch):
    """Streamlit 会把 app.py 装进 __main__；spawn 不应重跑整页。"""
    fake_main = types.ModuleType("__main__")
    fake_main.__file__ = str(Path(__file__).resolve().parents[1] / "app.py")
    monkeypatch.setitem(sys.modules, "__main__", fake_main)

    verdict = are_equivalent("(x + 1)**2", "x**2 + 2*x + 1", {"x"})

    assert verdict is SymbolicVerdict.EQUIVALENT


def test_equivalence_timeout_is_unverified():
    """超时返回未验证状态。"""
    verdict = are_equivalent("10**10**10", "0", {"x"}, timeout_s=0.01)
    assert verdict is SymbolicVerdict.UNVERIFIED
