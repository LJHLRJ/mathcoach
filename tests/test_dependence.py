"""依赖度信号：只读规则、阈值与误判边界。"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mathcoach.domain.dependence import (
    DependenceDialogEvent,
    DependenceLevel,
    DependenceStepAttempt,
    DependenceStepRun,
    evaluate_dependence,
)
from mathcoach.domain.models import (
    ExerciseKind,
    Independence,
    Receipt,
    Stage,
)

NOW = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)


def _receipt(
    index: int,
    *,
    card_id: str = "card-a",
    max_hint_level: int = 1,
) -> Receipt:
    """构造一条指定提示层级的历史收据。"""
    return Receipt(
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course="三角函数",
        exercise_type=ExerciseKind.FILL,
        duration_s=30,
        max_hint_level=max_hint_level,
        goal="测试",
        independence=(
            Independence.INDEPENDENT
            if max_hint_level <= 3
            else Independence.SEMI_INDEPENDENT
        ),
        created_at=NOW + timedelta(minutes=index),
    )


def test_no_signal_when_sample_is_small() -> None:
    """样本不足 3 条时不收紧。"""
    signal = evaluate_dependence(
        "card-a",
        [_receipt(0, max_hint_level=5), _receipt(1, max_hint_level=4)],
        mastery=0.8,
    )

    assert signal.level is DependenceLevel.NONE
    assert signal.hint_ceiling is None


def test_watch_when_two_of_three_are_semi_independent() -> None:
    """最近三题两题 L4/L5 且包含 L5 时只进入观察。"""
    signal = evaluate_dependence(
        "card-a",
        [
            _receipt(0, max_hint_level=1),
            _receipt(1, max_hint_level=4),
            _receipt(2, max_hint_level=5),
        ],
        mastery=0.8,
    )

    assert signal.level is DependenceLevel.WATCH
    assert "semi_independent_streak" in signal.reasons
    assert signal.hint_ceiling is None


def test_tighten_when_density_and_mastery_are_high() -> None:
    """最近五题三题 L4/L5、包含 L5 且掌握度达标时收紧。"""
    signal = evaluate_dependence(
        "card-a",
        [
            _receipt(0, max_hint_level=1),
            _receipt(1, max_hint_level=4),
            _receipt(2, max_hint_level=5),
            _receipt(3, max_hint_level=4),
            _receipt(4, max_hint_level=2),
        ],
        mastery=0.6,
    )

    assert signal.level is DependenceLevel.TIGHTEN
    assert signal.hint_ceiling == 2
    assert "semi_independent_density" in signal.reasons


def test_no_tighten_when_mastery_is_low() -> None:
    """掌握度低时只观察，不收紧提示。"""
    signal = evaluate_dependence(
        "card-a",
        [
            _receipt(0, max_hint_level=4),
            _receipt(1, max_hint_level=5),
            _receipt(2, max_hint_level=4),
        ],
        mastery=0.2,
    )

    assert signal.level is not DependenceLevel.TIGHTEN


def test_unknown_mastery_does_not_tighten() -> None:
    """掌握度未知时不做收紧判断。"""
    signal = evaluate_dependence(
        "card-a",
        [
            _receipt(0, max_hint_level=4),
            _receipt(1, max_hint_level=5),
            _receipt(2, max_hint_level=4),
        ],
        mastery=None,
    )

    assert signal.level is DependenceLevel.WATCH


def test_dialog_quality_drop_is_watch_only() -> None:
    """追问命中率下降只提高观察等级。"""
    events = [
        DependenceDialogEvent(
            card_id="card-a",
            level=3,
            kind="hit",
            created_at=NOW + timedelta(minutes=index),
        )
        for index in range(5)
    ]
    events.extend(
        DependenceDialogEvent(
            card_id="card-a",
            level=3,
            kind="miss",
            created_at=NOW + timedelta(minutes=10 + index),
        )
        for index in range(3)
    )

    signal = evaluate_dependence(
        "card-a",
        [_receipt(0)],
        dialog_events=events,
    )

    assert signal.level is DependenceLevel.WATCH
    assert "dialog_quality_drop" in signal.reasons
    assert signal.hint_ceiling is None


def test_step_stuck_is_watch_only() -> None:
    """同一步骤反复出错只提高观察等级。"""
    runs = [
        DependenceStepRun(
            exercise_id="ex-1",
            card_id="card-a",
            created_at=NOW + timedelta(minutes=index),
            attempts=(
                DependenceStepAttempt(
                    step_index=2, step_tag="formula", verdict="incorrect"
                ),
            ),
        )
        for index in range(3)
    ]

    signal = evaluate_dependence(
        "card-a",
        [_receipt(0)],
        step_runs=runs,
    )

    assert signal.level is DependenceLevel.WATCH
    assert "step_stuck" in signal.reasons
    assert signal.hint_ceiling is None


def test_other_cards_are_ignored() -> None:
    """其他卡片的收据不参与当前判断。"""
    signal = evaluate_dependence(
        "card-a",
        [
            _receipt(0, card_id="card-b", max_hint_level=5),
            _receipt(1, card_id="card-b", max_hint_level=5),
            _receipt(2, card_id="card-b", max_hint_level=5),
        ],
        mastery=0.8,
    )

    assert signal.level is DependenceLevel.NONE
    assert signal.sample == 0


def test_module_has_no_runtime_side_effects() -> None:
    """模块只依赖领域模型，不触达存储或 UI。"""
    source = (
        Path(__file__).resolve().parents[1]
        / "mathcoach"
        / "domain"
        / "dependence.py"
    ).read_text(encoding="utf-8")

    assert "sqlite3" not in source
    assert "streamlit" not in source
