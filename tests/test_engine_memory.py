"""引擎与记忆层联动：写收据/错题、复习流转、游客模式不落盘。"""
from pathlib import Path

import pytest

from mathcoach.content.loader import load_content
from mathcoach.domain.models import (
    Consent,
    ErrorType,
    Independence,
    Phase,
    ReviewState,
)
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.memory.repository import InMemoryRepository, build_repository
from mathcoach.memory.sqlite_repo import SQLiteRepository
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def _engine(repository: InMemoryRepository, consent: Consent | None = None) -> SessionEngine:
    """构造带离线 Provider 的引擎。"""
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card = next(card for card in cards if card.id == "hs-function-intro-001")
    return SessionEngine(
        card=card,
        provider=OfflineProvider(),
        repository=repository,
        consent=consent or Consent(),
    )


def _wrong_then_correct(engine: SessionEngine, with_hint: bool = False) -> None:
    """先答错再重试并答对。"""
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    engine.retry()
    if with_hint:
        engine.request_hint("step")
        engine.retry()
    engine.submit_answer("y = x²")


def test_wrong_answer_records_mistake_and_review_item():
    """答错写入错题与复习队列。"""
    repository = InMemoryRepository()
    engine = _engine(repository)
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")

    mistakes = repository.list_mistakes()
    assert len(mistakes) == 1
    assert mistakes[0].exercise_id == engine.current_exercise.id
    assert mistakes[0].user_answer == "y² = x"
    assert repository.list_review_items()


def test_correct_answer_saves_receipt_and_reviews_mistake():
    """答对写收据并把错题转为复习中。"""
    repository = InMemoryRepository()
    engine = _engine(repository)
    _wrong_then_correct(engine)

    assert len(repository.list_receipts()) == 1
    entry = repository.list_mistakes()[0]
    assert entry.review_state is ReviewState.REVIEWING
    assert entry.review_count == 1
    assert entry.consecutive_correct == 1


def test_semi_independent_review_schedules_three_days_later():
    """有提示答对按半独立排期。"""
    repository = InMemoryRepository()
    engine = _engine(repository)
    _wrong_then_correct(engine, with_hint=True)

    entry = repository.list_mistakes()[0]
    assert entry.review_state is ReviewState.REVIEWING
    assert entry.consecutive_correct == 0


def test_two_independent_corrects_master_across_sessions():
    """跨会话两次独立答对转为已掌握。"""
    repository = InMemoryRepository()
    _wrong_then_correct(_engine(repository))
    assert repository.list_mistakes()[0].review_state is not ReviewState.MASTERED

    second = _engine(repository)
    second.confirm_goal("再练一次")
    second.begin_quiz()
    second.submit_answer("y = x²")

    entry = repository.list_mistakes()[0]
    assert entry.review_state is ReviewState.MASTERED
    assert repository.list_review_items() == []


def test_diagnosis_override_updates_mistake_book():
    """错因确认覆盖错题类型。"""
    repository = InMemoryRepository()
    engine = _engine(repository)
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    engine.retry()
    engine.submit_answer("x = 1")
    engine.confirm_diagnosis("计算失误")

    assert repository.list_mistakes()[0].error_type is ErrorType.CALCULATION


def test_diagnosis_confirmation_keeps_mastery():
    """确认错因不改变掌握度。"""
    repository = InMemoryRepository()
    engine = _engine(repository)
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    engine.retry()
    engine.submit_answer("x = 1")
    before = repository.get_mastery(engine.card.id)

    engine.confirm_diagnosis("计算失误")

    assert repository.get_mastery(engine.card.id) == before


def test_restatement_records_quality_without_extra_mastery():
    """复述记录质量且不额外提升掌握度。"""
    repository = InMemoryRepository()
    engine = _engine(repository)
    _wrong_then_correct(engine)
    before = repository.get_mastery(engine.card.id)

    view = engine.submit_restatement("每个 x 只有唯一 y 与之对应")

    assert view.receipt is not None
    assert view.receipt.restatement_quality == "完整"
    assert repository.list_receipts()[0].restatement_quality == "完整"
    assert repository.get_mastery(engine.card.id) == before
    with pytest.raises(ValueError):
        engine.submit_restatement("   ")


def test_hinted_correct_gains_less_mastery_than_independent():
    """有提示答对的掌握度增益更小。"""
    def mastery_after(hinted: bool) -> float:
        """计算指定提示条件下的掌握度。"""
        repository = InMemoryRepository()
        engine = _engine(repository)
        engine.confirm_goal("搞懂函数")
        engine.begin_quiz()
        if hinted:
            engine.request_hint("step")
            engine.retry()
        engine.submit_answer("y = x²")
        value = repository.get_mastery(engine.card.id)
        assert value is not None
        return value

    independent = mastery_after(False)
    hinted = mastery_after(True)

    assert independent > hinted > 0.3


