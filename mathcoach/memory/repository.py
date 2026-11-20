"""记忆仓储契约与内存实现；游客模式使用 InMemoryRepository。"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from ..config import db_path as default_db_path
from ..domain.models import (
    AuditEntry,
    Consent,
    DailyResult,
    MistakeEntry,
    Receipt,
    ReviewItem,
    ReviewState,
)
from .scheduler import next_review

DEFAULT_CONSENT = Consent(memory=True, mistake_book=True)


class Repository(Protocol):
    def save_consent(self, consent: Consent) -> None: ...

    def load_consent(self) -> Consent: ...

    def save_receipt(self, receipt: Receipt, exercise_id: str) -> None: ...

    def list_receipts(self, limit: int | None = 50) -> list[Receipt]: ...

    def save_mistake(self, entry: MistakeEntry) -> MistakeEntry: ...

    def find_mistake(self, exercise_id: str) -> MistakeEntry | None: ...

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]: ...

    def record_review(
        self, exercise_id: str, independent: bool, now: datetime
    ) -> MistakeEntry | None: ...

    def list_review_items(self) -> list[ReviewItem]: ...

    def record_audit(
        self, op: str, result: str, now: datetime | None = None
    ) -> None: ...

    def list_audit(self, limit: int = 50) -> list[AuditEntry]: ...

    def save_daily_result(self, result: DailyResult) -> None: ...

    def get_daily_result(self, day: str) -> DailyResult | None: ...

    def close(self) -> None: ...


class InMemoryRepository:
    """游客模式：进程结束即丢弃，不触碰磁盘。"""

    def __init__(self, consent: Consent | None = None) -> None:
        self._consent = consent or DEFAULT_CONSENT
        self._receipts: list[Receipt] = []
        self._mistakes: dict[str, MistakeEntry] = {}
        self._due_at: dict[str, datetime] = {}
        self._audit: list[AuditEntry] = []
        self._daily: dict[str, DailyResult] = {}

    def save_consent(self, consent: Consent) -> None:
        self._consent = consent

    def load_consent(self) -> Consent:
        return self._consent

    def save_receipt(self, receipt: Receipt, exercise_id: str) -> None:
        self._receipts.append(receipt)

    def list_receipts(self, limit: int | None = 50) -> list[Receipt]:
        receipts = list(reversed(self._receipts))
        return receipts if limit is None else receipts[:limit]

    def save_mistake(self, entry: MistakeEntry) -> MistakeEntry:
        existing = self._mistakes.get(entry.exercise_id)
        if existing is not None:
            entry = replace(
                entry,
                id=existing.id,
                created_at=existing.created_at,
                review_state=ReviewState.UNREVIEWED,
                review_count=0,
                consecutive_correct=0,
                receipt_ids=existing.receipt_ids,
            )
        self._mistakes[entry.exercise_id] = entry
        self._due_at[entry.id] = entry.created_at
        return entry

    def find_mistake(self, exercise_id: str) -> MistakeEntry | None:
        return self._mistakes.get(exercise_id)

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]:
        entries = [
            entry
            for entry in self._mistakes.values()
            if include_mastered or entry.review_state is not ReviewState.MASTERED
        ]
        entries.sort(key=lambda entry: entry.created_at, reverse=True)
        return entries if limit is None else entries[:limit]

    def record_review(
        self, exercise_id: str, independent: bool, now: datetime
    ) -> MistakeEntry | None:
        entry = self._mistakes.get(exercise_id)
        if entry is None:
            return None
        state, review_count, streak, due_at = next_review(entry, independent, now)
        updated = replace(
            entry,
            review_state=state,
            review_count=review_count,
            consecutive_correct=streak,
        )
        self._mistakes[exercise_id] = updated
        if due_at is None:
            self._due_at.pop(entry.id, None)
        else:
            self._due_at[entry.id] = due_at
        return updated

    def list_review_items(self) -> list[ReviewItem]:
        items = [
            ReviewItem(mistake=entry, due_at=self._due_at[entry.id])
            for entry in self._mistakes.values()
            if entry.id in self._due_at
            and entry.review_state is not ReviewState.MASTERED
        ]
        items.sort(key=lambda item: item.due_at)
        return items

    def record_audit(
        self, op: str, result: str, now: datetime | None = None
    ) -> None:
        self._audit.append(
            AuditEntry(
                id=len(self._audit) + 1,
                op=op,
                result=result,
                created_at=now or datetime.now(timezone.utc),
            )
        )

    def list_audit(self, limit: int = 50) -> list[AuditEntry]:
        return list(reversed(self._audit))[:limit]

    def save_daily_result(self, result: DailyResult) -> None:
        self._daily[result.date] = result

    def get_daily_result(self, day: str) -> DailyResult | None:
        return self._daily.get(day)

    def close(self) -> None:
        return None


def build_repository(
    consent: Consent | None = None, path: Path | None = None
) -> Repository:
    """consent 全关 → 内存仓储；否则使用 SQLite（路径在仓库之外）。"""
    consent = consent or DEFAULT_CONSENT
    if not consent.memory and not consent.mistake_book:
        return InMemoryRepository(consent)
    from .sqlite_repo import SQLiteRepository

    return SQLiteRepository(path or default_db_path(), consent)


def load_consent(path: Path | None = None) -> Consent:
    """读取已保存的授权；数据库不存在时返回默认值且不创建文件。"""
    target = path or default_db_path()
    if not target.exists():
        return DEFAULT_CONSENT
    from .sqlite_repo import SQLiteRepository

    repository = SQLiteRepository(target)
    try:
        return repository.load_consent()
    finally:
        repository.close()
