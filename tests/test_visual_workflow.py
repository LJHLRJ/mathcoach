"""视觉回归 workflow、依赖边界与基线文件静态检查。"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/visual-regression.yml"
VISUAL_TEST = ROOT / "tests/test_visual_regression.py"
RUNTIME_REQUIREMENTS = ROOT / "requirements.txt"
VISUAL_REQUIREMENTS = ROOT / "requirements-visual.txt"
BASELINES = ROOT / "tests/visual/baselines"
STATES = ("first_screen", "quiz", "receipt")


def test_visual_workflow_is_valid_yaml_and_triggered():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    assert isinstance(data, dict)
    triggers = data.get("on") or data.get(True)  # PyYAML 可能把 on 解析为布尔键
    assert "pull_request" in triggers
    assert "workflow_dispatch" in triggers
    job = data["jobs"]["visual"]
    assert job["runs-on"] == "ubuntu-latest"


def test_visual_workflow_runs_test_and_uploads_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "requirements-visual.txt" in text
    assert "google-chrome --version" in text
    assert "VISUAL_REQUIRE_BROWSER" in text
    assert "VISUAL_MAX_DIFF_RATIO" in text
    assert "tests/test_visual_regression.py" in text
    assert "actions/upload-artifact" in text
    assert "if: always()" in text
    assert "git push" not in text


def test_visual_dependencies_are_ci_only_and_baselines_exist():
    runtime = RUNTIME_REQUIREMENTS.read_text(encoding="utf-8")
    visual = VISUAL_REQUIREMENTS.read_text(encoding="utf-8")
    test_text = VISUAL_TEST.read_text(encoding="utf-8")

    assert "playwright" not in runtime
    assert "playwright" in visual.lower()
    for state in STATES:
        assert f'"{state}"' in test_text
        assert (BASELINES / f"{state}.png").is_file()
