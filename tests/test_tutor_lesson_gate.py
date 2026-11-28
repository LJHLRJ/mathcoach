"""教学链路：模板教案与 Gate 审查。"""
from collections.abc import Mapping, Sequence

from mathcoach.tutor import (
    KC_P1_ID,
    UNIT_TRIG_002,
    LessonPlan,
    MathClaimModel,
    TeachingUnit,
    build_lesson,
    build_template_lesson,
    review_lesson,
)
from mathcoach.verify.symbolic import SymbolicVerdict


class _MissingKCNarrator:
    """模拟漏掉一个 KC 的 LLM 教案。"""

    def narrate(
        self,
        unit: TeachingUnit,
        student_state: Mapping[str, float | None],
        pretest: Sequence[Mapping[str, object]],
    ) -> LessonPlan:
        """删除 P1 的讲解、例题步骤与检查问题。"""
        lesson = build_template_lesson(unit)
        return lesson.model_copy(
            update={
                "sections": [
                    item
                    for item in lesson.sections
                    if item.kc_id != KC_P1_ID
                ],
                "worked_example": [
                    item
                    for item in lesson.worked_example
                    if item.kc_id != KC_P1_ID
                ],
                "check_questions": [
                    item
                    for item in lesson.check_questions
                    if item.kc_id != KC_P1_ID
                ],
            }
        )


class _BrokenNarrator:
    """模拟模型不可用。"""

    def narrate(
        self,
        unit: TeachingUnit,
        student_state: Mapping[str, float | None],
        pretest: Sequence[Mapping[str, object]],
    ) -> LessonPlan:
        """直接抛错，触发模板降级。"""
        raise RuntimeError("offline")


def _reject(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """模拟 verify 拒绝。"""
    return SymbolicVerdict.REJECTED


def _unverified(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """模拟 verify 无法确认。"""
    return SymbolicVerdict.UNVERIFIED


def test_template_lesson_passes_gate() -> None:
    """模板教案覆盖全部目标 KC 并通过 Gate。"""
    outcome = build_lesson(UNIT_TRIG_002)

    assert outcome.source == "template"
    assert outcome.gate.passed
    assert set(outcome.gate.covered_kc_ids) == set(UNIT_TRIG_002.kc_ids)


def test_lesson_missing_kc_fails_gate() -> None:
    """缺少任一目标 KC 的教案不能通过 Gate。"""
    lesson = _MissingKCNarrator().narrate(UNIT_TRIG_002, {}, ())
    gate = review_lesson(lesson, UNIT_TRIG_002)

    assert not gate.passed
    assert any(issue.code == "coverage" for issue in gate.issues)


def test_llm_gate_failure_falls_back_to_template() -> None:
    """LLM 教案 Gate 失败时回退模板，且最终 Gate 通过。"""
    outcome = build_lesson(UNIT_TRIG_002, narrator=_MissingKCNarrator())

    assert outcome.source == "fallback"
    assert outcome.gate.passed
    assert outcome.fallback_reasons
    assert outcome.fallback_reasons[0].startswith("gate_failed")


def test_llm_unavailable_falls_back_to_template() -> None:
    """模型不可用时回退模板教案。"""
    outcome = build_lesson(UNIT_TRIG_002, narrator=_BrokenNarrator())

    assert outcome.source == "fallback"
    assert outcome.gate.passed
    assert outcome.fallback_reasons == ["llm_unavailable"]


def test_gate_rejects_verify_rejected_claim() -> None:
    """verify 拒绝的数学断言使 Gate 失败。"""
    outcome = build_lesson(UNIT_TRIG_002, verify_fn=_reject)

    assert not outcome.gate.passed
    assert any(issue.code == "math_claim" for issue in outcome.gate.issues)


def test_gate_fails_unverified_claim() -> None:
    """无法验证的断言按硬失败处理，并标记人工复核。"""
    outcome = build_lesson(UNIT_TRIG_002, verify_fn=_unverified)

    assert not outcome.gate.passed
    assert outcome.gate.needs_manual_review
    assert any(issue.code == "math_claim" for issue in outcome.gate.issues)


def test_gate_rejects_example_leakage() -> None:
    """教案例题与待测题重复时 Gate 失败。"""
    lesson = build_template_lesson(UNIT_TRIG_002).model_copy(
        update={"example_exercise_ids": ["hs-trig-002-e1"]}
    )
    gate = review_lesson(
        lesson,
        UNIT_TRIG_002,
        assessment_exercise_ids=["hs-trig-002-e1"],
    )

    assert not gate.passed
    assert any(issue.code == "leakage" for issue in gate.issues)


def test_gate_rejects_source_ref_leakage() -> None:
    """教案引用待测题 ID 时 Gate 失败。"""
    lesson = build_template_lesson(UNIT_TRIG_002).model_copy(
        update={"source_refs": ["hs-trig-002-e1"]}
    )
    gate = review_lesson(
        lesson,
        UNIT_TRIG_002,
        assessment_exercise_ids=["hs-trig-002-e1"],
    )

    assert not gate.passed
    assert any(issue.code == "leakage" for issue in gate.issues)


def test_gate_rejects_unapproved_math_claim() -> None:
    """未登记的数学断言不能进入教案。"""
    lesson = build_template_lesson(UNIT_TRIG_002).model_copy(
        update={
            "math_claims": [
                MathClaimModel(left="1", right="2", variables=[])
            ]
        }
    )
    gate = review_lesson(lesson, UNIT_TRIG_002)

    assert not gate.passed
    assert any("已审核断言清单" in issue.message for issue in gate.issues)
