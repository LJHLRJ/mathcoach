"""可解释报告：结论、证据锚点、空数据降级与 Markdown 呈现。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    ReviewState,
    Stage,
)
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.report import build_explainable_report, render_report_markdown

NOW = datetime(2026, 11, 28, 9, 0, tzinfo=timezone.utc)


def _mistake(
    identifier: str, exercise_id: str, error_type: ErrorType
) -> MistakeEntry:
    """构造一条错题。"""
    return MistakeEntry(
        id=identifier,
        exercise_id=exercise_id,
        card_id="hs-trig-002",
        stage=Stage.HIGH_SCHOOL,
        course="三角函数",
        exercise_type=ExerciseKind.FILL,
        stem="题干",
        user_answer="9/25",
        correct_answer="16/25",
        error_type=error_type,
        max_hint_level=2,
        created_at=NOW - timedelta(days=1),
        review_state=ReviewState.REVIEWING,
    )


def _receipt(identifier: str, exercise_id: str) -> Receipt:
    """构造一张收据。"""
    return Receipt(
        id=identifier,
        card_id="hs-trig-002",
        stage=Stage.HIGH_SCHOOL,
        course="三角函数",
        exercise_type=ExerciseKind.FILL,
        duration_s=42,
        max_hint_level=2,
        goal="搞懂同角关系",
        independence=Independence.INDEPENDENT,
        created_at=NOW - timedelta(hours=2),
        exercise_id=exercise_id,
    )


def _repo() -> InMemoryRepository:
    """准备一份带错题与收据的档案。"""
    repository = InMemoryRepository()
    repository.save_mistake(
        _mistake("m1", "hs-trig-002-e2", ErrorType.FORMULA)
    )
    repository.save_mistake(
        _mistake("m2", "hs-trig-002-e1", ErrorType.CALCULATION)
    )
    repository.save_receipt(_receipt("r1", "hs-trig-002-e2"), "hs-trig-002-e2")
    return repository


def test_report_builds_conclusions_with_evidence() -> None:
    """薄弱 KC、错因与独立率结论都带记录 ID 证据。"""
    report = build_explainable_report(
        _repo(),
        now=NOW,
        kc_mastery={"kc-hs-trig-002-f1": 0.2},
    )

    kinds = {conclusion.kind for conclusion in report.conclusions}
    assert "weak_kc" in kinds
    assert "error_pattern" in kinds
    assert kinds & {"independence", "review_load"}
    for conclusion in report.conclusions:
        assert conclusion.evidence
        assert conclusion.metrics
        assert all(
            anchor.id in {"m1", "m2", "r1"}
            for anchor in conclusion.evidence
        )


def test_report_markdown_contains_anchor_ids() -> None:
    """Markdown 同时呈现结论与可回指锚点。"""
    report = build_explainable_report(
        _repo(),
        now=NOW,
        kc_mastery={"kc-hs-trig-002-f1": 0.2},
    )

    markdown = render_report_markdown(report)

    assert "## 结论与证据" in markdown
    assert "mistake:m1" in markdown


def test_receipt_only_report_uses_receipt_anchor() -> None:
    """只有收据时，独立完成率结论用收据 ID 做锚点。"""
    repository = InMemoryRepository()
    repository.save_receipt(
        _receipt("r1", "hs-trig-002-e2"), "hs-trig-002-e2"
    )

    report = build_explainable_report(repository, now=NOW)

    conclusion = next(
        item
        for item in report.conclusions
        if item.kind == "independence"
    )
    assert conclusion.evidence[0].kind == "receipt"
    assert "receipt:r1" in render_report_markdown(report)


def test_empty_repository_reports_data_gap() -> None:
    """没有数据时不编造结论，只说明证据不足。"""
    report = build_explainable_report(
        InMemoryRepository(), now=NOW
    )

    assert report.conclusions == ()
    assert "证据不足" in render_report_markdown(report)
