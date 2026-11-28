"""教学与出题提示词：两个环节使用不同的系统提示，不合并调用。"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from .catalog import KC_BY_ID
from .models import QuestionDraft, TeachingUnit

LESSON_PROMPT_VERSION = "tutor-lesson-1"
QUESTION_PROMPT_VERSION = "tutor-question-1"

SYSTEM_LESSON = (
    f"prompt_version={LESSON_PROMPT_VERSION} 你是数学教案编写助手。"
    "只输出严格 JSON，不输出 Markdown。"
    "必须覆盖输入中的每一个目标 KC；每个 KC 至少包含一段讲解、"
    "一个带 KC 标签的例题步骤和一个检查问题。"
    "不得引入未审核的 KC；不得编造题目 ID；"
    "数学断言只能使用输入给出的可验证断言。"
)

SYSTEM_QUESTION = (
    f"prompt_version={QUESTION_PROMPT_VERSION} 你只改写题目的语言表达。"
    "不得改变参数、条件、答案或解题步骤；"
    "不得在题干中泄露答案；"
    "只输出 JSON，字段为 stem 与 solution_outline。"
)


def build_lesson_prompt(
    unit: TeachingUnit,
    student_state: Mapping[str, float | None],
    pretest: Sequence[Mapping[str, object]],
) -> str:
    """构造教案生成输入；只含 KC 定义、学生状态与前测摘要。

    Args:
        unit: 教学单元。
        student_state: KC ID -> 当前掌握概率；None 表示未观测。
        pretest: 前测摘要，只含 KC 与是否正确。

    Returns:
        可直接发送给模型的 JSON 字符串。
    """
    payload = {
        "task": "build_lesson",
        "unit": unit.model_dump(),
        "student_state": dict(student_state),
        "pretest": list(pretest),
        "kcs": [
            KC_BY_ID[kc_id].model_dump()
            for kc_id in unit.kc_ids
            if kc_id in KC_BY_ID
        ],
        "required_output": {
            "schema_version": "lesson/1",
            "target_kc_ids": unit.kc_ids,
            "sections": "每个 KC 一段，字段 id/kc_id/heading/text",
            "worked_example": "每个 KC 至少一步，字段 kc_id/tag/text",
            "check_questions": "每个 KC 一题，字段 id/kc_id/prompt/answer",
            "common_errors": "至少一条",
            "referenced_kc_ids": "只能来自目标 KC 或已审核先修 KC",
            "math_claims": "只能复制输入 KC 中的 math_claim",
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def build_question_prompt(draft: QuestionDraft) -> str:
    """构造题目语言实现输入；参数与答案由确定性代码给出。

    Args:
        draft: 已通过参数校验与 verify 的题目草稿。

    Returns:
        可直接发送给模型的 JSON 字符串。
    """
    payload = {
        "task": "realize_question_wording",
        "draft": draft.model_dump(),
        "constraints": [
            "题干必须保留全部参数字符串",
            "题干不得包含答案",
            "解析必须包含答案",
            "不得新增或删除条件",
            "不得改变题型",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)
