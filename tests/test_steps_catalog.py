"""步骤元数据目录：试点加载、结构校验与未知 KC 跳过。"""
import yaml

from mathcoach.steps import CATALOG, STEP_SPECS, load_step_catalog


def test_catalog_loads_pilot_steps() -> None:
    """hs-trig 全部 15 道题都有连续步骤，且都绑定已知 KC。"""
    assert CATALOG.errors == ()
    expected = {
        f"hs-trig-{card}-e{index}"
        for card in ("001", "002", "003", "004", "005")
        for index in (1, 2, 3)
    }
    assert set(STEP_SPECS) == expected
    specs = STEP_SPECS["hs-trig-002-e2"]

    assert [spec.index for spec in specs] == [1, 2]
    assert specs[0].kc_id == "kc-hs-trig-002-f1"
    assert specs[1].kc_id == "kc-hs-trig-002-p1"
    assert specs[0].expected == "16/25"
    assert specs[1].expected == "4/5"
    assert [spec.index for spec in STEP_SPECS["hs-trig-002-e1"]] == [1]
    assert [spec.index for spec in STEP_SPECS["hs-trig-002-e3"]] == [1, 2]
    assert [spec.index for spec in STEP_SPECS["hs-trig-005-e3"]] == [1]


def _payload(kc_id: str) -> dict:
    """构造一份最小步骤文件。"""
    return {
        "version": 1,
        "exercise_id": "hs-trig-002-e2",
        "card_id": "hs-trig-002",
        "steps": [
            {
                "index": 1,
                "prompt": "测试步骤",
                "expected": "1",
                "variables": [],
                "kc_id": kc_id,
                "input_kind": "expr",
            }
        ],
    }


def test_catalog_rejects_unknown_kc(tmp_path) -> None:
    """引用未知 KC 的步骤文件会被跳过并记录错误。"""
    (tmp_path / "bad.yaml").write_text(
        yaml.safe_dump(_payload("kc-unknown"), allow_unicode=True),
        encoding="utf-8",
    )

    catalog = load_step_catalog(tmp_path)

    assert catalog.specs == {}
    assert any("未知 KC" in error for error in catalog.errors)


def test_catalog_rejects_non_contiguous_indexes(tmp_path) -> None:
    """步骤序号必须从 1 连续编号。"""
    payload = _payload("kc-hs-trig-002-f1")
    payload["steps"][0]["index"] = 2
    (tmp_path / "bad.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
    )

    catalog = load_step_catalog(tmp_path)

    assert catalog.specs == {}
    assert any("连续编号" in error for error in catalog.errors)
