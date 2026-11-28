"""安装器与发布资产配置检查。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_installer_uses_per_user_install():
    """Windows 安装器按当前账户安装并生成安装包。"""
    text = (ROOT / "scripts/installer/MathCoach.iss").read_text(encoding="utf-8")

    assert "DefaultDirName={localappdata}\\Programs\\MathCoach" in text
    assert "PrivilegesRequired=lowest" in text
    assert "OutputDir=dist\\installer" in text
    assert "OutputBaseFilename=MathCoachSetup-{#MyAppVersion}" in text
    assert "UninstallDisplayIcon={app}\\MathCoach.exe" in text
    assert 'Source: "dist\\MathCoach\\*"' in text


def test_macos_dmg_script_uses_hdiutil():
    """macOS 打包脚本通过 hdiutil 生成 dmg。"""
    text = (ROOT / "scripts/build_macos_dmg.sh").read_text(encoding="utf-8")

    assert "hdiutil create" in text
    assert "/Applications" in text
    assert "MathCoach-$version.dmg" in text


def test_release_workflow_builds_installers():
    """发布 workflow 构建并上传桌面安装包。"""
    text = (ROOT / ".github/workflows/release-desktop.yml").read_text(
        encoding="utf-8"
    )

    assert "ISCC.exe" in text
    assert "scripts/build_macos_dmg.sh" in text
    assert "MathCoachSetup" in text
    assert ".dmg" in text
    assert "gh release upload" in text
