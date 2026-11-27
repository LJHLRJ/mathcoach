"""收据生成：答对后生成，独立程度由本题最高提示层级推导。"""
import re
import unicodedata
from datetime import datetime, timezone

from .basis import basis_for_receipt
from .hint_ladder import independence_for
from .models import Exercise, KnowledgeCard, Receipt

RESTATEMENT_COMPLETE = "完整"
RESTATEMENT_PARTIAL = "部分"
RESTATEMENT_SPARSE = "待补充"
# 复述完整与部分的关键片段覆盖率门槛；片段总量少时容易波动，门槛取偏宽值
RESTATEMENT_COMPLETE_MIN = 0.3
RESTATEMENT_PARTIAL_MIN = 0.1

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_ALNUM_RUN = re.compile(r"[a-z0-9]+")


def _key_fragments(text: str) -> set[str]:
    """把文本拆成可比较的关键片段。

    汉字取相邻二字，字母数字取长度至少为 2 的整词；单字与单数字不参与比对，
    避免“的”“x”这类高频片段把覆盖率撑高。

    Args:
        text: 原始文本。

    Returns:
        关键片段集合。
    """
    normalized = unicodedata.normalize("NFKC", text).lower()
    fragments: set[str] = set()
    for run in _CJK_RUN.findall(normalized):
        fragments.update(
            run[index : index + 2] for index in range(len(run) - 1)
        )
    for run in _ALNUM_RUN.findall(normalized):
        if len(run) >= 2:
            fragments.add(run)
    return fragments


def assess_restatement(restatement: str, reference: str) -> str | None:
    """按关键片段覆盖率评估复述质量。

    只做确定性比对，不调用模型；覆盖率是参考文本片段被复述命中的比例，
    因此结论只反映措辞重合度，供自查参考，不改变判分与调度。

    Args:
        restatement: 复述文本。
        reference: 标准思路，通常取 ``Exercise.solution_outline``。

    Returns:
        空复述返回 None；否则返回 ``完整`` / ``部分`` / ``待补充``。
    """
    if not restatement.strip():
        return None
    reference_fragments = _key_fragments(reference)
    if not reference_fragments:
        return RESTATEMENT_PARTIAL
    hits = reference_fragments & _key_fragments(restatement)
    coverage = len(hits) / len(reference_fragments)
    if coverage >= RESTATEMENT_COMPLETE_MIN:
        return RESTATEMENT_COMPLETE
    if coverage >= RESTATEMENT_PARTIAL_MIN:
        return RESTATEMENT_PARTIAL
    return RESTATEMENT_SPARSE



def build_receipt(
    card: KnowledgeCard,
    exercise: Exercise,
    goal: str,
    max_hint_level: int,
    duration_s: int,
    restatement_quality: str | None = None,
    judged: bool = True,
    verified: bool = True,
) -> Receipt:
    """生成一张收据。

    独立程度由 ``max_hint_level`` 推导（≤3 独立，≥4 半独立）；依据文字在创建时
    写入 ``basis``，展示层不再补算；时间统一用 UTC。

    Args:
        card: 当前知识卡片。
        exercise: 刚做对的题目。
        goal: 本次会话的目标。
        max_hint_level: 本题用到的最高提示层级。
        duration_s: 本题用时（秒）。
        restatement_quality: L6 复述质量；未走复述时为 None。
        judged: 是否通过判定；False 时依据写“未通过判定，不生成收据”。
        verified: 符号验证是否通过；False 时按半独立记录。

    Returns:
        不可变的 ``Receipt``。
    """
    return Receipt(
        card_id=card.id,
        stage=card.stage,
        course=card.course,
        exercise_type=exercise.kind,
        duration_s=duration_s,
        max_hint_level=max_hint_level,
        goal=goal,
        independence=independence_for(max_hint_level),
        created_at=datetime.now(timezone.utc),
        restatement_quality=restatement_quality,
        exercise_id=exercise.id,
        basis=basis_for_receipt(max_hint_level, judged, verified),
    )
