"""调度改用 next_review_at 过滤，bucket 只做展示分组。"""
from datetime import datetime, timedelta, timezone

from mathcoach.domain.spaced_repetition import Bucket, Quality
from mathcoach.memory.scheduler import build_review_queue
from mathcoach.memory.sqlite_repo import SQLiteRepository

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _seed(repo):
    repo.add_mistake(card_id="hs-001", error_type="概念不清", now=NOW - timedelta(days=3))
    repo.add_mistake(card_id="hs-002", error_type="计算失误", now=NOW - timedelta(days=1))


def test_review_queue_only_includes_due_items(tmp_path):
    repo = SQLiteRepository(tmp_path / "s.db")
    _seed(repo)
    queue = build_review_queue(repo, now=NOW)
    assert all(item.next_review_at <= NOW for group in queue.values() for item in group)


def test_bucket_grouping_uses_interval(tmp_path):
    repo = SQLiteRepository(tmp_path / "s.db")
    _seed(repo)
    queue = build_review_queue(repo, now=NOW)
    assert set(queue.keys()) <= {Bucket.TODAY, Bucket.TOMORROW, Bucket.THREE_DAYS}


def test_update_after_review_persists_new_schedule(tmp_path):
    repo = SQLiteRepository(tmp_path / "s.db")
    mid = repo.add_mistake(card_id="hs-001", error_type="概念不清", now=NOW)
    repo.record_review(mid, Quality.INDEPENDENT, now=NOW)
    row = repo.get_mistake(mid)
    assert row.interval_days == 3
    assert row.ease > 2.5
    assert row.next_review_at > NOW
