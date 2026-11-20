"""学习包导出：Markdown、独立收据/错题文件与 Anki TSV。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..domain.models import KnowledgeCard, MistakeEntry, Receipt
from ..memory.repository import Repository
from ..safety.redlines import (
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
    describe_write,
    sanitize_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_FILENAMES = (
    "learning_package.md",
    "receipts.md",
    "mistakes.md",
    "anki.tsv",
)
STAGE_LABELS = {"highschool": "高中", "undergraduate": "本科", "graduate": "研究生"}
_EXPORT = "export"


@dataclass(frozen=True)
class ExportArtifact:
    destination: Path
    files: dict[str, str]
    card_count: int
    receipt_count: int
    mistake_count: int
    generated_at: datetime

    def summary_text(self) -> str:
        return (
            f"知识点 {self.card_count} 张 · 收据 {self.receipt_count} 条 · "
            f"错题 {self.mistake_count} 条 · {len(self.files)} 个文件"
        )


def _safe(text: object) -> str:
    return sanitize_text(str(text))


def _md(text: object) -> str:
    return _safe(text).replace("|", r"\|").replace("\n", " ").strip()


def _tsv(text: object) -> str:
    return _safe(text).replace("\t", " ").replace("\r", " ").replace("\n", "<br>")


def _tag(text: object) -> str:
    return re.sub(r"\s+", "_", _safe(text)).strip("_")


def _when(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def _knowledge_section(cards: list[KnowledgeCard]) -> str:
    lines = ["## 知识点摘要", ""]
    if not cards:
        lines.append("暂无已学习卡片。")
        return "\n".join(lines)
    for card in cards:
        lines.append(
            f"### {STAGE_LABELS.get(card.stage.value, card.stage.value)} · "
            f"{_md(card.course)} · {_md(card.name)}"
        )
        lines.append(f"- 直觉：{_md(card.intuition)}")
        lines.append(f"- 定义：{_md(card.definition)}")
        if card.mistakes:
            lines.append(f"- 常见误区：{_md('；'.join(card.mistakes))}")
        lines.append(f"- 示例：{_md(card.example)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _receipts_section(
    receipts: list[Receipt], cards_by_id: dict[str, KnowledgeCard]
) -> str:
    lines = [
        "## 收据摘要",
        "",
        "| 时间 | 卡片 | 题型 | 最高提示 | 独立程度 | 用时 |",
        "|---|---|---|---|---|---|",
    ]
    if not receipts:
        lines.append("| - | 暂无收据 | - | - | - | - |")
        return "\n".join(lines)
    for receipt in receipts:
        card = cards_by_id.get(receipt.card_id)
        name = card.name if card else receipt.card_id
        lines.append(
            f"| {_when(receipt.created_at)} | {_md(name)} | "
            f"{receipt.exercise_type.value} | L{receipt.max_hint_level} | "
            f"{receipt.independence.value} | {receipt.duration_s} 秒 |"
        )
    return "\n".join(lines)


def _mistakes_section(mistakes: list[MistakeEntry]) -> str:
    lines = ["## 错题清单", ""]
    if not mistakes:
        lines.append("暂无错题。")
        return "\n".join(lines)
    for index, mistake in enumerate(mistakes, start=1):
        lines.append(f"### {index}. {_md(mistake.stem)}")
        lines.append(f"- 课程：{_md(mistake.course)}")
        lines.append(f"- 你的答案：{_md(mistake.user_answer)}")
        lines.append(f"- 正确答案：{_md(mistake.correct_answer)}")
        lines.append(f"- 错因：{mistake.error_type.value}")
        lines.append(f"- 复习状态：{mistake.review_state.value}")
        solution = mistake.exercise_snapshot.get("solution_outline")
        if solution:
            lines.append(f"- 思路：{_md(solution)}")
        lines.append(f"- 记录时间：{_when(mistake.created_at)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _anki_tsv(mistakes: list[MistakeEntry]) -> str:
    lines = [
        "#separator:tab",
        "#html:true",
        "#tags column:3",
        "题干\t答案与思路\t标签",
    ]
    for mistake in mistakes:
        solution = mistake.exercise_snapshot.get("solution_outline") or ""
        back = f"正确答案：{mistake.correct_answer}"
        if solution:
            back += f"<br>思路：{solution}"
        if mistake.user_answer:
            back += f"<br>你的答案：{mistake.user_answer}"
        back += f"<br>错因：{mistake.error_type.value}"
        tags = " ".join(
            [
                "mathcoach",
                f"stage_{_tag(mistake.stage.value)}",
                f"course_{_tag(mistake.course)}",
                f"error_{_tag(mistake.error_type.value)}",
            ]
        )
        lines.append(
            f"{_tsv(mistake.stem)}\t{_tsv(back)}\t{tags}"
        )
    return "\n".join(lines) + "\n"


def build_export_artifact(
    repository: Repository,
    cards: list[KnowledgeCard],
    destination: Path,
    now: datetime,
) -> ExportArtifact:
    receipts = repository.list_receipts(limit=None)
    mistakes = repository.list_mistakes(limit=None)
    cards_by_id = {card.id: card for card in cards}
    engaged_ids = {receipt.card_id for receipt in receipts} | {
        mistake.card_id for mistake in mistakes
    }
    engaged_cards = [card for card in cards if card.id in engaged_ids]

    knowledge = _knowledge_section(engaged_cards)
    receipt_text = _receipts_section(receipts, cards_by_id)
    mistake_text = _mistakes_section(mistakes)
    generated = _when(now)

    learning = "\n\n".join(
        [
            "# 数学陪练学习包",
            f"生成时间：{generated}",
            knowledge,
            receipt_text,
            mistake_text,
        ]
    )
    files = {
        "learning_package.md": learning + "\n",
        "receipts.md": f"# 收据摘要\n\n生成时间：{generated}\n\n{receipt_text}\n",
        "mistakes.md": f"# 错题清单\n\n生成时间：{generated}\n\n{mistake_text}\n",
        "anki.tsv": _anki_tsv(mistakes),
    }
    return ExportArtifact(
        destination=Path(destination),
        files=files,
        card_count=len(engaged_cards),
        receipt_count=len(receipts),
        mistake_count=len(mistakes),
        generated_at=now,
    )


def describe_export(artifact: ExportArtifact) -> str:
    return describe_write(
        _EXPORT,
        {
            "destination": str(artifact.destination),
            "cards": artifact.card_count,
            "receipts": artifact.receipt_count,
            "mistakes": artifact.mistake_count,
            "files": list(artifact.files),
        },
    )


def _is_inside_repo(path: Path) -> bool:
    try:
        Path(path).resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def write_export(
    artifact: ExportArtifact,
    *,
    consent,
    confirmation: str | None,
    repository: Repository,
) -> tuple[Path, ...]:
    if _is_inside_repo(artifact.destination):
        repository.record_audit(_EXPORT, "blocked:forbidden_destination")
        raise WriteBlocked("forbidden_destination")
    try:
        assert_write_allowed(
            _EXPORT,
            consent=consent,
            confirmation=confirmation,
            destination="file",
        )
    except (WriteBlocked, ConfirmationRequired) as exc:
        repository.record_audit(_EXPORT, f"blocked:{exc.reason}")
        raise

    written: list[Path] = []
    try:
        artifact.destination.mkdir(parents=True, exist_ok=True)
        for name, content in artifact.files.items():
            path = artifact.destination / name
            path.write_text(content, encoding="utf-8")
            written.append(path)
    except OSError:
        repository.record_audit(_EXPORT, "error")
        raise
    repository.record_audit(_EXPORT, "ok")
    return tuple(written)
