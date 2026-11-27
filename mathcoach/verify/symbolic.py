"""符号验证拒绝门（设计文档 §7）。

执行顺序：
1. ``ast.parse(mode="eval")``；
2. 只允许 Expression / BinOp(+ - * / **) / UnaryOp / 白名单函数 Call /
   白名单变量 Name / 有限数值常量；属性、下标、lambda、推导式、f-string、
   容器、字符串常量一律拒绝；
3. 用 sympy ``parse_expr`` 转换，``local_dict`` 只含显式变量，
   ``global_dict`` 只含安全子集且不暴露真实 builtins；
4. 二次检查 ``free_symbols``；
5. 在子进程内执行 ``simplify(a - b) == 0``，超时/异常返回 UNVERIFIED；
   显式传 ``timeout_s=None`` 时在当前进程计算，用于已知可控的离线场景。

上层拿到 UNVERIFIED 时必须标注“需人工核对”，不得伪装成确定判分。
"""
from __future__ import annotations

import ast
import multiprocessing as mp
import sys
from enum import Enum
from multiprocessing.connection import Connection
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sympy

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
DEFAULT_TIMEOUT_S = 20.0 if sys.platform == "win32" else 2.0
# Windows 只有 spawn，子进程需重新导入 sympy；在 Streamlit/AppTest 已加载的父进程中，
# 实测单次验证约 8 秒（2026-11，Python 3.14 + Windows），5 秒会稳定误报 UNVERIFIED。
# 上限仍需保留，避免病态表达式无限占用子进程。


class SymbolicVerdict(str, Enum):
    """符号比较的四种结论；“不等”和“无法确认”必须分开处理。"""

    EQUIVALENT = "equivalent"          # 差值化简为 0
    NOT_EQUIVALENT = "not_equivalent"  # 差值化简后不为 0
    UNVERIFIED = "unverified"          # 超时、解析失败或结果含 nan/oo，需人工核对
    REJECTED = "rejected"              # 输入未通过 AST 白名单


class _Rejected(Exception):
    """AST 不在白名单内。"""


def _check_node(node: ast.AST, variables: frozenset[str]) -> None:
    """递归检查一个 AST 节点是否落在白名单内。

    只放行数值常量、白名单变量、``+ - * / **``、正负号与白名单数学函数；
    其余节点一律抛 ``_Rejected``。变量名必须既是合法标识符又在 ``variables`` 中。
    """
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
    """检查表达式是否只使用白名单语法，返回拒绝原因或 None。

    空串、语法错误、变量不在 ``variables``、函数不在 ``ALLOWED_FUNCTIONS``、
    关键字参数，以及属性、下标、lambda、推导式、容器、字符串常量都会被拒绝。
    只做静态检查，不执行表达式，也不判断数学等价。

    Args:
        expression: 待检查的表达式文本。
        variables: 允许出现的变量名；通常由标准答案经 ``expr_variables`` 提取。

    Returns:
        通过时返回 ``None``；否则返回一句可直接展示的中文原因。
    """
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
    """从可信来源（标准答案）提取变量名，供白名单使用。

    只收集 ``ast.Name`` 节点并剔除函数名；语法错误时返回空集合。
    只能用于标准答案或 accepted，不能拿学生的原始输入放宽白名单。

    Args:
        expression: 标准答案或被接受答案的表达式文本。

    Returns:
        变量名集合；解析失败时为空集。
    """
    try:
        tree = ast.parse(str(expression).strip(), mode="eval")
    except SyntaxError:
        return set()
    names = {node.id for node in ast.walk(tree.body) if isinstance(node, ast.Name)}
    return names - ALLOWED_FUNCTIONS


def _safe_globals() -> dict:
    """构造 sympy 的全局命名空间。

    只放白名单数学函数与符号构造器，``__builtins__`` 置空，
    避免 ``parse_expr`` 通过表达式访问导入、文件或系统能力。
    """
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


def _parse(expression: str, variables: frozenset[str]) -> sympy.Expr | None:
    """把表达式转成 sympy 对象；无法转换时返回 None。

    ``local_dict`` 只含 ``variables`` 中的符号，转换后再检查一次 ``free_symbols``，
    防止解析器自动引入额外符号。

    Args:
        expression: 已通过 ``validate_expression`` 的表达式文本。
        variables: 允许的自由变量集合。

    Returns:
        ``sympy.Expr``，或无法安全转换时的 ``None``。
    """
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
    """化简 ``left - right`` 并给出结论，无法可靠化简时返回 UNVERIFIED。

    差值为 0 才算 EQUIVALENT；``nan``、``zoo``、``±oo`` 视为不可确认，
    不能当成“不相等”。这里不重复做 AST 检查，使用前必须已过白名单。

    Args:
        left: 待比较表达式。
        right: 参照表达式。
        variables: 允许的自由变量集合。

    Returns:
        ``EQUIVALENT``、``NOT_EQUIVALENT`` 或 ``UNVERIFIED``。
    """
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


def _worker(
    connection: Connection,
    left: str,
    right: str,
    variables: frozenset[str],
) -> None:
    """子进程入口：计算结论并通过管道回传字符串。

    任何异常都降级为 UNVERIFIED，保证父进程在超时前总能收到一个结论；
    管道写入失败也不重试。
    """
    try:
        verdict = _compute_verdict(left, right, variables)
    except Exception:
        verdict = SymbolicVerdict.UNVERIFIED
    try:
        connection.send(verdict.value)
    finally:
        connection.close()


def _start_process(process: mp.Process) -> None:
    """启动子进程，并避免 Windows spawn 重跑宿主主脚本。

    Windows 只有 spawn，子进程会按 ``sys.modules["__main__"].__file__`` 重新
    执行主脚本。Streamlit 会把 ``app.py`` 装进 ``__main__``，于是子进程跑整页
    UI 而不是 ``_worker``，还在 ``session_state`` 缺失处退出，管道不关闭。
    启动期间临时隐藏 ``__file__``，子进程只导入 worker 所在模块；prep data 在
    ``start()`` 内同步采集，返回后立即恢复。

    Args:
        process: 已构造、尚未启动的 ``mp.Process``。
    """
    main = sys.modules.get("__main__")
    if main is None or "__file__" not in main.__dict__:
        process.start()
        return
    script_path = main.__dict__.pop("__file__")
    try:
        process.start()
    finally:
        main.__dict__["__file__"] = script_path


def are_equivalent(
    left: str,
    right: str,
    variables: set[str] | frozenset[str],
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> SymbolicVerdict:
    """判断两个表达式是否数学等价，无法确认时返回 UNVERIFIED。

    先对两侧做白名单检查，任一不通过即 REJECTED；随后在子进程中化简
    ``left - right``，超时、解析失败或异常都返回 UNVERIFIED。

    Args:
        left: 学生作答的表达式。
        right: 标准答案或被接受答案。
        variables: 允许的自由变量集合，通常来自标准答案。
        timeout_s: 子进程等待上限（秒）。传 ``None`` 就在当前进程计算，
            不设超时，只用于已知可控的离线场景。

    Returns:
        ``EQUIVALENT``、``NOT_EQUIVALENT``、``UNVERIFIED`` 或 ``REJECTED``。

    Note:
        返回值不是布尔值：UNVERIFIED 与 REJECTED 必须由上层标注“需人工核对”，
        不能当成答错。Windows 走 spawn，子进程要重新导入 sympy，超时上限因此
        设为 20 秒；POSIX 优先 fork，默认 2 秒。
    """
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
            _start_process(process)
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
