"""调度改用 next_review_at 过滤，bucket 只做展示分组。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.models import ReviewState
from mathcoach.domain.spaced_repetition import Bucket, Quality
from mathcoach.memory.scheduler import build_review_queue
from mathcoach.memory.sqlite_repo import SQLiteRepository

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _seed(repo: SQLiteRepository) -> None:
    """写入两条不同到期时间的错题。"""
    repo.add_mistake(card_id="hs-001", error_type="概念不清", now=NOW - timedelta(days=3))
    repo.add_mistake(card_id="hs-002", error_type="计算失误", now=NOW - timedelta(days=1))


def test_review_queue_only_includes_due_items(tmp_path):
    """复习队列只包含已到期条目。"""
    repo = SQLiteRepository(tmp_path / "s.db")
    _seed(repo)
    queue = build_review_queue(repo, now=NOW)
    assert all(item.next_review_at <= NOW for group in queue.values() for item in group)


def test_bucket_grouping_uses_interval(tmp_path):
    """展示分组只使用三个到期桶。"""
    repo = SQLiteRepository(tmp_path / "s.db")
    _seed(repo)
    queue = build_review_queue(repo, now=NOW)
    assert set(queue.keys()) <= {Bucket.TODAY, Bucket.TOMORROW, Bucket.THREE_DAYS}


def test_update_after_review_persists_new_schedule(tmp_path, monkeypatch):
    """复习后持久化新的 SM-2 排期。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "sm2")
    repo = SQLiteRepository(tmp_path / "s.db")
    mid = repo.add_mistake(card_id="hs-001", error_type="概念不清", now=NOW)
    repo.record_review(mid, Quality.INDEPENDENT, now=NOW)
    row = repo.get_mistake(mid)
    assert row.interval_days == 3
    assert row.ease > 2.5
    assert row.next_review_at > NOW


def test_sm2_quality_review_updates_mastery_state(tmp_path, monkeypatch):
    """连续两次独立完成后转为已掌握并移出队列。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "sm2")
    repo = SQLiteRepository(tmp_path / "s.db")
    mid = repo.add_mistake(card_id="hs-001", error_type="概念不清", now=NOW)

    first = repo.record_review(mid, Quality.INDEPENDENT, now=NOW)
    assert first.review_state is ReviewState.REVIEWING
    assert first.consecutive_correct == 1
    assert repo.list_review_items()

    second = repo.record_review(
        mid, Quality.INDEPENDENT, now=NOW + timedelta(days=3)
    )
    assert second.review_state is ReviewState.MASTERED
    assert repo.list_review_items() == []


def test_sm2_bool_review_uses_sm2_schedule(tmp_path, monkeypatch):
    """布尔评分同样走 SM-2 排期。"""
    monkeypatch.setenv("MATHCOACH_SCHEDULER", "sm2")
    repo = SQLiteRepository(tmp_path / "s.db")
    mid = repo.add_mistake(card_id="hs-001", error_type="概念不清", now=NOW)
    before = repo.get_mistake(mid)

    updated = repo.record_review(mid, True, now=NOW)

    assert updated.ease > before.ease
    assert updated.interval_days == 3
    assert updated.next_review_at > NOW
