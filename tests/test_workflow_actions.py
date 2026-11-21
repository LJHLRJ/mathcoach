"""确保 workflow 使用 Node 24 版本的 GitHub Actions。"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))
REQUIRED = {
    "actions/checkout": "v7",
    "actions/setup-python": "v7",
    "actions/upload-artifact": "v7",
}


def test_workflows_use_node24_action_majors():
    assert WORKFLOWS
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        for action, version in REQUIRED.items():
            for match in re.finditer(rf"uses:\s*{re.escape(action)}@(\S+)", text):
                assert match.group(1) == version, (
                    f"{path.name} 使用了 {action}@{match.group(1)}，"
                    f"应升级到 {version}"
                )


def test_workflows_are_valid_yaml_and_pin_action_majors():
    for path in WORKFLOWS:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path.name
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("uses:"):
                ref = stripped.removeprefix("uses:").strip()
                assert re.search(r"@v\d+$", ref), f"{path.name} 未固定大版本：{ref}"
