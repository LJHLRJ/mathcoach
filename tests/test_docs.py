"""文档与提示词评审副本必须与运行时保持一致。"""
from pathlib import Path

from mathcoach.llm.prompts import PROMPT_VERSION, SYSTEM_PARSER, SYSTEM_TUTOR

ROOT = Path(__file__).resolve().parents[1]


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
