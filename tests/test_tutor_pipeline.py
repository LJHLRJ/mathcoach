"""教学 → 出题链路：Gate 门控、LLM 降级与 verify 降级。"""
from collections.abc import Mapping, Sequence

from mathcoach.domain.models import Exercise, ExerciseKind
from mathcoach.tutor import (
    UNIT_TRIG_002,
    LessonPlan,
    TeachingUnit,
    run_teaching_chain,
)
from mathcoach.verify.symbolic import SymbolicVerdict


class _BrokenLessonNarrator:
    """模拟教案模型不可用。"""

    def narrate(
        self,
        unit: TeachingUnit,
        student_state: Mapping[str, float | None],
        pretest: Sequence[Mapping[str, object]],
    ) -> LessonPlan:
        """直接抛错。"""
        raise RuntimeError("offline")


def _bank() -> list[Exercise]:
    """构造一条可回退的已有题库题。"""
    return [
        Exercise(
            id="hs-trig-002-e1",
            card_id="hs-trig-002",
            kind=ExerciseKind.CHOICE,
            stem="下列恒等式正确的是（ ）",
            answer="sin²x+cos²x=1",
            solution_outline="由同角平方关系得到。",
            options=("sin²x+cos²x=1", "sin²x−cos²x=1"),
        )
    ]


def test_full_chain_returns_generated_question() -> None:
    """默认链路生成教案并通过 Gate，随后生成带 KC 标注的题目。"""
    outcome = run_teaching_chain(seed=0)

    assert outcome.lesson.gate.passed
    assert outcome.lesson.source == "template"
    assert outcome.question.source == "generated"
    assert outcome.question.question is not None
    assert outcome.question.verify_verdict == "equivalent"
    assert set(outcome.question.question.kc_ids) <= set(
        outcome.covered_kc_ids
    )


def test_llm_unavailable_lesson_falls_back_and_continues() -> None:
    """教案模型不可用时回退模板，并继续出题。"""
    outcome = run_teaching_chain(
        seed=0, lesson_narrator=_BrokenLessonNarrator()
    )

    assert outcome.lesson.source == "fallback"
    assert outcome.lesson.fallback_reasons == ["llm_unavailable"]
    assert outcome.lesson.gate.passed
    assert outcome.question.question is not None


def test_gate_failure_stops_question_generation() -> None:
    """模板教案也无法覆盖目标 KC 时，Gate 失败并停止出题。"""
    unit = TeachingUnit(
        id="unit-unknown",
        name="未登记单元",
        card_id="hs-trig-002",
        kc_ids=["kc-unknown"],
    )
    outcome = run_teaching_chain(unit, seed=0)

    assert not outcome.lesson.gate.passed
    assert outcome.question.question is None
    assert outcome.question.fallback_reason == "gate_failed"


def test_chain_verify_rejection_falls_back_to_bank() -> None:
    """教案断言通过、生成题被 verify 拒绝时回退题库题。"""
    calls = {"count": 0}

    def _accept_lesson_reject_question(
        left: str, right: str, variables: frozenset[str]
    ) -> SymbolicVerdict:
        """第一次调用用于教案断言，后续用于生成题。"""
        calls["count"] += 1
        if calls["count"] == 1:
            return SymbolicVerdict.EQUIVALENT
        return SymbolicVerdict.REJECTED

    outcome = run_teaching_chain(
        seed=0,
        bank=_bank(),
        verify_fn=_accept_lesson_reject_question,
    )

    assert outcome.lesson.gate.passed
    assert outcome.question.source == "bank"
    assert outcome.question.question is not None
    assert outcome.question.fallback_reason.startswith("verify:")
