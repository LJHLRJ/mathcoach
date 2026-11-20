"""符号验证拒绝门（设计文档 §7）。

执行顺序：
1. ``ast.parse(mode="eval")``；
2. 只允许 Expression / BinOp(+ - * / **) / UnaryOp / 白名单函数 Call /
   白名单变量 Name / 有限数值常量；属性、下标、lambda、推导式、f-string、
   容器、字符串常量一律拒绝；
3. 用 sympy ``parse_expr`` 转换，``local_dict`` 只含显式变量，
   ``global_dict`` 只含安全子集且不暴露真实 builtins；
4. 二次检查 ``free_symbols``；
5. 在子进程内执行 ``simplify(a - b) == 0``，超时/异常返回 UNVERIFIED。

上层拿到 UNVERIFIED 时必须标注“需人工核对”，不得伪装成确定判分。
"""
from __future__ import annotations

import ast
import multiprocessing as mp
import sys
from enum import Enum

ALLOWED_FUNCTIONS = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "cot",
        "sec",
        "csc",
        "asin",
        "acos",
        "atan",
        "sinh",
        "cosh",
        "tanh",
        "log",
        "ln",
        "exp",
        "sqrt",
        "abs",
    }
)
_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_UNARY_OPS = (ast.UAdd, ast.USub)
DEFAULT_TIMEOUT_S = 5.0 if sys.platform == "win32" else 2.0
# Windows 只有 spawn，子进程需重新导入 sympy，冷启动明显慢于 fork


class SymbolicVerdict(str, Enum):
    EQUIVALENT = "equivalent"
    NOT_EQUIVALENT = "not_equivalent"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class _Rejected(Exception):
    """AST 不在白名单内。"""


def _check_node(node: ast.AST, variables: frozenset[str]) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise _Rejected("只允许数值常量，字符串/布尔常量被拒绝")
        if isinstance(node.value, float) and (
            node.value != node.value or node.value in (float("inf"), float("-inf"))
        ):
            raise _Rejected("数值常量必须是有限值")
        return
    if isinstance(node, ast.Name):
        if not node.id.isidentifier() or node.id not in variables:
            raise _Rejected(f"变量 {node.id!r} 不在白名单")
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _BIN_OPS):
            raise _Rejected(f"不允许的运算符 {type(node.op).__name__}")
        _check_node(node.left, variables)
        _check_node(node.right, variables)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _UNARY_OPS):
            raise _Rejected("只允许正负号")
        _check_node(node.operand, variables)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
            raise _Rejected("只允许白名单数学函数")
        if node.keywords:
            raise _Rejected("不允许关键字参数")
        if not 1 <= len(node.args) <= 2:
            raise _Rejected("函数参数数量不合法")
        for arg in node.args:
            _check_node(arg, variables)
        return
    raise _Rejected(f"不允许的语法节点 {type(node).__name__}")


def validate_expression(expression: str, variables: set[str] | frozenset[str]) -> str | None:
    """通过则返回 None；否则返回拒绝原因。"""
    if not isinstance(expression, str) or not expression.strip():
        return "表达式为空"
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        return f"无法解析：{exc.msg}"
    try:
        _check_node(tree.body, frozenset(variables))
    except _Rejected as exc:
        return str(exc)
    return None


def expr_variables(expression: str) -> set[str]:
    """从可信内容（标准答案）提取变量名，作为显式白名单。"""
    try:
        tree = ast.parse(str(expression).strip(), mode="eval")
    except SyntaxError:
        return set()
    names = {node.id for node in ast.walk(tree.body) if isinstance(node, ast.Name)}
    return names - ALLOWED_FUNCTIONS


def _safe_globals() -> dict:
    import sympy

    return {
        "__builtins__": {},  # 不暴露真实 builtins
        "Symbol": sympy.Symbol,
        "Integer": sympy.Integer,
        "Float": sympy.Float,
        "Rational": sympy.Rational,
        "sin": sympy.sin,
        "cos": sympy.cos,
        "tan": sympy.tan,
        "cot": sympy.cot,
        "sec": sympy.sec,
        "csc": sympy.csc,
        "asin": sympy.asin,
        "acos": sympy.acos,
        "atan": sympy.atan,
        "sinh": sympy.sinh,
        "cosh": sympy.cosh,
        "tanh": sympy.tanh,
        "log": sympy.log,
        "ln": sympy.log,
        "exp": sympy.exp,
        "sqrt": sympy.sqrt,
        "abs": sympy.Abs,
    }


def _parse(expression: str, variables: frozenset[str]):
    import sympy
    from sympy.parsing.sympy_parser import parse_expr

    local_dict = {name: sympy.Symbol(name) for name in variables}
    value = parse_expr(
        expression.strip(),
        local_dict=local_dict,
        global_dict=_safe_globals(),
        evaluate=True,
    )
    value = sympy.sympify(value)
    if not isinstance(value, sympy.Expr):
        return None
    if value.free_symbols - {sympy.Symbol(name) for name in variables}:
        return None
    return value


def _compute_verdict(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    import sympy

    a = _parse(left, variables)
    b = _parse(right, variables)
    if a is None or b is None:
        return SymbolicVerdict.UNVERIFIED
    try:
        difference = sympy.simplify(a - b)
    except Exception:
        return SymbolicVerdict.UNVERIFIED
    if difference.has(sympy.nan, sympy.zoo, sympy.oo, -sympy.oo):
        return SymbolicVerdict.UNVERIFIED
    return (
        SymbolicVerdict.EQUIVALENT
        if difference == 0
        else SymbolicVerdict.NOT_EQUIVALENT
    )


def _worker(connection, left: str, right: str, variables: frozenset[str]) -> None:
    try:
        verdict = _compute_verdict(left, right, variables)
    except Exception:
        verdict = SymbolicVerdict.UNVERIFIED
    try:
        connection.send(verdict.value)
    finally:
        connection.close()


def are_equivalent(
    left: str,
    right: str,
    variables: set[str] | frozenset[str],
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> SymbolicVerdict:
    """判断两个表达式是否数学等价；拒绝/超时/异常都不伪装成布尔值。"""
    scope = frozenset(variables)
    for expression in (left, right):
        if validate_expression(expression, scope) is not None:
            return SymbolicVerdict.REJECTED

    if timeout_s is None:
        try:
            return _compute_verdict(left, right, scope)
        except Exception:
            return SymbolicVerdict.UNVERIFIED

    try:
        # Python 3.14 在 POSIX 上默认 forkserver；从 stdin/嵌入式环境会失败，
        # 这里优先 fork，Windows 退化到 spawn。
        method = "fork" if "fork" in mp.get_all_start_methods() else "spawn"
        context = mp.get_context(method)
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=_worker,
            args=(child, left, right, scope),
            daemon=True,
        )
        try:
            process.start()
        except Exception:
            parent.close()
            child.close()
            return SymbolicVerdict.UNVERIFIED
        child.close()

        if parent.poll(timeout_s):
            try:
                value = parent.recv()
            except EOFError:
                value = SymbolicVerdict.UNVERIFIED.value
            finally:
                parent.close()
            try:
                process.join(timeout=0.2)
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=0.5)
            try:
                return SymbolicVerdict(value)
            except ValueError:
                return SymbolicVerdict.UNVERIFIED

        parent.close()
        process.terminate()
        process.join(timeout=0.5)
        return SymbolicVerdict.UNVERIFIED
    except Exception:
        return SymbolicVerdict.UNVERIFIED
