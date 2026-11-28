"""出题管线：确定性场景约束 → 模板/LLM 语言实现 → verify 终审 → 降级。

参数枚举与合法性检查全部由确定性代码完成；LLM 不计算答案。
"""
from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from string import Formatter
from typing import Protocol

from ..domain.models import Exercise, ExerciseKind
from ..verify.symbolic import SymbolicVerdict, are_equivalent
from .catalog import EXERCISE_KC
from .models import (
    GeneratedQuestion,
    LessonOutcome,
    QuestionDraft,
    QuestionOutcome,
    QuestionWording,
)
from .prompts import SYSTEM_QUESTION, build_question_prompt

VerifyFn = Callable[[str, str, frozenset[str]], SymbolicVerdict]


def default_verify(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """用验证层检查确定性生成的答案；输入受控，走离线等价检查。"""
    return are_equivalent(left, right, variables, timeout_s=None)


def _fraction(numerator: str, denominator: str) -> Fraction:
    """把参数分子/分母转成有理数。"""
    return Fraction(int(numerator), int(denominator))


def _format_fraction(value: Fraction) -> str:
    """把有理数格式化成 `p/q` 或整数。"""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _quadrant_cos(params: dict[str, str]) -> str:
    """按象限取余弦值。"""
    return _format_fraction(
        _fraction(params["cos_num"], params["cos_den"])
    )


def _valid_quadrant(params: dict[str, str]) -> bool:
    """检查 sin²+cos²=1 且余弦符号与象限一致。"""
    sin = _fraction(params["sin_num"], params["sin_den"])
    cos = _fraction(params["cos_num"], params["cos_den"])
    if sin * sin + cos * cos != 1:
        return False
    quadrant = params.get("quadrant")
    if quadrant == "第一象限":
        return cos > 0
    if quadrant == "第二象限":
        return cos < 0
    return False


def _quotient_tan(params: dict[str, str]) -> str:
    """按商数关系求正切。"""
    sin = _fraction(params["sin_num"], params["sin_den"])
    cos = _fraction(params["cos_num"], params["cos_den"])
    return _format_fraction(sin / cos)


def _valid_quotient(params: dict[str, str]) -> bool:
    """检查平方关系成立且余弦不为零。"""
    sin = _fraction(params["sin_num"], params["sin_den"])
    cos = _fraction(params["cos_num"], params["cos_den"])
    return sin * sin + cos * cos == 1 and cos != 0


@dataclass(frozen=True)
class ProblemSchema:
    """一个已审核的出题场景；参数域与推导函数都是确定性的。"""

    id: str
    kc_ids: tuple[str, ...]
    kind: ExerciseKind
    scenarios: tuple[dict[str, str], ...]
    stem_template: str
    solution_template: str
    derive: Callable[[dict[str, str]], str]
    validate: Callable[[dict[str, str]], bool]
    variables: tuple[str, ...] = ()


_TRIPLES: tuple[tuple[str, str, str, str], ...] = (
    ("3", "5", "4", "5"),
    ("5", "13", "12", "13"),
    ("8", "17", "15", "17"),
    ("7", "25", "24", "25"),
)

_QUADRANT_SCENARIOS = tuple(
    {
        "sin_num": sin_num,
        "sin_den": sin_den,
        "cos_num": signed_cos,
        "cos_den": cos_den,
        "quadrant": quadrant,
    }
    for sin_num, sin_den, cos_num, cos_den in _TRIPLES
    for quadrant, signed_cos in (
        ("第一象限", cos_num),
        ("第二象限", f"-{cos_num}"),
    )
)

_TAN_SCENARIOS = tuple(
    {
        "sin_num": sin_num,
        "sin_den": sin_den,
        "cos_num": cos_num,
        "cos_den": cos_den,
    }
    for sin_num, sin_den, cos_num, cos_den in _TRIPLES
) + tuple(
    {
        "sin_num": sin_num,
        "sin_den": sin_den,
        "cos_num": f"-{cos_num}",
        "cos_den": cos_den,
    }
    for sin_num, sin_den, cos_num, cos_den in _TRIPLES
)

SCHEMA_IDENTITY = ProblemSchema(
    id="trig-square-identity/v1",
    kc_ids=("kc-hs-trig-002-f1",),
    kind=ExerciseKind.EXPR,
    scenarios=({},),
    stem_template="化简 sin(x)**2 + cos(x)**2。",
    solution_template="由同角平方关系，sin²x + cos²x = 1。",
    derive=lambda params: "1",
    validate=lambda params: True,
    variables=("x",),
)

SCHEMA_QUADRANT = ProblemSchema(
    id="trig-quadrant-cos/v1",
    kc_ids=("kc-hs-trig-002-f1", "kc-hs-trig-002-p1"),
    kind=ExerciseKind.FILL,
    scenarios=_QUADRANT_SCENARIOS,
    stem_template=(
        "已知 sin x = {sin_num}/{sin_den}，且 x 在{quadrant}，"
        "求 cos x（用分数表示）。"
    ),
    solution_template=(
        "cos²x = 1 − sin²x，再按{quadrant}确定符号，"
        "得 cos x = {answer}。"
    ),
    derive=_quadrant_cos,
    validate=_valid_quadrant,
)

SCHEMA_TAN = ProblemSchema(
    id="trig-quotient-tan/v1",
    kc_ids=("kc-hs-trig-002-r1",),
    kind=ExerciseKind.FILL,
    scenarios=_TAN_SCENARIOS,
    stem_template=(
        "已知 sin x = {sin_num}/{sin_den}，cos x = {cos_num}/{cos_den}，"
        "求 tan x（用分数表示）。"
    ),
    solution_template=(
        "tan x = sin x / cos x = {sin_num}/{sin_den} ÷ "
        "{cos_num}/{cos_den} = {answer}。"
    ),
    derive=_quotient_tan,
    validate=_valid_quotient,
)

SCHEMAS: tuple[ProblemSchema, ...] = (
    SCHEMA_IDENTITY,
    SCHEMA_QUADRANT,
    SCHEMA_TAN,
)


def _visible_fields(template: str) -> list[str]:
    """返回题干模板中实际展示的参数名。"""
    return [
        field
        for _, field, _, _ in Formatter().parse(template)
        if field
    ]


def build_draft(
    schema: ProblemSchema, parameters: dict[str, str]
) -> QuestionDraft:
    """按 schema 与参数生成题目草稿；答案由确定性函数推导。"""
    answer = schema.derive(parameters)
    return QuestionDraft(
        schema_id=schema.id,
        kc_ids=list(schema.kc_ids),
        kind=schema.kind,
        stem=schema.stem_template.format(**parameters),
        answer=answer,
        expected_answer=answer,
        solution_outline=schema.solution_template.format(
            answer=answer, **parameters
        ),
        parameters=dict(parameters),
        visible_parameter_keys=_visible_fields(schema.stem_template),
        variables=list(schema.variables),
    )


def validate_wording(
    wording: QuestionWording, draft: QuestionDraft
) -> str | None:
    """检查语言实现是否保留参数且不泄露答案。"""
    stem = wording.stem.strip()
    solution = wording.solution_outline.strip()
    if not stem or len(stem) > 400:
        return "题干为空或过长"
    if not solution or len(solution) > 600:
        return "解析为空或过长"
    for key in draft.visible_parameter_keys:
        value = draft.parameters.get(key, "")
        if value and value not in stem:
            return f"题干缺少参数 {value}"
    if draft.answer and draft.answer in stem:
        return "题干包含答案"
    if draft.answer and draft.answer not in solution:
        return "解析未包含答案"
    return None


class QuestionClient(Protocol):
    """题目语言实现所需的最小模型客户端。"""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """返回模型原始文本，期望为 JSON。"""
        ...


class QuestionNarrator(Protocol):
    """题目语言实现接口；不参与参数与答案计算。"""

    def narrate(self, draft: QuestionDraft) -> QuestionWording:
        """把草稿改写成题目措辞。"""
        ...


class TemplateQuestionNarrator:
    """默认语言实现：直接使用确定性模板。"""

    def narrate(self, draft: QuestionDraft) -> QuestionWording:
        """返回模板措辞。"""
        return QuestionWording(
            stem=draft.stem,
            solution_outline=draft.solution_outline,
        )


class LLMQuestionNarrator:
    """只改写措辞的模型实现；结构或安全检查失败时抛异常。"""

    def __init__(self, client: QuestionClient) -> None:
        self.client = client

    def narrate(self, draft: QuestionDraft) -> QuestionWording:
        """调用模型并校验措辞。"""
        raw = self.client.complete(
            SYSTEM_QUESTION, build_question_prompt(draft)
        )
        wording = QuestionWording.model_validate_json(raw)
        reason = validate_wording(wording, draft)
        if reason is not None:
            raise ValueError(reason)
        return wording


def build_question_narrator(
    client: QuestionClient | None = None,
) -> QuestionNarrator:
    """按是否注入客户端选择 LLM 或模板语言实现。"""
    if client is None:
        return TemplateQuestionNarrator()
    return LLMQuestionNarrator(client)


def _verify_draft(
    draft: QuestionDraft, verify_fn: VerifyFn | None
) -> SymbolicVerdict:
    """调用 verify 检查答案；异常按 UNVERIFIED 处理。"""
    verify = verify_fn or default_verify
    try:
        return verify(
            draft.answer,
            draft.expected_answer,
            frozenset(draft.variables),
        )
    except Exception:
        return SymbolicVerdict.UNVERIFIED


def _bank_question(
    exercise: Exercise, kc_ids: Sequence[str]
) -> GeneratedQuestion:
    """把已有题库题转换成出题结果。"""
    return GeneratedQuestion(
        schema_id=f"bank:{exercise.id}",
        kc_ids=list(kc_ids),
        kind=exercise.kind,
        stem=exercise.stem,
        options=list(exercise.options),
        answer=exercise.answer,
        solution_outline=exercise.solution_outline,
        source="bank",
        verify_verdict="bank",
        notes=["已有题库兜底"],
    )


def _fallback(
    covered: set[str],
    bank: Sequence[Exercise],
    reason: str,
    verify_fn: VerifyFn | None,
    schemas: Sequence[ProblemSchema],
) -> QuestionOutcome:
    """按已有题库 → 预置模板题的顺序降级。"""
    for exercise in bank:
        kc_ids = EXERCISE_KC.get(exercise.id)
        if kc_ids and set(kc_ids) <= covered:
            return QuestionOutcome(
                question=_bank_question(exercise, kc_ids),
                source="bank",
                fallback_reason=reason,
                verify_verdict="bank",
                notes=["bank_fallback"],
            )
    for schema in schemas:
        if not set(schema.kc_ids) <= covered:
            continue
        for parameters in schema.scenarios:
            if not schema.validate(parameters):
                continue
            draft = build_draft(schema, parameters)
            verdict = _verify_draft(draft, verify_fn)
            if verdict is not SymbolicVerdict.EQUIVALENT:
                continue
            wording = TemplateQuestionNarrator().narrate(draft)
            return QuestionOutcome(
                question=GeneratedQuestion(
                    schema_id=draft.schema_id,
                    kc_ids=draft.kc_ids,
                    kind=draft.kind,
                    stem=wording.stem,
                    options=draft.options,
                    answer=draft.answer,
                    solution_outline=wording.solution_outline,
                    source="template",
                    verify_verdict=verdict.value,
                    notes=["template_fallback"],
                ),
                source="template",
                fallback_reason=reason,
                verify_verdict=verdict.value,
                notes=["template_fallback"],
            )
    return QuestionOutcome(
        question=None,
        source="none",
        fallback_reason=reason,
        notes=["no_fallback"],
    )


def generate_question(
    lesson: LessonOutcome,
    *,
    seed: int = 0,
    bank: Sequence[Exercise] = (),
    schemas: Sequence[ProblemSchema] = SCHEMAS,
    question_narrator: QuestionNarrator | None = None,
    verify_fn: VerifyFn | None = None,
) -> QuestionOutcome:
    """按教案覆盖的 KC 生成题目；任何失败都走降级路径。

    Args:
        lesson: 已通过 Gate 的教案结果。
        seed: 场景选择种子。
        bank: 可回退的已有题库题。
        schemas: 可选出题场景。
        question_narrator: 可选语言实现器；None 使用模板。
        verify_fn: verify 检查函数。

    Returns:
        ``QuestionOutcome``；没有可用题时 ``question`` 为 None。
    """
    covered = set(lesson.gate.covered_kc_ids)
    eligible = [
        schema for schema in schemas if set(schema.kc_ids) <= covered
    ]
    if not eligible:
        return _fallback(
            covered, bank, "kc_alignment", verify_fn, schemas
        )

    rng = random.Random(seed)
    schema = rng.choice(eligible)
    if not schema.scenarios:
        return _fallback(
            covered, bank, "parameters", verify_fn, schemas
        )
    parameters = rng.choice(schema.scenarios)
    if not schema.validate(parameters):
        return _fallback(
            covered, bank, "parameters", verify_fn, schemas
        )
    draft = build_draft(schema, parameters)
    verdict = _verify_draft(draft, verify_fn)
    if verdict is not SymbolicVerdict.EQUIVALENT:
        return _fallback(
            covered, bank, f"verify:{verdict.value}", verify_fn, schemas
        )

    wording = TemplateQuestionNarrator().narrate(draft)
    notes: list[str] = []
    if question_narrator is not None:
        try:
            candidate = question_narrator.narrate(draft)
            reason = validate_wording(candidate, draft)
            if reason is None:
                wording = candidate
            else:
                notes.append(f"wording_rejected:{reason}")
        except Exception:
            notes.append("wording_llm_unavailable")

    return QuestionOutcome(
        question=GeneratedQuestion(
            schema_id=draft.schema_id,
            kc_ids=draft.kc_ids,
            kind=draft.kind,
            stem=wording.stem,
            options=draft.options,
            answer=draft.answer,
            solution_outline=wording.solution_outline,
            source="generated",
            verify_verdict=verdict.value,
            notes=notes,
        ),
        source="generated",
        verify_verdict=verdict.value,
        notes=notes,
    )
