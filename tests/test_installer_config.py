"""安装器与发布资产配置检查。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_installer_uses_per_user_install():
    text = (ROOT / "scripts/installer/MathCoach.iss").read_text(encoding="utf-8")

    assert "DefaultDirName={localappdata}\\Programs\\MathCoach" in text
    assert "PrivilegesRequired=lowest" in text
    assert "OutputBaseFilename=MathCoachSetup-{#MyAppVersion}" in text
    assert "UninstallDisplayIcon={app}\\MathCoach.exe" in text
    assert 'Source: "dist\\MathCoach\\*"' in text


def test_macos_dmg_script_uses_hdiutil():
    text = (ROOT / "scripts/build_macos_dmg.sh").read_text(encoding="utf-8")

    assert "hdiutil create" in text
    assert "/Applications" in text
    assert "MathCoach-$version.dmg" in text
