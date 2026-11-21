"""安装向导配置与安装前说明的静态一致性断言；不执行安装器。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISS_PATH = ROOT / "scripts" / "installer" / "MathCoach.iss"
NOTICE_PATH = ROOT / "scripts" / "installer" / "install-before.txt"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, name: str) -> list[str]:
    """返回指定 Inno 小节的非空、非注释行。"""
    marker = f"[{name}]".lower()
    lines: list[str] = []
    active = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            active = stripped.lower() == marker
            continue
        if active and stripped and not stripped.startswith(";"):
            lines.append(stripped)
    return lines


def test_installer_exposes_preinstall_notice():
    setup = _section(_read(ISS_PATH), "Setup")

    assert "InfoBeforeFile=scripts\\installer\\install-before.txt" in setup
    assert "DisableWelcomePage=yes" in setup
    assert NOTICE_PATH.is_file()


def test_notice_documents_trust_and_data_boundary():
    notice = _read(NOTICE_PATH)

    for phrase in (
        "未签名",
        "SHA256",
        "不会上传到任何服务器",
        "不会在安装阶段请求 AI 密钥",
        "不收集任何用户数据",
    ):
        assert phrase in notice


def test_desktop_icon_defaults_to_checked():
    tasks = _section(_read(ISS_PATH), "Tasks")
    line = next(
        item for item in tasks if item.startswith('Name: "desktopicon"')
    )

    assert "unchecked" not in line


def test_autostart_defaults_to_unchecked_and_is_removed_on_uninstall():
    text = _read(ISS_PATH)
    tasks = _section(text, "Tasks")
    line = next(
        item for item in tasks if item.startswith('Name: "autostart"')
    )
    assert "unchecked" in line

    registry = _section(text, "Registry")
    entry = next(
        item for item in registry if "CurrentVersion\\Run" in item
    )
    assert "Root: HKCU" in entry
    assert "Tasks: autostart" in entry
    assert "uninsdeletevalue" in entry
    assert "MathCoach.exe" in entry


def test_launch_after_install_is_checked_by_default():
    run = _section(_read(ISS_PATH), "Run")
    line = next(item for item in run if "postinstall" in item)

    assert "MathCoach.exe" in line
    assert "skipifsilent" in line
    assert "unchecked" not in line


def test_cancel_message_mentions_rollback():
    messages = _section(_read(ISS_PATH), "Messages")
    line = next(
        item for item in messages if item.startswith("ExitSetupMessage=")
    )

    assert "rolled back" in line


def test_notice_documents_install_options_and_limits():
    notice = _read(NOTICE_PATH)

    for phrase in (
        "桌面快捷方式首次安装默认勾选",
        "开机自启默认不勾选",
        "Windows 设置",
        "取消会回滚",
        "首次启动会自动创建",
        "没有分组件进度状态",
    ):
        assert phrase in notice


def test_notice_documents_non_blocking_first_launch():
    notice = _read(NOTICE_PATH)

    assert "不需要登录" in notice
    assert "不要求配置 AI" in notice
    assert "非阻塞卡片" in notice
