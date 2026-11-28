"""速度掌握度：权重边界、异常耗时、BKT 接入与 FSRS 评分。"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mathcoach.config import resolve_content_root
from mathcoach.content.loader import load_content
from mathcoach.domain.bkt import initial_mastery, update_mastery
from mathcoach.domain.models import (
    Consent,
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    Stage,
)
from mathcoach.domain.spaced_repetition import Quality
from mathcoach.llm import OfflineProvider
from mathcoach.mastery import (
    SpeedPolicy,
    is_weak_correct,
    normalize_duration,
    observation_weight,
    quality_for_correct,
    reference_seconds_from_history,
)
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.memory.sqlite_repo import SQLiteRepository
from mathcoach.session.daily import (
    DailyQuestion,
    DailyState,
    record_daily_mistake,
    submit_daily_answer,
)
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = resolve_content_root(Path(__file__).resolve().parents[1] / "app.py")
POLICY = SpeedPolicy(
    reference_s=60.0,
    weak_ratio=1.5,
    floor_weight=0.5,
    max_duration_s=3600,
    min_samples=3,
)


def _receipt(duration_s: int, card_id: str = "c1") -> Receipt:
    """构造一条最小收据。"""
    return Receipt(
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=duration_s,
        max_hint_level=1,
        goal="练习",
        independence=Independence.INDEPENDENT,
        created_at=datetime.now(timezone.utc),
    )


def _card_and_question() -> tuple[object, DailyQuestion]:
    """取第一张卡与第一道题，供每日/会话测试复用。"""
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card = next(item for item in cards if item.id == "hs-function-intro-001")
    return card, DailyQuestion(card, card.exercises[0])


def test_weight_boundary_is_inclusive_at_threshold() -> None:
    """恰好到达弱阈值时仍按 1.0 处理。"""
    assert observation_weight(90, 60, POLICY) == 1.0
    assert observation_weight(90.1, 60, POLICY) < 1.0


def test_weight_reaches_floor_and_stays_there() -> None:
    """超过两倍弱阈值后权重固定为下限。"""
    assert observation_weight(180, 60, POLICY) == 0.5
    assert observation_weight(1000, 60, POLICY) == 0.5


def test_unknown_or_negative_duration_is_neutral() -> None:
    """未知或负耗时不能当成慢速。"""
    assert observation_weight(None, 60, POLICY) == 1.0
    assert observation_weight(-10, 60, POLICY) == 1.0
    assert observation_weight(0, 60, POLICY) == 1.0


def test_abnormal_duration_is_truncated() -> None:
    """超长耗时先截断，再计算权重。"""
    policy = SpeedPolicy(max_duration_s=3600)
    assert normalize_duration(1_000_000, policy) == 3600
    assert observation_weight(1_000_000, 60, policy) == 0.5


def test_reference_uses_median_and_ignores_abnormal_values() -> None:
    """参考耗时取历史中位数，异常长记录不参与。"""
    receipts = [
        _receipt(20),
        _receipt(40),
        _receipt(60),
        _receipt(5000),
    ]

    assert reference_seconds_from_history(receipts, "c1", policy=POLICY) == 40


def test_reference_falls_back_when_samples_are_insufficient() -> None:
    """样本不足时回退默认参考耗时。"""
    assert (
        reference_seconds_from_history(
            [_receipt(20), _receipt(40)],
            "c1",
            policy=POLICY,
            default=70,
        )
        == 70
    )


def test_weak_correct_maps_to_hinted_quality() -> None:
    """弱正确映射到 HINTED，复用现有 FSRS 的 HARD 间隔。"""
    assert is_weak_correct(200, 60, POLICY)
    assert quality_for_correct(200, 60, 0, POLICY) is Quality.HINTED
    assert quality_for_correct(10, 60, 0, POLICY) is Quality.INDEPENDENT
    assert quality_for_correct(10, 60, 4, POLICY) is Quality.HINTED


def test_weak_review_gets_shorter_fsrs_interval(
    tmp_path, monkeypatch
) -> None:
    """弱正确在 FSRS 路径按 HINTED 得到更短间隔。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "fsrs")
    repo = SQLiteRepository(tmp_path / "speed-fsrs.db")
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    for identifier in ("independent", "weak"):
        repo.save_mistake(
            MistakeEntry(
                id=identifier,
                exercise_id=f"e-{identifier}",
                card_id="c1",
                stage=Stage.HIGH_SCHOOL,
                course="函数与导数",
                exercise_type=ExerciseKind.FILL,
                stem="题干",
                user_answer="错答",
                correct_answer="正确",
                error_type=ErrorType.CALCULATION,
                max_hint_level=1,
                created_at=now,
                next_review_at=now,
            )
        )

    independent = repo.record_review(
        "e-independent", Quality.INDEPENDENT, now
    )
    weak = repo.record_review("e-weak", Quality.HINTED, now)

    assert independent is not None
    assert weak is not None
    assert weak.interval_days <= independent.interval_days


def test_record_mastery_weight_scales_update_without_formula_change() -> None:
    """mastery_weight 只缩放更新幅度。"""
    repository = InMemoryRepository(Consent(memory=True, mistake_book=False))
    now = datetime.now(timezone.utc)
    prior = initial_mastery()
    full = update_mastery(prior, True)

    weighted = repository.record_mastery(
        "c1", True, now, mastery_weight=0.5
    )

    assert weighted == pytest.approx(prior + 0.5 * (full - prior))


def test_session_weak_correct_gets_lower_mastery() -> None:
    """会话收据的弱正确在 BKT 入口被降权。"""
    card, _ = _card_and_question()
    normal_repo = InMemoryRepository(
        Consent(memory=True, mistake_book=False)
    )
    weak_repo = InMemoryRepository(
        Consent(memory=True, mistake_book=False)
    )
    normal_engine = SessionEngine(
        card,
        OfflineProvider(),
        repository=normal_repo,
        consent=Consent(memory=True, mistake_book=False),
    )
    weak_engine = SessionEngine(
        card,
        OfflineProvider(),
        repository=weak_repo,
        consent=Consent(memory=True, mistake_book=False),
    )
    for engine in (normal_engine, weak_engine):
        engine.confirm_goal("练习函数")
        engine.begin_quiz()
    weak_engine.state.exercise_started_at = datetime.now(
        timezone.utc
    ) - timedelta(seconds=300)

    answer = card.exercises[0].answer
    normal_engine.submit_answer(answer)
    weak_engine.submit_answer(answer)

    assert normal_repo.get_mastery(card.id) is not None
    assert weak_repo.get_mastery(card.id) is not None
    assert weak_repo.get_mastery(card.id) < normal_repo.get_mastery(card.id)


def test_daily_submission_tracks_question_duration() -> None:
    """每日挑战的单题作答记录包含耗时。"""
    _, question = _card_and_question()
    now = datetime.now(timezone.utc)
    state = DailyState(
        date_key="daily-test",
        questions=(question,),
        started_at=now - timedelta(seconds=45),
    )

    submission = submit_daily_answer(state, "y² = x", now)

    assert submission is not None
    assert submission.duration_s >= 45
    assert state.question_started_at == now


def test_daily_mistake_snapshot_keeps_duration() -> None:
    """错题快照保留单题耗时，供后续分析使用。"""
    repository = InMemoryRepository(Consent())
    _, question = _card_and_question()
    now = datetime.now(timezone.utc)

    record_daily_mistake(
        repository,
        Consent(),
        question,
        "y² = x",
        now,
        duration_s=42,
    )

    stored = repository.find_mistake(question.exercise.id)
    assert stored is not None
    assert stored.exercise_snapshot["duration_s"] == 42
