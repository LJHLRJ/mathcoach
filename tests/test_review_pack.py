"""混合复习包：到期 3 + 先修缺口 1 + 拓展 1，缺口优先，自动去重。"""
from mathcoach.domain.review_pack import compose


def test_quota_3_1_1():
    """默认配额为到期 3、缺口 1、拓展 1。"""
    result = compose(
        due=["d0", "d1", "d2", "d3", "d4"],
        gaps=["g"],
        variants=["v"],
    )

    assert len(result) == 5
    assert result.count("g") == 1
    assert result.count("v") == 1
    assert sum(1 for item in result if item.startswith("d")) == 3


def test_fill_when_gap_missing():
    """缺口为空时由到期项补足总配额。"""
    result = compose(
        due=["d0", "d1", "d2", "d3", "d4"],
        gaps=[],
        variants=["v"],
    )

    assert len(result) == 5
    assert "v" in result
    assert sum(1 for item in result if item.startswith("d")) == 4


def test_fill_when_variant_missing():
    """拓展为空时由到期项补足，缺口项仍居首。"""
    result = compose(
        due=["d0", "d1", "d2", "d3", "d4"],
        gaps=["g"],
        variants=[],
    )

    assert len(result) == 5
    assert result[0] == "g"
    assert sum(1 for item in result if item.startswith("d")) == 4


def test_gap_item_placed_first():
    """缺口项排在复习包首位。"""
    result = compose(due=["d0", "d1", "d2"], gaps=["g"], variants=["v"])

    assert result[0] == "g"


def test_no_duplicates():
    """入参重复项在结果中只保留一次。"""
    result = compose(
        due=["d0", "d0", "d1", "d2", "d3"],
        gaps=["g", "g"],
        variants=["v", "v"],
    )

    assert len(result) == 5
    assert len(set(result)) == 5
