"""教案结构审查 Gate：确定性检查优先，无法验证的断言硬失败并标记人工复核。

Gate 不生成内容、不改教案；只给出通过/失败与问题清单。
"""
from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from ..verify.symbolic import SymbolicVerdict, are_equivalent
from .catalog import KC_BY_ID
from .models import GateIssue, GateResult, LessonPlan, TeachingUnit

VerifyFn = Callable[[str, str, frozenset[str]], SymbolicVerdict]

MAX_SECTION_CHARS = 600
MAX_SENTENCE_CHARS = 80
_SENTENCE_SPLIT = re.compile(r"[。！？!?；;]")


def default_verify(
    left: str, right: str, variables: frozenset[str]
) -> SymbolicVerdict:
    """用验证层做离线等价检查；输入来自受控模板，不设子进程超时。"""
    return are_equivalent(left, right, variables, timeout_s=None)


def _long_sentence(text: str) -> bool:
    """文本中是否存在超过长度上限的句子。"""
    return any(
        len(part.strip()) > MAX_SENTENCE_CHARS
        for part in _SENTENCE_SPLIT.split(text)
        if part.strip()
    )


def review_lesson(
    lesson: LessonPlan,
    unit: TeachingUnit,
    *,
    verify_fn: VerifyFn | None = None,
    assessment_exercise_ids: Sequence[str] = (),
) -> GateResult:
    """审查教案是否覆盖目标 KC、是否跳步、是否越界引用。

    Args:
        lesson: 待审查教案。
        unit: 教学单元，给出目标 KC 与允许的先修 KC。
        verify_fn: 数学断言验证函数；缺省走 ``verify`` 的离线等价检查。
        assessment_exercise_ids: 即将用于正式测评的题目 ID，用于查答案泄露。

    Returns:
        ``GateResult``；``passed`` 为 False 时不得进入出题。
    """
    verify = verify_fn or default_verify
    issues: list[GateIssue] = []
    warnings: list[str] = []
    covered: list[str] = []
    target = set(unit.kc_ids)
    allowed = target | set(unit.approved_prerequisite_kc_ids)

    missing_targets = target - set(lesson.target_kc_ids)
    if missing_targets:
        issues.append(
            GateIssue(
                code="target",
                message="教案目标缺少 KC：" + ", ".join(sorted(missing_targets)),
            )
        )

    for kc_id in unit.kc_ids:
        kc = KC_BY_ID.get(kc_id)
        if kc is None:
            issues.append(
                GateIssue(code="unknown_kc", message=f"未登记的 KC：{kc_id}")
            )
            continue
        has_section = any(
            section.kc_id == kc_id for section in lesson.sections
        )
        required_tags = set(kc.required_step_tags)
        has_step = any(
            step.kc_id == kc_id
            and (not required_tags or step.tag in required_tags)
            for step in lesson.worked_example
        )
        has_check = any(
            question.kc_id == kc_id for question in lesson.check_questions
        )
        if has_section and has_step and has_check:
            covered.append(kc_id)
        else:
            issues.append(
                GateIssue(
                    code="coverage",
                    message=(
                        f"{kc.name} 覆盖不完整："
                        f"讲解={has_section}，例题步骤={has_step}，"
                        f"检查问题={has_check}"
                    ),
                )
            )

    used_kc_ids = {
        item.kc_id
        for item in (
            list(lesson.sections)
            + list(lesson.worked_example)
            + list(lesson.check_questions)
        )
    } | set(lesson.referenced_kc_ids)
    unknown = used_kc_ids - allowed
    if unknown:
        issues.append(
            GateIssue(
                code="prerequisite",
                message="引用了未审核的 KC：" + ", ".join(sorted(unknown)),
            )
        )

    for section in lesson.sections:
        if len(section.text) > MAX_SECTION_CHARS:
            issues.append(
                GateIssue(
                    code="language",
                    message=f"讲解段 {section.id} 超过 {MAX_SECTION_CHARS} 字",
                )
            )
        if _long_sentence(section.text):
            issues.append(
                GateIssue(
                    code="language",
                    message=(
                        f"讲解段 {section.id} 存在超过 "
                        f"{MAX_SENTENCE_CHARS} 字的句子"
                    ),
                )
            )

    leaked = set(lesson.example_exercise_ids) & set(
        assessment_exercise_ids
    )
    if leaked:
        issues.append(
            GateIssue(
                code="leakage",
                message="教案例题与待测题重复：" + ", ".join(sorted(leaked)),
            )
        )
    leaked_refs = set(lesson.source_refs) & set(assessment_exercise_ids)
    if leaked_refs:
        issues.append(
            GateIssue(
                code="leakage",
                message=(
                    "教案引用与待测题重复："
                    + ", ".join(sorted(leaked_refs))
                ),
            )
        )

    for question in lesson.check_questions:
        if not question.answer.strip():
            issues.append(
                GateIssue(
                    code="check_question",
                    message=f"检查问题 {question.id} 缺少参考答案",
                )
            )

    if not lesson.common_errors:
        warnings.append("教案未列出常见误区")

    needs_manual = False
    allowed_claims = {
        (
            kc.math_claim.left,
            kc.math_claim.right,
            tuple(sorted(kc.math_claim.variables)),
        )
        for kc_id in unit.kc_ids
        if (kc := KC_BY_ID.get(kc_id)) is not None
        and kc.math_claim is not None
    }
    for index, claim in enumerate(lesson.math_claims, start=1):
        key = (
            claim.left,
            claim.right,
            tuple(sorted(claim.variables)),
        )
        if key not in allowed_claims:
            issues.append(
                GateIssue(
                    code="math_claim",
                    message=f"数学断言 {index} 不在已审核断言清单内",
                )
            )
            continue
        try:
            verdict = verify(
                claim.left, claim.right, frozenset(claim.variables)
            )
        except Exception:
            verdict = SymbolicVerdict.UNVERIFIED
        if verdict is SymbolicVerdict.REJECTED:
            issues.append(
                GateIssue(
                    code="math_claim",
                    message=f"数学断言 {index} 未通过安全白名单",
                )
            )
        elif verdict is SymbolicVerdict.NOT_EQUIVALENT:
            issues.append(
                GateIssue(
                    code="math_claim",
                    message=f"数学断言 {index} 不成立",
                )
            )
        elif verdict is SymbolicVerdict.UNVERIFIED:
            needs_manual = True
            issues.append(
                GateIssue(
                    code="math_claim",
                    message=f"数学断言 {index} 无法自动验证，需人工复核",
                )
            )

    return GateResult(
        passed=not issues,
        covered_kc_ids=covered,
        issues=issues,
        warnings=warnings,
        needs_manual_review=needs_manual,
    )
