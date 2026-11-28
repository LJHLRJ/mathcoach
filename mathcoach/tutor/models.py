"""教学链路模型：KC、教案、Gate 结果、生成题与链路结果。

只定义数据结构与序列化形状，不包含判定、调度或 BKT 写入。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import ExerciseKind


class MathClaimModel(BaseModel):
    """教案中一条可交给 verify 复核的数学断言。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    left: str
    right: str
    variables: list[str] = Field(default_factory=list)


class KnowledgeComponent(BaseModel):
    """知识组件（KC）：解题时实际调用的最小认知单元。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    knowledge_point_id: str
    kind: Literal["fact", "rule", "procedure", "strategy"]
    name: str
    statement: str
    explanation: str
    example: str
    common_errors: list[str] = Field(default_factory=list)
    required_step_tags: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    math_claim: MathClaimModel | None = None


class TeachingUnit(BaseModel):
    """一次教学单元：一张知识点卡上的 1–3 个 KC。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    card_id: str
    kc_ids: list[str]
    approved_prerequisite_kc_ids: list[str] = Field(default_factory=list)


class LessonSection(BaseModel):
    """教案中的一段讲解，必须绑定到一个 KC。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kc_id: str
    heading: str
    text: str


class WorkedStep(BaseModel):
    """例题中的一步，标签用于 Gate 检查步骤完整性。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kc_id: str
    tag: str
    text: str


class CheckQuestion(BaseModel):
    """教案内检查问题；不是正式测评题。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kc_id: str
    prompt: str
    answer: str


class LessonPlan(BaseModel):
    """结构化教案；LLM 输出必须符合此 schema。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["lesson/1"] = "lesson/1"
    title: str
    target_kc_ids: list[str]
    sections: list[LessonSection]
    worked_example: list[WorkedStep]
    check_questions: list[CheckQuestion]
    common_errors: list[str] = Field(default_factory=list)
    referenced_kc_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    math_claims: list[MathClaimModel] = Field(default_factory=list)
    example_exercise_ids: list[str] = Field(default_factory=list)
    language_level: Literal["basic", "intermediate"] = "basic"


class GateIssue(BaseModel):
    """Gate 的一条失败项。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class GateResult(BaseModel):
    """结构审查结果；``passed`` 为 False 时不得进入出题。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    covered_kc_ids: list[str]
    issues: list[GateIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    needs_manual_review: bool = False


class LessonOutcome(BaseModel):
    """教案生成结果，包含来源与 Gate。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lesson: LessonPlan
    source: Literal["template", "llm", "fallback"]
    gate: GateResult
    fallback_reasons: list[str] = Field(default_factory=list)


class QuestionWording(BaseModel):
    """题目语言实现结果；只允许改措辞，不允许改答案。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stem: str
    solution_outline: str


class QuestionDraft(BaseModel):
    """确定性出题管线生成的题目草稿。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_id: str
    kc_ids: list[str]
    kind: ExerciseKind
    stem: str
    answer: str
    expected_answer: str
    solution_outline: str
    parameters: dict[str, str] = Field(default_factory=dict)
    visible_parameter_keys: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)


class GeneratedQuestion(BaseModel):
    """可进入测评的题目；必须带 KC 标注与来源。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_id: str
    kc_ids: list[str]
    kind: ExerciseKind
    stem: str
    options: list[str] = Field(default_factory=list)
    answer: str
    solution_outline: str
    source: Literal["generated", "bank", "template"]
    verify_verdict: str
    notes: list[str] = Field(default_factory=list)


class QuestionOutcome(BaseModel):
    """出题结果，包含降级原因与验证结论。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: GeneratedQuestion | None
    source: Literal["generated", "bank", "template", "none"]
    fallback_reason: str = ""
    verify_verdict: str = ""
    notes: list[str] = Field(default_factory=list)


class ChainOutcome(BaseModel):
    """教学 → 出题的完整链路结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lesson: LessonOutcome
    question: QuestionOutcome
    covered_kc_ids: list[str]
