"""KC 目录：从 content/kc/*.yaml 加载并校验引用。"""
from pathlib import Path

import pytest
import yaml

from mathcoach.content.loader import load_content
from mathcoach.tutor import (
    EXERCISE_KC,
    KC_BY_ID,
    KC_F1,
    KCCatalogError,
    UNIT_TRIG_002,
    load_catalog,
)

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def _write_bundle(path: Path, data: dict) -> None:
    """写入一个 KC YAML 文件。"""
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )


def test_catalog_loads_from_content() -> None:
    """内置 content/kc 目录包含教学单元与题目映射。"""
    assert set(UNIT_TRIG_002.kc_ids) <= set(KC_BY_ID)
    assert UNIT_TRIG_002.card_id == "hs-trig-002"
    catalog = load_catalog()
    assert "hs-trig-002-e3" in catalog.exercise_kc
    assert {
        "unit-hs-trig-001",
        "unit-hs-trig-003",
        "unit-hs-trig-004",
        "unit-hs-trig-005",
    } <= set(catalog.units)


def test_catalog_ids_exist_in_content() -> None:
    """KC 目录引用的知识点与题目都能在题库中找到。"""
    cards, _ = load_content(CONTENT_ROOT, strict=False)
    card_ids = {card.id for card in cards}
    exercise_ids = {
        exercise.id for card in cards for exercise in card.exercises
    }

    assert {
        kc.knowledge_point_id for kc in KC_BY_ID.values()
    } <= card_ids
    assert set(EXERCISE_KC) <= exercise_ids


def test_catalog_rejects_unknown_kc_reference(tmp_path: Path) -> None:
    """教学单元引用不存在的 KC 时加载失败。"""
    unit = UNIT_TRIG_002.model_copy(
        update={
            "kc_ids": ["kc-missing"],
            "approved_prerequisite_kc_ids": [],
        }
    )
    _write_bundle(
        tmp_path / "bad.yaml",
        {
            "version": 1,
            "unit": unit.model_dump(),
            "kcs": [KC_F1.model_dump()],
            "exercise_kc": {},
        },
    )

    with pytest.raises(KCCatalogError):
        load_catalog(tmp_path)


def test_catalog_loads_valid_single_kc_bundle(tmp_path: Path) -> None:
    """最小合法目录可以加载。"""
    unit = UNIT_TRIG_002.model_copy(
        update={
            "kc_ids": [KC_F1.id],
            "approved_prerequisite_kc_ids": [],
        }
    )
    _write_bundle(
        tmp_path / "valid.yaml",
        {
            "version": 1,
            "unit": unit.model_dump(),
            "kcs": [KC_F1.model_dump()],
            "exercise_kc": {"hs-trig-002-e1": [KC_F1.id]},
        },
    )

    catalog = load_catalog(tmp_path)

    assert catalog.units[unit.id].kc_ids == [KC_F1.id]
    assert catalog.exercise_kc["hs-trig-002-e1"] == (KC_F1.id,)
