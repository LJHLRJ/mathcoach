"""教学 → 出题链路编排：Gate 不通过则不出题。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..domain.models import Exercise
from .catalog import UNIT_TRIG_002
from .gate import VerifyFn
from .generation import ProblemSchema, QuestionNarrator, generate_question
from .lesson import LessonNarrator, build_lesson
from .models import ChainOutcome, QuestionOutcome, TeachingUnit


def run_teaching_chain(
    unit: TeachingUnit = UNIT_TRIG_002,
    *,
    student_state: Mapping[str, float | None] | None = None,
    pretest: Sequence[Mapping[str, object]] = (),
    lesson_narrator: LessonNarrator | None = None,
    question_narrator: QuestionNarrator | None = None,
    bank: Sequence[Exercise] = (),
    schemas: Sequence[ProblemSchema] | None = None,
    seed: int = 0,
    verify_fn: VerifyFn | None = None,
) -> ChainOutcome:
    """生成教案、过 Gate，再按覆盖 KC 出题。

    Args:
        unit: 教学单元。
        student_state: KC ID -> 掌握概率。
        pretest: 前测摘要。
        lesson_narrator: 教案叙事器；None 用模板。
        question_narrator: 题目语言实现器；None 用模板。
        bank: 可回退的已有题库题。
        schemas: 可选出题场景；None 使用内置场景。
        seed: 场景选择种子。
        verify_fn: verify 检查函数。

    Returns:
        ``ChainOutcome``；Gate 失败时 ``question.question`` 为 None。
    """
    lesson = build_lesson(
        unit,
        student_state=student_state,
        pretest=pretest,
        narrator=lesson_narrator,
        verify_fn=verify_fn,
        assessment_exercise_ids=tuple(exercise.id for exercise in bank),
    )
    if not lesson.gate.passed:
        return ChainOutcome(
            lesson=lesson,
            question=QuestionOutcome(
                question=None,
                source="none",
                fallback_reason="gate_failed",
                notes=["lesson_gate_failed"],
            ),
            covered_kc_ids=lesson.gate.covered_kc_ids,
        )
    kwargs = {}
    if schemas is not None:
        kwargs["schemas"] = schemas
    question = generate_question(
        lesson,
        seed=seed,
        bank=bank,
        question_narrator=question_narrator,
        verify_fn=verify_fn,
        **kwargs,
    )
    return ChainOutcome(
        lesson=lesson,
        question=question,
        covered_kc_ids=lesson.gate.covered_kc_ids,
    )
