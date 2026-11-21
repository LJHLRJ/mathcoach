"""测试与 CI 默认启用严格内容模式。"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_local_tests_default_to_strict_content_mode():
    assert os.environ.get("MATHCOACH_CONTENT_STRICT") == "1"


def test_pytest_workflows_inject_strict_content_mode():
    for name in ("visual-regression.yml", "release-desktop.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "MATHCOACH_CONTENT_STRICT" in text
        assert 'MATHCOACH_CONTENT_STRICT: "1"' in text


def test_config_default_remains_off_without_env():
    env = os.environ.copy()
    env.pop("MATHCOACH_CONTENT_STRICT", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from mathcoach.config import content_strict; "
            "print(content_strict())",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"
