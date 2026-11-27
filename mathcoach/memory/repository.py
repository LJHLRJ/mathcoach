"""记忆仓储契约与内存实现；游客模式使用 InMemoryRepository。"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from ..config import db_path as default_db_path
from ..domain.bkt import bkt_params, initial_mastery, update_mastery
from ..domain.models import (
    AuditEntry,
    ChallengeResult,
    Consent,
    DailyResult,
    ErrorType,
    MasterySnapshot,
    MistakeEntry,
    Receipt,
    ReviewItem,
    ReviewState,
)
from ..domain.spaced_repetition import Quality, quality_from_outcome
from .scheduler import next_review

DEFAULT_CONSENT = Consent(memory=True, mistake_book=True)


class Repository(Protocol):
    """记忆仓储的最小契约。"""

    def save_consent(self, consent: Consent) -> None:
        """保存授权状态。"""
        ...

    def load_consent(self) -> Consent:
        """读取授权状态。"""
        ...

    def save_receipt(self, receipt: Receipt, exercise_id: str) -> None:
        """保存收据，并按题目 ID 关联。"""
        ...

    def update_receipt_restatement(
        self, receipt_id: str, quality: str
    ) -> bool:
        """只补写 L6 复述质量，不重复推进掌握概率；收据不存在时返回 False。"""
        ...

    def list_receipts(self, limit: int | None = 50) -> list[Receipt]:
        """按时间倒序返回收据；``limit=None`` 返回全部。"""
        ...

    def save_mistake(self, entry: MistakeEntry) -> MistakeEntry:
        """写入或覆盖错题，返回实际存储的条目。"""
        ...

    def find_mistake(self, exercise_id: str) -> MistakeEntry | None:
        """按题目 ID 取错题。"""
        ...

    def update_mistake_error_type(
        self, exercise_id: str, error_type: ErrorType
    ) -> MistakeEntry | None:
        """只更新错因，不改变复习进度与掌握概率。"""
        ...

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]:
        """按创建时间倒序返回错题。"""
        ...

    def record_review(
        self, exercise_id: str, independent: bool | Quality, now: datetime
    ) -> MistakeEntry | None:
        """登记一次复习，更新状态与到期时间。

        ``independent`` 可以是布尔值，也可以是 ``Quality``。
        """
        ...

    def list_review_items(self) -> list[ReviewItem]:
        """返回待复习项，按到期时间排序。"""
        ...

    def get_mastery(self, card_id: str) -> float | None:
        """读取掌握概率；没有记录时返回 None。"""
        ...

    def list_mastery_history(
        self, card_id: str | None = None
    ) -> list[MasterySnapshot]:
        """按记录时间升序返回掌握度快照；可按卡片过滤。"""
        ...

    def set_mastery(self, card_id: str, probability: float, now: datetime) -> None:
        """写入掌握概率。"""
        ...

    def record_mastery(
        self,
        card_id: str,
        correct: bool,
        now: datetime,
        quality: Quality | None = None,
    ) -> float:
        """按一次作答更新掌握概率并返回新值；``quality`` 区分独立与提示后答对。"""
        ...

    def record_audit(
        self, op: str, result: str, now: datetime | None = None
    ) -> None:
        """追加一条审计记录。"""
        ...

    def list_audit(self, limit: int = 50) -> list[AuditEntry]:
        """按时间倒序返回审计记录。"""
        ...

    def save_daily_result(self, result: DailyResult) -> None:
        """保存每日挑战结果。"""
        ...

    def get_daily_result(self, day: str) -> DailyResult | None:
        """按日期键取每日挑战结果。"""
        ...

    def save_challenge_result(self, result: ChallengeResult) -> ChallengeResult:
        """保存挑战赛成绩，返回带 id 的结果。"""
        ...

    def list_challenge_results(self, limit: int = 10) -> list[ChallengeResult]:
        """返回挑战赛成绩榜。"""
        ...

    def close(self) -> None:
        """关闭底层连接。"""
        ...


class InMemoryRepository:
    """游客模式：进程结束即丢弃，不触碰磁盘。"""

    def __init__(self, consent: Consent | None = None) -> None:
        """创建内存仓储；consent 缺省为记忆与错题本全开。"""
        self._consent = consent or DEFAULT_CONSENT
        self._receipts: list[Receipt] = []
        self._mistakes: dict[str, MistakeEntry] = {}
        self._due_at: dict[str, datetime] = {}
        self._audit: list[AuditEntry] = []
        self._daily: dict[str, DailyResult] = {}
        self._challenges: list[ChallengeResult] = []
        self._mastery: dict[str, float] = {}
        self._mastery_history: list[MasterySnapshot] = []

    def save_consent(self, consent: Consent) -> None:
        """保存授权状态。"""
        self._consent = consent

    def load_consent(self) -> Consent:
        """读取授权状态。"""
        return self._consent

    def save_receipt(self, receipt: Receipt, exercise_id: str) -> None:
        """追加收据并推进 BKT 掌握概率。"""
        self._receipts.append(receipt)
        # 收据代表一次通过观察，按提示层级折减后同步推进掌握概率
        quality = quality_from_outcome(True, receipt.max_hint_level)
        self.record_mastery(
            receipt.card_id,
            correct=True,
            now=receipt.created_at,
            quality=quality,
        )

    def update_receipt_restatement(
        self, receipt_id: str, quality: str
    ) -> bool:
        """只补写 L6 复述质量，不重复推进掌握概率。"""
        for index, receipt in enumerate(self._receipts):
            if receipt.id == receipt_id:
                self._receipts[index] = replace(
                    receipt, restatement_quality=quality
                )
                return True
        return False

    def list_receipts(self, limit: int | None = 50) -> list[Receipt]:
        """按时间倒序返回收据；``limit=None`` 返回全部。"""
        receipts = list(reversed(self._receipts))
        return receipts if limit is None else receipts[:limit]

    def save_mistake(self, entry: MistakeEntry) -> MistakeEntry:
        """写入错题；同题重复写入时保留原 id、创建时间与收据关联，复习进度重置。"""
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
        # 错题代表一次未通过观察，同步推进 BKT 掌握概率
        self.record_mastery(entry.card_id, correct=False, now=entry.created_at)
        return entry

    def find_mistake(self, exercise_id: str) -> MistakeEntry | None:
        """按题目 ID 取错题。"""
        return self._mistakes.get(exercise_id)

    def update_mistake_error_type(
        self, exercise_id: str, error_type: ErrorType
    ) -> MistakeEntry | None:
        """只更新错因，不改变复习进度与掌握概率。"""
        entry = self._mistakes.get(exercise_id)
        if entry is None:
            return None
        updated = replace(entry, error_type=error_type)
        self._mistakes[exercise_id] = updated
        return updated

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ) -> list[MistakeEntry]:
        """按创建时间倒序返回错题，可含或排除已掌握。"""
        entries = [
            entry
            for entry in self._mistakes.values()
            if include_mastered or entry.review_state is not ReviewState.MASTERED
        ]
        entries.sort(key=lambda entry: entry.created_at, reverse=True)
        return entries if limit is None else entries[:limit]

    def get_mastery(self, card_id: str) -> float | None:
        """读取掌握概率。"""
        return self._mastery.get(card_id)

    def set_mastery(self, card_id: str, probability: float, now: datetime) -> None:
        """写入掌握概率，截到 [0, 1]，并追加一条历史快照。"""
        value = max(0.0, min(1.0, float(probability)))
        self._mastery[card_id] = value
        self._mastery_history.append(
            MasterySnapshot(card_id, value, now)
        )

    def list_mastery_history(
        self, card_id: str | None = None
    ) -> list[MasterySnapshot]:
        """按记录时间升序返回掌握度快照；可按卡片过滤。"""
        snapshots = [
            snapshot
            for snapshot in self._mastery_history
            if card_id is None or snapshot.card_id == card_id
        ]
        snapshots.sort(key=lambda snapshot: snapshot.recorded_at)
        return snapshots

    def record_mastery(
        self,
        card_id: str,
        correct: bool,
        now: datetime,
        quality: Quality | None = None,
    ) -> float:
        """按一次作答更新 BKT 掌握概率并返回新值。"""
        prior = self.get_mastery(card_id)
        if prior is None:
            prior = initial_mastery(bkt_params())
        updated = update_mastery(prior, correct, bkt_params(), quality=quality)
        self.set_mastery(card_id, updated, now)
        return updated

    def record_review(
        self, exercise_id: str, independent: bool | Quality, now: datetime
    ) -> MistakeEntry | None:
        """登记一次复习；``Quality`` 会折成是否独立完成。"""
        if isinstance(independent, Quality):
            independent = independent is Quality.INDEPENDENT
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
        """返回未掌握且有到期时间的复习项，按到期时间排序。"""
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
        """追加审计记录，id 用当前序号。"""
        self._audit.append(
            AuditEntry(
                id=len(self._audit) + 1,
                op=op,
                result=result,
                created_at=now or datetime.now(timezone.utc),
            )
        )

    def list_audit(self, limit: int = 50) -> list[AuditEntry]:
        """按时间倒序返回审计记录。"""
        return list(reversed(self._audit))[:limit]

    def save_daily_result(self, result: DailyResult) -> None:
        """按日期键保存每日挑战结果。"""
        self._daily[result.date] = result

    def get_daily_result(self, day: str) -> DailyResult | None:
        """按日期键取每日挑战结果。"""
        return self._daily.get(day)

    def save_challenge_result(self, result: ChallengeResult) -> ChallengeResult:
        """追加挑战成绩并补上自增 id。"""
        stored = replace(result, id=len(self._challenges) + 1)
        self._challenges.append(stored)
        return stored

    def list_challenge_results(self, limit: int = 10) -> list[ChallengeResult]:
        """按分数降序、用时升序返回挑战成绩。"""
        ordered = sorted(
            self._challenges,
            key=lambda result: (-result.score, result.duration_s, result.id),
        )
        return ordered[:limit]

    def close(self) -> None:
        """内存实现无需关闭。"""
        return None


def build_repository(
    consent: Consent | None = None, path: Path | None = None
) -> Repository:
    """按授权选择仓储实现。

    记忆与错题本都关闭时用内存仓储；否则用 SQLite，默认路径在仓库之外。

    Args:
        consent: 授权状态，缺省全开。
        path: SQLite 文件路径，缺省用配置里的默认路径。

    Returns:
        ``Repository``。
    """
    consent = consent or DEFAULT_CONSENT
    if not consent.memory and not consent.mistake_book:
        return InMemoryRepository(consent)
    from .sqlite_repo import SQLiteRepository

    return SQLiteRepository(path or default_db_path(), consent)


def load_consent(path: Path | None = None) -> Consent:
    """读取已保存的授权。

    数据库不存在时返回默认值且不创建文件；读取后立即关闭连接。

    Args:
        path: SQLite 文件路径，缺省用配置里的默认路径。

    Returns:
        ``Consent``。
    """
    target = path or default_db_path()
    if not target.exists():
        return DEFAULT_CONSENT
    from .sqlite_repo import SQLiteRepository

    repository = SQLiteRepository(target)
    try:
        return repository.load_consent()
    finally:
        repository.close()