def test_sparse_restatement_feeds_back_to_review():
    """稀疏复述回退复习连对。"""
    repository = InMemoryRepository()
    engine = _engine(repository)
    _wrong_then_correct(engine)
    before = repository.find_mistake("hs-function-intro-001-e1")
    mastery_before = repository.get_mastery(engine.card.id)
    assert before is not None and before.consecutive_correct == 1

    view = engine.submit_restatement("先移项再合并同类项")

    entry = repository.find_mistake("hs-function-intro-001-e1")
    assert entry is not None
    assert entry.consecutive_correct == 0
    assert entry.review_count == before.review_count + 1
    assert repository.get_mastery(engine.card.id) == mastery_before
    assert "半独立" in view.notice


def test_complete_restatement_keeps_review_streak():
    """完整复述保留复习连对。"""
    repository = InMemoryRepository()
    engine = _engine(repository)
    _wrong_then_correct(engine)
    before = repository.find_mistake("hs-function-intro-001-e1")
    assert before is not None

    view = engine.submit_restatement("每个 x 只有唯一 y 与之对应")

    updated = repository.find_mistake("hs-function-intro-001-e1")
    assert updated is not None
    assert updated.consecutive_correct == before.consecutive_correct
    assert "半独立" not in view.notice


def test_hinted_correct_is_not_recorded_as_fsrs_lapse(
    tmp_path, monkeypatch
):
    """有提示答对不计 FSRS 遗忘。"""
    monkeypatch.delenv("MATHCOACH_SCHEDULER", raising=False)
    repository = SQLiteRepository(tmp_path / "hinted.sqlite3")
    try:
        engine = _engine(repository)
        engine.confirm_goal("搞懂函数")
        engine.begin_quiz()
        engine.submit_answer("y² = x")
        engine.retry()
        engine.request_hint("step")
        engine.retry()

        view = engine.submit_answer("y = x²")

        assert view.phase is Phase.RECEIPT
        assert view.receipt is not None
        assert view.receipt.max_hint_level == 4
        assert view.receipt.independence is Independence.SEMI_INDEPENDENT

        entry = repository.find_mistake("hs-function-intro-001-e1")
        assert entry is not None
        assert entry.lapses == 0
        assert entry.stability > 1.0
    finally:
        repository.close()


def test_hinted_correct_uses_sm2_hinted_interval(tmp_path, monkeypatch):
    """SM-2 下有提示答对使用短间隔。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "sm2")
    repository = SQLiteRepository(tmp_path / "hinted-sm2.sqlite3")
    try:
        engine = _engine(repository)
        engine.confirm_goal("搞懂函数")
        engine.begin_quiz()
        engine.submit_answer("y² = x")
        engine.retry()
        engine.request_hint("step")
        engine.retry()

        engine.submit_answer("y = x²")

        entry = repository.find_mistake("hs-function-intro-001-e1")
        assert entry is not None
        assert entry.review_state is ReviewState.REVIEWING
        assert entry.interval_days == 1
        assert entry.ease == pytest.approx(2.36)
    finally:
        repository.close()


def test_consent_off_does_not_write_anything():
    """同意关闭时不写任何学习数据。"""
    repository = InMemoryRepository(Consent(memory=False, mistake_book=False))
    engine = _engine(repository, Consent(memory=False, mistake_book=False))
    _wrong_then_correct(engine)

    assert repository.list_mistakes() == []
    assert repository.list_receipts() == []


def test_sqlite_memory_survives_restart(tmp_path):
    """SQLite 记忆跨重启保留。"""
    path = tmp_path / "mathcoach.sqlite3"
    repository = SQLiteRepository(path)
    engine = _engine(repository)
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    repository.close()

    reopened = SQLiteRepository(path)
    try:
        assert len(reopened.list_mistakes()) == 1
        assert len(reopened.list_review_items()) == 1
    finally:
        reopened.close()


def test_guest_engine_never_creates_database(tmp_path):
    """游客引擎不创建数据库文件。"""
    path = tmp_path / "guest.sqlite3"
    consent = Consent(memory=False, mistake_book=False)
    repository = build_repository(consent, path)
    engine = _engine(repository, consent)
    _wrong_then_correct(engine)

    assert repository.list_mistakes() == []
    assert repository.list_receipts() == []
    assert not path.exists()
