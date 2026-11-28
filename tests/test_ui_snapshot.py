"""页面内只读快照：全量读取合并、过滤语义与委托。"""
from types import SimpleNamespace

from mathcoach.domain.models import ReviewState
from mathcoach.ui.snapshot import RepositorySnapshot


class _Repo:
    """记录各读取方法调用次数的假仓储。"""

    def __init__(self) -> None:
        self.calls = {
            "receipts": 0,
            "mistakes": 0,
            "review": 0,
            "mastery": 0,
        }
        self._receipts = [
            SimpleNamespace(id=f"r{index}") for index in range(3)
        ]
        self._mistakes = [
            SimpleNamespace(id="m1", review_state=ReviewState.REVIEWING),
            SimpleNamespace(id="m2", review_state=ReviewState.MASTERED),
        ]
        self._review_items = [SimpleNamespace(id="q1")]

    def list_receipts(self, limit: int | None = 50):
        """返回预置收据。"""
        self.calls["receipts"] += 1
        return self._receipts if limit is None else self._receipts[:limit]

    def list_mistakes(
        self, limit: int | None = 50, include_mastered: bool = True
    ):
        """返回预置错题。"""
        self.calls["mistakes"] += 1
        items = list(self._mistakes)
        return items if limit is None else items[:limit]

    def list_review_items(self):
        """返回预置复习项。"""
        self.calls["review"] += 1
        return list(self._review_items)

    def get_mastery(self, card_id: str) -> float:
        """返回固定掌握概率。"""
        self.calls["mastery"] += 1
        return 0.4

    def find_mistake(self, exercise_id: str) -> str:
        """用于验证未重写的方法会委托给原仓储。"""
        return f"live:{exercise_id}"


def test_snapshot_reads_each_collection_once() -> None:
    """一轮渲染内每个集合只读一次。"""
    repo = _Repo()
    snapshot = RepositorySnapshot(repo)

    assert [item.id for item in snapshot.list_receipts(limit=None)] == [
        "r0",
        "r1",
        "r2",
    ]
    assert len(snapshot.list_receipts(limit=1)) == 1
    assert len(snapshot.list_mistakes(limit=None)) == 2
    assert len(snapshot.list_mistakes(include_mastered=False)) == 1
    assert len(snapshot.list_review_items()) == 1

    assert repo.calls == {
        "receipts": 1,
        "mistakes": 1,
        "review": 1,
        "mastery": 0,
    }


def test_snapshot_keeps_mistake_filter_semantics() -> None:
    """已掌握过滤由快照自己完成，不重新查库。"""
    repo = _Repo()
    snapshot = RepositorySnapshot(repo)

    active = snapshot.list_mistakes(limit=None, include_mastered=False)

    assert [item.id for item in active] == ["m1"]
    assert repo.calls["mistakes"] == 1


def test_snapshot_caches_mastery_and_delegates_other_methods() -> None:
    """掌握概率同轮只查一次，其余方法委托原仓储。"""
    repo = _Repo()
    snapshot = RepositorySnapshot(repo)

    assert snapshot.get_mastery("card-1") == 0.4
    assert snapshot.get_mastery("card-1") == 0.4
    assert repo.calls["mastery"] == 1
    assert snapshot.find_mistake("e1") == "live:e1"
