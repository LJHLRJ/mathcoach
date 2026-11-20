"""引擎与记忆层联动：写收据/错题、复习流转、游客模式不落盘。"""
from pathlib import Path

from mathcoach.content.loader import load_content
from mathcoach.domain.models import Consent, ErrorType, ReviewState
from mathcoach.llm.offline_provider import OfflineProvider
from mathcoach.memory.repository import InMemoryRepository, build_repository
from mathcoach.memory.sqlite_repo import SQLiteRepository
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def _engine(repository, consent: Consent | None = None) -> SessionEngine:
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card = next(card for card in cards if card.id == "hs-function-intro-001")
    return SessionEngine(
        card=card,
        provider=OfflineProvider(),
        repository=repository,
        consent=consent or Consent(),
    )


def _wrong_then_correct(engine: SessionEngine, with_hint: bool = False) -> None:
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    engine.retry()
    if with_hint:
        engine.request_hint("step")
        engine.retry()
    engine.submit_answer("y = x²")


def test_wrong_answer_records_mistake_and_review_item():
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
    repository = InMemoryRepository()
    engine = _engine(repository)
    _wrong_then_correct(engine)

    assert len(repository.list_receipts()) == 1
    entry = repository.list_mistakes()[0]
    assert entry.review_state is ReviewState.REVIEWING
    assert entry.review_count == 1
    assert entry.consecutive_correct == 1


def test_semi_independent_review_schedules_three_days_later():
    repository = InMemoryRepository()
    engine = _engine(repository)
    _wrong_then_correct(engine, with_hint=True)

    entry = repository.list_mistakes()[0]
    assert entry.review_state is ReviewState.REVIEWING
    assert entry.consecutive_correct == 0


def test_two_independent_corrects_master_across_sessions():
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
    repository = InMemoryRepository()
    engine = _engine(repository)
    engine.confirm_goal("搞懂函数")
    engine.begin_quiz()
    engine.submit_answer("y² = x")
    engine.retry()
    engine.submit_answer("x = 1")
    engine.confirm_diagnosis("计算失误")

    assert repository.list_mistakes()[0].error_type is ErrorType.CALCULATION


def test_consent_off_does_not_write_anything():
    repository = InMemoryRepository(Consent(memory=False, mistake_book=False))
    engine = _engine(repository, Consent(memory=False, mistake_book=False))
    _wrong_then_correct(engine)

    assert repository.list_mistakes() == []
    assert repository.list_receipts() == []


def test_sqlite_memory_survives_restart(tmp_path):
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
    path = tmp_path / "guest.sqlite3"
    consent = Consent(memory=False, mistake_book=False)
    repository = build_repository(consent, path)
    engine = _engine(repository, consent)
    _wrong_then_correct(engine)

    assert repository.list_mistakes() == []
    assert repository.list_receipts() == []
    assert not path.exists()
