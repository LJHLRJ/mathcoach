"""文档与提示词评审副本必须与运行时保持一致。"""
import ast
from pathlib import Path

from mathcoach.llm.prompts import PROMPT_VERSION, SYSTEM_PARSER, SYSTEM_TUTOR

ROOT = Path(__file__).resolve().parents[1]
SECURITY_FILES = (
    ROOT / "tests/test_guards.py",
    ROOT / "tests/test_redlines.py",
)


def test_readme_contains_required_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install -r requirements.txt" in readme
    assert "streamlit run app.py" in readme
    assert "MATHCOACH_CONTENT_STRICT=1 python -m pytest -q" in readme
    assert "python -m build" in readme


def test_readme_milestone_table_covers_current_releases():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for milestone in ("M9", "M12", "M16", "M17"):
        assert f"| {milestone} |" in readme
    assert "FSRS" in readme
    assert "BKT" in readme
    assert "v0.5.0" in readme


def test_readme_points_update_entry_to_settings_tab():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "“设置”Tab 中的“关于与更新”" in readme
    assert "侧边栏“关于与更新”" not in readme


def test_readme_documents_security_test_coverage():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## 安全与边界" in readme
    assert "### 安全测试覆盖" in readme
    assert "22 项" in readme
    assert "9 / 10" in readme
    assert "6 / 6" in readme
    assert "GitHub Actions" in readme
    assert "9 / 9" not in readme
    assert "28 个用例" not in readme
    assert "10/10" not in readme
    assert "12/12" not in readme


def _functions_with(
    path: Path, markers: tuple[str, ...], *, include_safe: bool = False
) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    names: list[str] = []
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        if not include_safe and node.name.startswith("test_safe_"):
            continue
        source = (node.name + " " + (ast.get_source_segment(text, node) or "")).lower()
        if any(marker in source for marker in markers):
            names.append(node.name)
    return names


def test_readme_security_counts_match_test_files():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    test_functions = [
        node.name
        for path in SECURITY_FILES
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    blocked = [
        name
        for path in SECURITY_FILES
        for name in _functions_with(
            path, ("blocked", "rejected", "injection", "拒绝", "screened")
        )
    ]
    injection_samples = [
        name
        for path in SECURITY_FILES
        for name in _functions_with(
            path, ("block", "reject", "inject"), include_safe=True
        )
    ]
    redacted = [
        name
        for path in SECURITY_FILES
        for name in _functions_with(
            path, ("redact", "sanitize", "已脱敏", "masked")
        )
    ]

    assert len(test_functions) == 22
    assert len(blocked) == 9
    assert len(injection_samples) == 10
    assert len(redacted) == 6
    assert f"{len(test_functions)} 项" in readme
    assert f"{len(blocked)} / {len(injection_samples)}" in readme
    assert f"{len(redacted)} / {len(redacted)}" in readme


def test_readme_documents_unsigned_first_run_steps():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "未签名" in readme
    assert "更多信息" in readme
    assert "仍要运行" in readme
    assert "系统设置 → 隐私与安全性" in readme


def test_prompt_copies_match_runtime_constants():
    tutor = (ROOT / "prompts" / "tutor.md").read_text(encoding="utf-8")
    parser = (ROOT / "prompts" / "parser.md").read_text(encoding="utf-8")

    assert PROMPT_VERSION in tutor
    assert PROMPT_VERSION in parser
    assert SYSTEM_TUTOR in tutor
    assert SYSTEM_PARSER in parser


def test_prompts_directory_is_review_only():
    readme = (ROOT / "prompts" / "README.md").read_text(encoding="utf-8")
    assert "运行时不读取" in readme or "运行时不会读取" in readme
