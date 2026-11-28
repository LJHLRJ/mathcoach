"""交互延迟优化：周报叙事按需生成、小测表单与片段配置。"""
import json
from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mathcoach.domain.models import (
    ExerciseKind,
    Independence,
    Receipt,
    Stage,
)

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
COMPONENTS_PATH = (
    Path(__file__).resolve().parents[1]
    / "mathcoach"
    / "ui"
    / "components.py"
)


class _EchoProvider:
    """把统计层结论原样回显的假客户端，用于统计调用次数。"""

    calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        type(self).calls += 1
        payload = json.loads(user_prompt)
        return json.dumps(
            {
                "sections": [
                    {
                        "conclusion_id": item["conclusion_id"],
                        "text": item["statement"],
                    }
                    for item in payload["conclusions"]
                ]
            },
            ensure_ascii=False,
        )


def test_weekly_narrative_is_generated_on_demand(
    tmp_path, monkeypatch
) -> None:
    """进入周报不调用模型；点击按钮才生成，缓存后不重复调用。"""
    monkeypatch.setenv(
        "MATHCOACH_DB", str(tmp_path / "mathcoach.sqlite3")
    )
    _EchoProvider.calls = 0
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()

    repository = at.session_state["repository"]
    repository.save_receipt(
        Receipt(
            id="r1",
            card_id="hs-trig-002",
            stage=Stage.HIGH_SCHOOL,
            course="三角函数",
            exercise_type=ExerciseKind.CHOICE,
            duration_s=10,
            max_hint_level=0,
            goal="练",
            independence=Independence.INDEPENDENT,
            created_at=datetime.now(timezone.utc),
        ),
        "hs-trig-002-e1",
    )
    at.session_state["provider"] = _EchoProvider()

    at.selectbox[1].select("周报").run()

    assert not at.exception
    assert _EchoProvider.calls == 0
    assert any(
        button.label == "生成 / 刷新 AI 叙事"
        for button in at.button
    )

    next(
        button
        for button in at.button
        if button.label == "生成 / 刷新 AI 叙事"
    ).click().run()

    assert not at.exception
    assert _EchoProvider.calls == 1
    assert any(
        "叙事由模型改写" in caption.value
        for caption in at.caption
    )

    at.run()

    assert _EchoProvider.calls == 1


def test_latency_guards_are_wired() -> None:
    """表单、片段与缓存入口在源码中保持接线。"""
    source = APP_PATH.read_text(encoding="utf-8")
    components = COMPONENTS_PATH.read_text(encoding="utf-8")

    assert "@st.fragment\ndef _render_step_guide" in source
    assert "@st.fragment\ndef _render_visual_block" in source
    assert 'st.form(\n                "quiz_answer_form"' in source
    assert "rerun_fragment()" in source
    assert 'st.rerun(scope="fragment")' in components
    assert 'WEEKLY_NARRATIVE_KEY = "weekly_report_narrative"' in source
    assert "RepositorySnapshot(st.session_state.repository)" in source
    assert "load_with_samples()" in source
