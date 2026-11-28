"""出题管线：verify 终审、KC 对齐与降级路径。"""
from mathcoach.domain.models import Exercise, ExerciseKind
from mathcoach.tutor import (
    KC_F1_ID,
    SCHEMA_TAN,
    UNIT_TRIG_002,
    QuestionDraft,
    QuestionWording,
    TeachingUnit,
    build_lesson,
    generate_question,
)
from mathcoach.verify.symbolic import SymbolicVerdict


def _accept(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """模拟 verify 通过。"""
    return SymbolicVerdict.EQUIVALENT


def _reject(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """模拟 verify 拒绝。"""
    return SymbolicVerdict.REJECTED


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


class _BrokenQuestionNarrator:
    """模拟题目语言实现模型不可用。"""

    def narrate(self, draft: QuestionDraft) -> QuestionWording:
        """直接抛错，触发模板措辞。"""
        raise RuntimeError("offline")


class _LeakNarrator:
    """模拟把答案写进题干的错误措辞。"""

    def narrate(self, draft: QuestionDraft) -> QuestionWording:
        """返回包含答案的题干。"""
        return QuestionWording(
            stem=f"答案是 {draft.answer}",
            solution_outline=draft.answer,
        )


class _EchoNarrator:
    """模拟保留参数、不泄露答案的正常措辞。"""

    def narrate(self, draft: QuestionDraft) -> QuestionWording:
        """原样返回模板措辞。"""
        return QuestionWording(
            stem=draft.stem,
            solution_outline=draft.solution_outline,
        )


def test_generated_question_passes_verify_and_kc_alignment() -> None:
    """生成题通过 verify，且 KC 集合是教学覆盖集合的子集。"""
    lesson = build_lesson(UNIT_TRIG_002)
    outcome = generate_question(lesson, seed=0)

    assert outcome.source == "generated"
    assert outcome.question is not None
    assert outcome.verify_verdict == "equivalent"
    assert set(outcome.question.kc_ids) <= set(lesson.gate.covered_kc_ids)


def test_verify_rejection_falls_back_to_bank() -> None:
    """verify 拒绝时回退已有题库题。"""
    lesson = build_lesson(UNIT_TRIG_002)
    outcome = generate_question(
        lesson, seed=0, bank=_bank(), verify_fn=_reject
    )

    assert outcome.source == "bank"
    assert outcome.question is not None
    assert outcome.question.source == "bank"
    assert outcome.fallback_reason.startswith("verify:")


def test_kc_alignment_failure_returns_no_question() -> None:
    """出题 KC 不在教学覆盖集合内时不得生成。"""
    unit_f1 = TeachingUnit(
        id="unit-f1-only",
        name="只教平方关系",
        card_id="hs-trig-002",
        kc_ids=[KC_F1_ID],
    )
    lesson = build_lesson(unit_f1)
    outcome = generate_question(
        lesson,
        seed=0,
        bank=(),
        schemas=(SCHEMA_TAN,),
        verify_fn=_accept,
    )

    assert outcome.question is None
    assert outcome.source == "none"
    assert outcome.fallback_reason == "kc_alignment"


def test_question_wording_llm_failure_uses_template() -> None:
    """题目措辞模型失败时保留模板措辞，不阻断出题。"""
    lesson = build_lesson(UNIT_TRIG_002)
    outcome = generate_question(
        lesson,
        seed=0,
        question_narrator=_BrokenQuestionNarrator(),
        verify_fn=_accept,
    )

    assert outcome.source == "generated"
    assert outcome.question is not None
    assert "wording_llm_unavailable" in outcome.notes


def test_question_wording_answer_leak_is_rejected() -> None:
    """题干包含答案时拒绝 LLM 措辞，改用模板。"""
    lesson = build_lesson(UNIT_TRIG_002)
    outcome = generate_question(
        lesson,
        seed=0,
        question_narrator=_LeakNarrator(),
        verify_fn=_accept,
    )

    assert outcome.source == "generated"
    assert any(
        note.startswith("wording_rejected") for note in outcome.notes
    )


def test_valid_question_wording_is_accepted() -> None:
    """保留可见参数且不泄露答案的措辞可以通过校验。"""
    lesson = build_lesson(UNIT_TRIG_002)
    outcome = generate_question(
        lesson,
        seed=0,
        question_narrator=_EchoNarrator(),
        verify_fn=_accept,
    )

    assert outcome.source == "generated"
    assert outcome.notes == []


def test_generated_rejection_falls_back_to_template_question() -> None:
    """没有题库可退时，verify 拒绝后回退预置模板题。"""
    lesson = build_lesson(UNIT_TRIG_002)
    calls = {"count": 0}

    def _reject_then_accept(
        left: str, right: str, variables: frozenset[str]
    ) -> SymbolicVerdict:
        """第一次拒绝，后续通过，用于区分生成题与模板题。"""
        calls["count"] += 1
        if calls["count"] == 1:
            return SymbolicVerdict.REJECTED
        return SymbolicVerdict.EQUIVALENT

    outcome = generate_question(
        lesson, seed=0, bank=(), verify_fn=_reject_then_accept
    )

    assert outcome.source == "template"
    assert outcome.question is not None
    assert outcome.question.source == "template"
    assert outcome.fallback_reason.startswith("verify:")
