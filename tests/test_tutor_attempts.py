"""教学后作答回流：KC 掌握概率的权重与边界。"""
from pathlib import Path

from mathcoach.domain.bkt import initial_mastery, update_mastery
from mathcoach.domain.spaced_repetition import Quality
from mathcoach.tutor import (
    KC_F1_ID,
    KCMasteryStore,
    MAX_IMMEDIATE_DROP,
    TeachingAttempt,
    apply_attempt,
    shadow_db_path,
)


def test_pretest_does_not_update_formal_mastery() -> None:
    """教学前测默认不更新正式 BKT。"""
    updates = apply_attempt(
        {KC_F1_ID: 0.4},
        TeachingAttempt(
            kc_ids=(KC_F1_ID,), correct=True, source="pretest"
        ),
    )

    assert updates[KC_F1_ID] == 0.4


def test_pretest_can_be_counted_with_lower_weight() -> None:
    """显式允许时，前测按较低权重进入 BKT。"""
    prior = 0.4
    updates = apply_attempt(
        {KC_F1_ID: prior},
        TeachingAttempt(
            kc_ids=(KC_F1_ID,), correct=True, source="pretest"
        ),
        count_pretest=True,
    )
    full = update_mastery(prior, True)

    assert prior < updates[KC_F1_ID] < full


def test_immediate_wrong_drop_is_capped() -> None:
    """教学后即时答错只允许有限跌幅。"""
    prior = 0.8
    updates = apply_attempt(
        {KC_F1_ID: prior},
        TeachingAttempt(
            kc_ids=(KC_F1_ID,), correct=False, source="immediate"
        ),
    )

    assert updates[KC_F1_ID] >= prior - MAX_IMMEDIATE_DROP - 1e-9


def test_delayed_wrong_uses_full_bkt_update() -> None:
    """延迟复习答错按完整 BKT 更新。"""
    prior = 0.8
    updates = apply_attempt(
        {KC_F1_ID: prior},
        TeachingAttempt(
            kc_ids=(KC_F1_ID,), correct=False, source="delayed"
        ),
    )

    assert abs(updates[KC_F1_ID] - update_mastery(prior, False)) < 1e-9


def test_hinted_correct_has_weaker_gain() -> None:
    """提示后答对的掌握增益弱于独立答对。"""
    prior = 0.4
    hinted = apply_attempt(
        {KC_F1_ID: prior},
        TeachingAttempt(
            kc_ids=(KC_F1_ID,),
            correct=True,
            quality=Quality.HINTED,
            source="immediate",
        ),
    )
    independent = apply_attempt(
        {KC_F1_ID: prior},
        TeachingAttempt(
            kc_ids=(KC_F1_ID,), correct=True, source="immediate"
        ),
    )

    assert prior < hinted[KC_F1_ID] < independent[KC_F1_ID]


def test_shadow_store_persists_in_separate_db(tmp_path: Path) -> None:
    """影子掌握值写入独立库，不创建正式库。"""
    path = tmp_path / "kc-shadow.sqlite3"
    store = KCMasteryStore(path)
    try:
        store.record(
            TeachingAttempt(
                kc_ids=(KC_F1_ID,), correct=True, source="immediate"
            )
        )
        value = store.get(KC_F1_ID)
        assert value is not None
        assert value > initial_mastery()
        assert store.sample_size(KC_F1_ID) == 1
    finally:
        store.close()

    reopened = KCMasteryStore(path)
    try:
        assert reopened.get(KC_F1_ID) == value
    finally:
        reopened.close()
    assert not (tmp_path / "mathcoach.sqlite3").exists()


def test_shadow_store_loads_probabilities_and_samples_together(
    tmp_path: Path,
) -> None:
    """批量读取一次返回概率与样本量。"""
    store = KCMasteryStore(tmp_path / "kc-shadow.sqlite3")
    try:
        store.set(KC_F1_ID, 0.42, 3)
        mastery, samples = store.load_with_samples()
    finally:
        store.close()

    assert mastery == {KC_F1_ID: 0.42}
    assert samples == {KC_F1_ID: 3}


def test_shadow_store_pretest_is_not_persisted(tmp_path: Path) -> None:
    """前测默认不写入影子表。"""
    store = KCMasteryStore(tmp_path / "kc-shadow.sqlite3")
    try:
        store.record(
            TeachingAttempt(
                kc_ids=(KC_F1_ID,), correct=True, source="pretest"
            )
        )
        assert store.get(KC_F1_ID) is None
        assert store.sample_size(KC_F1_ID) == 0
    finally:
        store.close()


def test_shadow_db_path_is_separate_from_formal_db(
    tmp_path: Path, monkeypatch
) -> None:
    """影子库与正式库文件名不同。"""
    formal = tmp_path / "mathcoach.sqlite3"
    monkeypatch.setenv("MATHCOACH_DB", str(formal))

    shadow = shadow_db_path()

    assert shadow.name == "kc-shadow.sqlite3"
    assert shadow != formal

