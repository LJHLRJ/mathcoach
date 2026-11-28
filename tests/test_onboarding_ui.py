"""首次使用后的非阻塞引导：出现条件、关闭与持久化。"""
from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import (
    Consent,
    ExerciseKind,
    Independence,
    Receipt,
    Stage,
)
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.memory.settings_repo import SQLiteSettingsStore
from mathcoach.ui.onboarding import (
    ONBOARDING_KEY,
    dismiss_onboarding,
    onboarding_dismissed,
    repository_has_history,
    should_render_onboarding,
)

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
PERSISTENT = Consent(memory=True, mistake_book=True)


def _receipt() -> Receipt:
    """构造收据样例。"""
    return Receipt(
        card_id="hs-function-intro-001",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=12,
        max_hint_level=1,
        goal="搞懂函数",
        independence=Independence.INDEPENDENT,
        created_at=datetime(2026, 11, 21, 12, 0, tzinfo=UTC),
    )


def _complete_first_loop(at: AppTest) -> None:
    """完成一次最小学习闭环。"""
    at.selectbox[0].select("hs-function-intro-001").run()
    at.text_input[0].set_value("搞懂函数")
    at.button[0].click().run()
    at.button[0].click().run()
    at.radio[0].set_value("y = x²")
    at.button[0].click().run()


@pytest.mark.parametrize(
    ("completed", "had_history", "dismissed", "expected"),
    [
        (False, False, False, False),
        (True, True, False, False),
        (True, False, True, False),
        (True, False, False, True),
    ],
)
def test_should_render_onboarding(
    completed, had_history, dismissed, expected
):
    """引导仅在首次完成且未关闭时出现。"""
    assert (
        should_render_onboarding(
            completed=completed,
            had_history=had_history,
            dismissed=dismissed,
        )
        is expected
    )


def test_repository_has_history_detects_existing_receipts():
    """已有收据视为有历史。"""
    repository = InMemoryRepository()

    assert repository_has_history(repository) is False
    repository.save_receipt(_receipt(), exercise_id="hs-001-e1")
    assert repository_has_history(repository) is True


def test_dismissal_persists_to_settings_store(tmp_path):
    """关闭状态写入设置存储。"""
    path = tmp_path / "onboarding.sqlite3"

    assert onboarding_dismissed(PERSISTENT, path) is False
    dismiss_onboarding(PERSISTENT, path)
    assert onboarding_dismissed(PERSISTENT, path) is True

    store = SQLiteSettingsStore(path)
    try:
        assert store.get_all()[ONBOARDING_KEY] is True
    finally:
        store.close()


def test_onboarding_appears_after_first_use_without_blocking(
    tmp_path, monkeypatch
):
    """首次完成后出现非阻塞引导并可关闭。"""
    monkeypatch.setenv("MATHCOACH_DB", str(tmp_path / "onboarding-ui.sqlite3"))
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()

    assert not at.exception
    assert not any("新手引导" in markdown.value for markdown in at.markdown)

    _complete_first_loop(at)
    assert "收据已生成" in at.subheader[0].value
    assert not any("新手引导" in markdown.value for markdown in at.markdown)

    next(button for button in at.button if button.label == "继续").click().run()
    assert not at.exception
    assert any("新手引导" in markdown.value for markdown in at.markdown)
    assert at.title[0].value == "数学陪练"
    assert any(button.label == "提交答案" for button in at.button)

    next(
        button for button in at.button if button.key == "onboarding_dismiss"
    ).click().run()
    assert not at.exception
    assert not any("新手引导" in markdown.value for markdown in at.markdown)

    at.run()
    assert not any("新手引导" in markdown.value for markdown in at.markdown)
