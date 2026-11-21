"""GitHub Actions 桌面构建 workflow：手动/标签触发，只上传 artifact。"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-desktop.yml"


def test_build_workflow_is_manual_or_tag_triggered():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch" in text
    assert "tags:" in text
    assert "actions/upload-artifact" in text
    assert "gh release" not in text
    assert "git push" not in text


def test_build_workflow_is_valid_yaml():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    assert isinstance(data, dict)
    assert "jobs" in data
    assert "windows-latest" in str(data)
    assert "macos-latest" in str(data)


def test_packaging_docs_cover_artifact_workflow():
    text = (ROOT / "docs/packaging/desktop-packaging-plan.md").read_text(
        encoding="utf-8"
    )

    assert "build-desktop.yml" in text
    assert "workflow_dispatch" in text
    assert "需在仓库中验证一次 workflow" in text

