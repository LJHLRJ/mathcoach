"""设置模型、校验与安全导出。"""
import json
from datetime import datetime, timezone

from mathcoach.domain.models import (
    ErrorType,
    ExerciseKind,
    Independence,
    MistakeEntry,
    Receipt,
    ReviewItem,
    Stage,
)
from mathcoach.domain.settings import (
    AppSettings,
    export_json,
    export_markdown,
    export_mistakes_csv,
    export_receipts_csv,
    settings_for_export,
)

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _receipt() -> Receipt:
    return Receipt(
        card_id="hs-001",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        duration_s=12,
        max_hint_level=1,
        goal="搞懂函数",
        independence=Independence.INDEPENDENT,
        created_at=NOW,
        exercise_id="ex-1",
    )


def _mistake() -> MistakeEntry:
    return MistakeEntry(
        id="m1",
        exercise_id="ex-1",
        card_id="hs-001",
        stage=Stage.HIGH_SCHOOL,
        course="函数与导数",
        exercise_type=ExerciseKind.CHOICE,
        stem="题干",
        user_answer="错答",
        correct_answer="正确",
        error_type=ErrorType.CONCEPT,
        max_hint_level=1,
        created_at=NOW,
    )


def test_settings_round_trip_and_invalid_limit():
    settings = AppSettings.from_mapping(
        {"ai_enabled": True, "daily_review_limit": 7}
    )
    assert settings.to_mapping() == {
        "ai_enabled": True,
        "daily_review_limit": 7,
    }
    assert AppSettings.from_mapping({"daily_review_limit": -3}).daily_review_limit == 0
    assert AppSettings.from_mapping({"daily_review_limit": "bad"}).daily_review_limit == 0


def test_settings_export_allowlist_drops_secret_keys():
    exported = settings_for_export(
        {"api_key": "sk-secret", "daily_review_limit": 5, "unknown": "x"}
    )
    assert exported == {"ai_enabled": False, "daily_review_limit": 5}
    assert "sk-secret" not in json.dumps(exported)


def test_exports_exclude_secret_settings():
    receipt = _receipt()
    mistake = _mistake()
    review = ReviewItem(mistake=mistake, due_at=NOW)
    settings = {"api_key": "sk-secret", "daily_review_limit": 5}
    json_text = export_json(
        receipts=[receipt],
        mistakes=[mistake],
        review_items=[review],
        settings=settings,
        now=NOW,
    )
    csv_text = export_receipts_csv([receipt]) + export_mistakes_csv([mistake])
    markdown = export_markdown(
        receipts=[receipt], mistakes=[mistake], settings=settings, now=NOW
    )

    payload = json.loads(json_text)
    assert payload["settings"] == {"ai_enabled": False, "daily_review_limit": 5}
    assert "sk-secret" not in json_text
    assert "sk-secret" not in csv_text
    assert "sk-secret" not in markdown
    assert payload["receipts"][0]["card_id"] == "hs-001"
    assert payload["mistakes"][0]["error_type"] == "概念不清"
