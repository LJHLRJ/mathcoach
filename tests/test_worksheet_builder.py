"""可打印练习单构建：来源、限量、去重、快照回退与只读。"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mathcoach.config import resolve_content_root
from mathcoach.content.loader import load_content
from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    MistakeEntry,
    ReviewItem,
    Stage,
)
from mathcoach.domain.spaced_repetition import Quality
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.worksheet import WorksheetSource, build_worksheet

CONTENT_ROOT = resolve_content_root(Path(__file__).resolve().parents[1] / "app.py")
CARDS, _ = load_content(CONTENT_ROOT, strict=False)
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


def _mistake(
    identifier: str,
    *,
    exercise_id: str = "hs-function-intro-001-e1",
    card_id: str = "hs-function-intro-001",
    course: str = "函数与导数",
    stem: str = "函数题",
    correct_answer: str = "正确答案",
    created_at: datetime | None = None,
    snapshot: dict[str, object] | None = None,
) -> MistakeEntry:
    """构造一条错题。"""
    return MistakeEntry(
        id=identifier,
        exercise_id=exercise_id,
        card_id=card_id,
        stage=Stage.HIGH_SCHOOL,
        course=course,
        exercise_type=ExerciseKind.CHOICE,
        stem=stem,
        user_answer="错答",
        correct_answer=correct_answer,
        error_type=ErrorType.CONCEPT,
        max_hint_level=1,
        created_at=created_at or NOW - timedelta(days=1),
        exercise_snapshot=snapshot or {},
    )


class _DuplicateRepository:
    """重复返回同一错题的只读仓储替身。"""

    def __init__(self, mistake: MistakeEntry) -> None:
        self._mistake = mistake

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]:
        """返回两次同一错题。"""
        return [self._mistake, self._mistake]

    def list_review_items(self) -> list[ReviewItem]:
        """没有待复习项。"""
        return []


def test_current_card_worksheet_limits_and_reports_count() -> None:
    """当前卡片按上限截取，并记录截取提示。"""
    worksheet = build_worksheet(
        CARDS,
        source=WorksheetSource.CURRENT_CARD,
        current_card_id="hs-function-intro-001",
        count=2,
        now=NOW,
    )

    assert worksheet.count == 2
    assert worksheet.source_label == "当前卡片：函数的概念"
    assert all(item.card_name == "函数的概念" for item in worksheet.items)
    assert "已按题目上限截取前 2 题。" in worksheet.notes


def test_same_topic_prefers_current_then_chapter_then_course() -> None:
    """同章节/同课程来源先当前卡，再同章节，最后同课程。"""
    worksheet = build_worksheet(
        CARDS,
        source=WorksheetSource.SAME_TOPIC,
        current_card_id="hs-function-intro-001",
        count=10,
        now=NOW,
    )

    ids = [item.exercise.id for item in worksheet.items]
    assert worksheet.count == 10
    assert ids[:3] == [
        "hs-function-intro-001-e1",
        "hs-function-intro-001-e2",
        "hs-function-intro-001-e3",
    ]
    assert ids[3:6] == [
        "hs-func-002-e1",
        "hs-func-002-e2",
        "hs-func-002-e3",
    ]
    chapters = [
        item.card.chapter if item.card is not None else ""
        for item in worksheet.items
    ]
    assert chapters[:6] == ["函数概念"] * 6
    assert any(chapter != "函数概念" for chapter in chapters[6:])


def test_same_topic_respects_count_and_reports_truncation() -> None:
    """同章节/同课程来源同样受题目上限约束。"""
    worksheet = build_worksheet(
        CARDS,
        source=WorksheetSource.SAME_TOPIC,
        current_card_id="hs-function-intro-001",
        count=5,
        now=NOW,
    )

    assert worksheet.count == 5
    assert "已按题目上限截取前 5 题。" in worksheet.notes


def test_same_topic_reports_when_course_is_too_small() -> None:
    """同课程题量不足时明确提示实际生成数。"""
    single = replace(CARDS[0], course="独立课程", chapter="独立章节")
    worksheet = build_worksheet(
        [single],
        source=WorksheetSource.SAME_TOPIC,
        current_card_id=single.id,
        count=10,
        now=NOW,
    )

    assert worksheet.count == len(single.exercises)
    assert (
        f"同章节/同课程可用题目不足 10 题，"
        f"已生成 {len(single.exercises)} 题。"
        in worksheet.notes
    )


def test_unknown_card_returns_empty_worksheet() -> None:
    """卡片不存在时返回空练习单。"""
    worksheet = build_worksheet(
        CARDS,
        source=WorksheetSource.CURRENT_CARD,
        current_card_id="missing-card",
        now=NOW,
    )

    assert worksheet.items == ()
    assert worksheet.source_label == "当前卡片不在题库中"
    assert "暂无可生成的题目。" in worksheet.notes


def test_due_review_only_includes_today() -> None:
    """待复习来源只取今天到期的错题。"""
    repository = InMemoryRepository()
    due = repository.save_mistake(_mistake("m-due"))
    future = repository.save_mistake(
        _mistake(
            "m-future",
            exercise_id="hs-function-intro-001-e2",
            created_at=NOW - timedelta(days=1),
        )
    )
    repository.record_review(future.exercise_id, Quality.INDEPENDENT, NOW)

    worksheet = build_worksheet(
        CARDS,
        source=WorksheetSource.DUE_REVIEW,
        repository=repository,
        count=10,
        now=NOW,
    )

    assert [item.exercise.id for item in worksheet.items] == [
        due.exercise_id
    ]


def test_due_review_empty_reports_reason() -> None:
    """没有到期错题时给出明确提示。"""
    worksheet = build_worksheet(
        CARDS,
        source=WorksheetSource.DUE_REVIEW,
        repository=InMemoryRepository(),
        now=NOW,
    )

    assert worksheet.items == ()
    assert "今天没有到期的待复习错题。" in worksheet.notes
    assert "暂无可生成的题目。" in worksheet.notes


def test_mistake_source_uses_snapshot_when_exercise_missing() -> None:
    """旧错题不在题库时用快照还原。"""
    repository = InMemoryRepository()
    repository.save_mistake(
        _mistake(
            "legacy",
            exercise_id="legacy-e1",
            stem="旧题题干",
            correct_answer="旧答案",
            card_id="hs-function-intro-001",
            snapshot={
                "options": ["选项一", "选项二"],
                "solution_outline": "旧思路",
            },
        )
    )

    worksheet = build_worksheet(
        CARDS,
        source=WorksheetSource.MISTAKES,
        repository=repository,
        now=NOW,
    )

    assert worksheet.count == 1
    item = worksheet.items[0]
    assert item.exercise.stem == "旧题题干"
    assert item.exercise.answer == "旧答案"
    assert item.exercise.options == ("选项一", "选项二")
    assert item.exercise.solution_outline == "旧思路"
    assert item.card_name == "函数的概念"
    assert "部分题目不在题库中，已用错题快照还原。" in worksheet.notes


def test_mistake_source_dedupes_by_exercise_id() -> None:
    """同一道题重复出现时只保留一条。"""
    worksheet = build_worksheet(
        CARDS,
        source=WorksheetSource.MISTAKES,
        repository=_DuplicateRepository(_mistake("m1")),
        now=NOW,
    )

    assert worksheet.count == 1


def test_worksheet_build_does_not_write_repository() -> None:
    """构建练习单不改变错题或收据。"""
    repository = InMemoryRepository()
    repository.save_mistake(_mistake("m1"))
    before_mistakes = repository.list_mistakes(limit=None)
    before_receipts = repository.list_receipts(limit=None)

    build_worksheet(
        CARDS,
        source=WorksheetSource.MISTAKES,
        repository=repository,
        now=NOW,
    )

    assert repository.list_mistakes(limit=None) == before_mistakes
    assert repository.list_receipts(limit=None) == before_receipts
