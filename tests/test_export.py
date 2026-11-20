"""学习包导出：内容、脱敏、确认门与仓库禁写。"""
from datetime import datetime, timezone

import pytest

from mathcoach.domain.models import (
    Consent,
    Difficulty,
    ErrorType,
    Exercise,
    ExerciseKind,
    Independence,
    KnowledgeCard,
    MistakeEntry,
    Receipt,
    ReviewState,
    Stage,
)
from mathcoach.export.package import (
    EXPORT_FILENAMES,
    PROJECT_ROOT,
    build_export_artifact,
    write_export,
)
from mathcoach.memory.repository import InMemoryRepository
from mathcoach.safety.redlines import (
    FULL_CONFIRMATION,
    ConfirmationRequired,
    WriteBlocked,
)

NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
CARD_ID = "export-card"


def _card() -> KnowledgeCard:
    exercise = Exercise(
        id=f"{CARD_ID}-e1",
        card_id=CARD_ID,
        kind=ExerciseKind.CHOICE,
        stem="y=x² 是函数吗？",
        answer="是",
        solution_outline="每个 x 只有唯一 y",
        options=("是", "否"),
    )
    return KnowledgeCard(
        id=CARD_ID,
        name="函数的概念",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        chapter="函数概念",
        difficulty=Difficulty.BASIC,
        intuition="输入唯一输出",
        definition="每个 x 对应唯一 y",
        mistakes=("忽略定义域",),
        example="y=x²",
        exercises=(exercise,),
        source="智能体生成",
    )


def _repository() -> InMemoryRepository:
    repository = InMemoryRepository()
    repository.save_receipt(
        Receipt(
            card_id=CARD_ID,
            stage=Stage.HIGH_SCHOOL,
            course="函数与导数",
            exercise_type=ExerciseKind.CHOICE,
            duration_s=30,
            max_hint_level=2,
            goal="练函数",
            independence=Independence.INDEPENDENT,
            created_at=NOW,
            exercise_id=f"{CARD_ID}-e1",
            id="r1",
        ),
        exercise_id=f"{CARD_ID}-e1",
    )
    repository.save_mistake(
        MistakeEntry(
            id="m1",
            exercise_id=f"{CARD_ID}-e1",
            card_id=CARD_ID,
            stage=Stage.HIGH_SCHOOL,
            course="函数与导数",
            exercise_type=ExerciseKind.CHOICE,
            stem="回答问题",
            user_answer="电话 13800138000",
            correct_answer="每个 x 对应唯一 y",
            error_type=ErrorType.CONCEPT,
            max_hint_level=1,
            created_at=NOW,
            review_state=ReviewState.UNREVIEWED,
            exercise_snapshot={"solution_outline": "回到定义判断"},
        )
    )
    return repository


def test_artifact_contains_all_files_and_learning_content(tmp_path):
    artifact = build_export_artifact(
        _repository(), [_card()], tmp_path / "export", NOW
    )

    assert tuple(artifact.files) == EXPORT_FILENAMES
    assert artifact.card_count == 1
    assert artifact.receipt_count == 1
    assert artifact.mistake_count == 1

    learning = artifact.files["learning_package.md"]
    assert "# 数学陪练学习包" in learning
    assert "函数的概念" in learning
    assert "收据摘要" in learning
    assert "错题清单" in learning

    receipts = artifact.files["receipts.md"]
    assert "独立完成" in receipts
    assert "L2" in receipts

    mistakes = artifact.files["mistakes.md"]
    assert "回到定义判断" in mistakes
    assert "[已脱敏]" in mistakes
    assert "13800138000" not in mistakes


def test_anki_tsv_is_importable_and_redacted(tmp_path):
    artifact = build_export_artifact(
        _repository(), [_card()], tmp_path / "export", NOW
    )
    lines = artifact.files["anki.tsv"].splitlines()

    assert lines[0] == "#separator:tab"
    assert lines[1] == "#html:true"
    assert lines[2] == "#tags column:3"
    assert len(lines) == 5  # 3 行头 + 列名 + 1 条错题
    for line in lines[3:]:
        assert len(line.split("\t")) == 3
    assert "<br>" in lines[-1]
    assert "[已脱敏]" in lines[-1]
    assert "13800138000" not in artifact.files["anki.tsv"]
    assert all(not name.endswith(".apkg") for name in artifact.files)


def test_write_requires_full_confirmation(tmp_path):
    repository = _repository()
    destination = tmp_path / "export"
    artifact = build_export_artifact(repository, [_card()], destination, NOW)

    with pytest.raises(ConfirmationRequired):
        write_export(
            artifact,
            consent=Consent(),
            confirmation="确认",
            repository=repository,
        )
    assert not destination.exists()
    assert any(entry.op == "export" for entry in repository.list_audit())


def test_write_creates_files_after_confirmation(tmp_path):
    repository = _repository()
    destination = tmp_path / "export"
    artifact = build_export_artifact(repository, [_card()], destination, NOW)

    written = write_export(
        artifact,
        consent=Consent(),
        confirmation=FULL_CONFIRMATION,
        repository=repository,
    )

    assert len(written) == 4
    assert all(path.exists() for path in written)
    assert repository.list_audit()[0].op == "export"
    assert repository.list_audit()[0].result == "ok"


def test_repo_destination_is_rejected(tmp_path):
    repository = _repository()
    destination = PROJECT_ROOT / "tmp-export-should-not-exist"
    artifact = build_export_artifact(repository, [_card()], destination, NOW)

    with pytest.raises(WriteBlocked):
        write_export(
            artifact,
            consent=Consent(),
            confirmation=FULL_CONFIRMATION,
            repository=repository,
        )
    assert not destination.exists()
    assert "forbidden_destination" in repository.list_audit()[0].result


def test_guest_mode_cannot_export(tmp_path):
    repository = _repository()
    destination = tmp_path / "export"
    artifact = build_export_artifact(repository, [_card()], destination, NOW)

    with pytest.raises(WriteBlocked):
        write_export(
            artifact,
            consent=Consent(memory=False, mistake_book=False),
            confirmation=FULL_CONFIRMATION,
            repository=repository,
        )
    assert not destination.exists()
