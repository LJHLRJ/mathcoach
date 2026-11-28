"""路径目录：默认内容、verify 预检与错误跳过。"""
from pathlib import Path

from mathcoach.paths import load_path_catalog
from mathcoach.verify.symbolic import SymbolicVerdict

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def _yaml(path_id: str = "alt", *, expected: str = "5") -> str:
    """构造一条最小路径 YAML。"""
    return f"""version: 1
exercise_id: hs-trig-005-e2
card_id: hs-trig-005
paths:
  - id: {path_id}
    name: 直角三角形法
    summary: 用勾股定理。
    final_answer: "5"
    kc_ids: [kc-hs-trig-005-f1]
    verify_expression: "sqrt(3**2+4**2)"
    verify_expected: "{expected}"
    variables: []
    checkpoints:
      - index: 1
        prompt: "斜边是多少？"
        expected: "5"
        input_kind: number
        acceptable: ["5"]
"""


def test_default_catalog_loads_two_paths() -> None:
    """默认内容包含两条已登记路径。"""
    catalog = load_path_catalog(CONTENT_ROOT / "paths")

    assert not catalog.errors
    assert set(catalog.paths) == {"hs-trig-002-e2", "hs-trig-005-e2"}


def test_invalid_path_verify_is_rejected(tmp_path) -> None:
    """路径数学声明不成立时整条跳过。"""
    (tmp_path / "bad.yaml").write_text(_yaml(expected="6"), encoding="utf-8")

    catalog = load_path_catalog(tmp_path)

    assert catalog.paths == {}
    assert any("verify" in error for error in catalog.errors)


def test_expression_checkpoint_requires_verify_expected(tmp_path) -> None:
    """表达式检查点缺少 verify 参照时拒绝加载。"""
    text = _yaml().replace(
        '        input_kind: number\n        acceptable: ["5"]',
        '        input_kind: expr',
    )
    (tmp_path / "expr.yaml").write_text(text, encoding="utf-8")

    catalog = load_path_catalog(tmp_path)

    assert catalog.paths == {}
    assert catalog.errors


def test_duplicate_path_id_is_skipped(tmp_path) -> None:
    """同一题重复路径只保留第一条。"""
    text = _yaml()
    body = text.split("paths:\n", 1)[1]
    (tmp_path / "dup.yaml").write_text(text + body, encoding="utf-8")

    catalog = load_path_catalog(tmp_path)

    assert len(catalog.paths["hs-trig-005-e2"]) == 1
    assert any("重复路径" in error for error in catalog.errors)


def test_unknown_kc_is_rejected(tmp_path) -> None:
    """引用未知 KC 的路径不加载。"""
    text = _yaml().replace("kc-hs-trig-005-f1", "kc-unknown")
    (tmp_path / "kc.yaml").write_text(text, encoding="utf-8")

    catalog = load_path_catalog(tmp_path)

    assert catalog.paths == {}
    assert any("未知 KC" in error for error in catalog.errors)


def test_custom_verify_fn_is_used(tmp_path) -> None:
    """可注入 verify 函数，失败时拒绝路径。"""
    (tmp_path / "ok.yaml").write_text(_yaml(), encoding="utf-8")

    def reject(left: str, right: str, variables: frozenset[str]):
        return SymbolicVerdict.NOT_EQUIVALENT

    catalog = load_path_catalog(tmp_path, verify_fn=reject)

    assert catalog.paths == {}
    assert catalog.errors
