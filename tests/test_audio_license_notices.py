"""第三方资源清单、免责声明与设置页致谢入口。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
README = ROOT / "README.md"
AUDIO_DOC = ROOT / "docs" / "audio-and-backgrounds.md"


def test_notices_cover_used_reference_and_unused_resources():
    """资源清单覆盖已用、参考与未用资源。"""
    text = NOTICES.read_text(encoding="utf-8")

    for name in (
        "Pattern Craft",
        "uisfx",
        "Noisekun",
        "Moodist",
        "Open Lo-Fi",
        "CozyPixels",
        "bgvault",
        "Quiz and Game Show Sound Effects",
        "math-pattern-gen",
        "tiks",
    ):
        assert name in text

    assert "MIT License" in text
    assert "Copyright (c) 2025 Megh Bari" in text
    assert "CC0 1.0" in text
    assert "待人工复核" in text
    assert "仅参考配色，未使用任何图片" in text
    assert "未使用，待人工核实" in text


def test_disclaimer_is_verbatim_in_notices_and_readme():
    """免责声明在清单与 README 中逐字一致。"""
    required = (
        "本项目集成的背景图案、音效与环境音来自第三方开源项目",
        "不对第三方资源的版权状态作任何法律保证",
        "CC0 / 公有领域资源：无需署名",
        "MIT 资源：保留原版权声明与许可声明",
        "来源不明或许可证不清的资源：一律不使用",
        "不承担相关责任",
    )
    notices = NOTICES.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    for phrase in required:
        assert phrase in notices
        assert phrase in readme


def test_readme_and_audio_doc_link_to_notices():
    """README 与音频文档链接到第三方清单。"""
    readme = README.read_text(encoding="utf-8")
    audio_doc = AUDIO_DOC.read_text(encoding="utf-8")

    assert "[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)" in readme
    assert "[docs/audio-and-backgrounds.md](docs/audio-and-backgrounds.md)" in readme
    assert "[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)" in audio_doc


def test_settings_about_shows_resources_and_disclaimer(tmp_path, monkeypatch):
    """设置页关于区块展示资源与免责声明。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "about.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    at.session_state["main_tabs"] = "设置"
    at.run()

    assert not at.exception
    captions = " ".join(caption.value for caption in at.caption)
    markdown = " ".join(item.value for item in at.markdown)
    assert "THIRD_PARTY_NOTICES.md" in captions
    assert "不对第三方资源的版权状态作任何法律保证" in markdown
    assert "Pattern Craft" in markdown
