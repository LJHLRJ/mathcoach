"""教案生成：确定性模板兜底，可选 LLM 叙事；生成后立即过 Gate。

教案与出题是两条独立调用链：这里只生成教案，不生成题目。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from .catalog import KC_BY_ID
from .gate import VerifyFn, review_lesson
from .models import (
    CheckQuestion,
    LessonOutcome,
    LessonPlan,
    LessonSection,
    MathClaimModel,
    TeachingUnit,
    WorkedStep,
)
from .prompts import SYSTEM_LESSON, build_lesson_prompt

LESSON_SCHEMA_VERSION = "lesson/1"


class LessonClient(Protocol):
    """教案叙事所需的最小模型客户端。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """返回模型原始文本，期望为 JSON。"""
        ...


class LessonNarrator(Protocol):
    """教案生成接口；测试可注入确定性实现。"""

    def narrate(
        self,
        unit: TeachingUnit,
        student_state: Mapping[str, float | None],
        pretest: Sequence[Mapping[str, object]],
    ) -> LessonPlan:
        """生成教案。"""
        ...


class LLMLessonNarrator:
    """调用模型生成教案；解析与结构校验失败时抛异常，由上层降级。"""

    def __init__(self, client: LessonClient) -> None:
        self.client = client

    def narrate(
        self,
        unit: TeachingUnit,
        student_state: Mapping[str, float | None],
        pretest: Sequence[Mapping[str, object]],
    ) -> LessonPlan:
        """生成并解析教案 JSON。"""
        raw = self.client.complete(
            SYSTEM_LESSON,
            build_lesson_prompt(unit, student_state, pretest),
        )
        return LessonPlan.model_validate_json(raw)


def build_template_lesson(unit: TeachingUnit) -> LessonPlan:
    """按 KC 定义拼出确定性教案；不联网、不调用模型。"""
    sections: list[LessonSection] = []
    steps: list[WorkedStep] = []
    checks: list[CheckQuestion] = []
    common_errors: list[str] = []
    claims: list[MathClaimModel] = []
    source_refs = [unit.card_id]
    for kc_id in unit.kc_ids:
        kc = KC_BY_ID.get(kc_id)
        if kc is None:
            continue
        sections.append(
            LessonSection(
                id=f"sec-{kc.id}",
                kc_id=kc.id,
                heading=kc.name,
                text=f"{kc.statement}。{kc.explanation}",
            )
        )
        for tag in kc.required_step_tags or ["explain"]:
            steps.append(
                WorkedStep(kc_id=kc.id, tag=tag, text=kc.example)
            )
        checks.append(
            CheckQuestion(
                id=f"check-{kc.id}",
                kc_id=kc.id,
                prompt=f"用自己的话说明：{kc.statement}",
                answer=kc.statement,
            )
        )
        common_errors.extend(kc.common_errors)
        if kc.math_claim is not None:
            claims.append(kc.math_claim)
        source_refs.append(kc.id)
    return LessonPlan(
        title=f"{unit.name} · 教学",
        target_kc_ids=list(unit.kc_ids),
        sections=sections,
        worked_example=steps,
        check_questions=checks,
        common_errors=common_errors,
        referenced_kc_ids=list(unit.kc_ids),
        source_refs=source_refs,
        math_claims=claims,
        example_exercise_ids=[],
        language_level="basic",
    )


def build_lesson(
    unit: TeachingUnit,
    *,
    student_state: Mapping[str, float | None] | None = None,
    pretest: Sequence[Mapping[str, object]] = (),
    narrator: LessonNarrator | None = None,
    verify_fn: VerifyFn | None = None,
    assessment_exercise_ids: Sequence[str] = (),
) -> LessonOutcome:
    """生成教案并过 Gate；LLM 失败或 Gate 失败时回退模板教案。

    Args:
        unit: 教学单元。
        student_state: KC ID -> 掌握概率。
        pretest: 前测摘要。
        narrator: 教案叙事器；None 时只用模板。
        verify_fn: 数学断言验证函数。
        assessment_exercise_ids: 待测题 ID，用于答案泄露检查。

    Returns:
        ``LessonOutcome``；模板也失败时 ``gate.passed`` 为 False。
    """
    state = dict(student_state or {})
    template = build_template_lesson(unit)
    template_gate = review_lesson(
        template,
        unit,
        verify_fn=verify_fn,
        assessment_exercise_ids=assessment_exercise_ids,
    )
    if narrator is None:
        return LessonOutcome(
            lesson=template,
            source="template",
            gate=template_gate,
        )
    try:
        candidate = narrator.narrate(unit, state, tuple(pretest))
        candidate_gate = review_lesson(
            candidate,
            unit,
            verify_fn=verify_fn,
            assessment_exercise_ids=assessment_exercise_ids,
        )
    except Exception:
        return LessonOutcome(
            lesson=template,
            source="fallback",
            gate=template_gate,
            fallback_reasons=["llm_unavailable"],
        )
    if candidate_gate.passed:
        return LessonOutcome(
            lesson=candidate,
            source="llm",
            gate=candidate_gate,
        )
    codes = ",".join(sorted({issue.code for issue in candidate_gate.issues}))
    return LessonOutcome(
        lesson=template,
        source="fallback",
        gate=template_gate,
        fallback_reasons=[f"gate_failed:{codes}"],
    )
