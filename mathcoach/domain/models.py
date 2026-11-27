"""领域模型：不可变 dataclass + 枚举，供各层共享。

``SessionState`` 是唯一可变的会话状态，其余模型创建后不再修改。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

from .spaced_repetition import DEFAULT_EASE, DEFAULT_INTERVAL


class Stage(str, Enum):
    """学段，取值与 content/ 下的目录名一致。"""

    HIGH_SCHOOL = "highschool"
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"


class Difficulty(str, Enum):
    """难度分档，用于筛选与展示。"""

    BASIC = "基础"
    INTERMEDIATE = "进阶"
    CHALLENGE = "挑战"


class HintLevel(int, Enum):
    """提示层级 L0–L6 的命名常量；会话状态里层级用 int 保存。"""

    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4
    L5 = 5
    L6 = 6


class ErrorType(str, Enum):
    """五类错因；诊断结果允许学生在 DIAGNOSE 阶段改选。"""

    CONCEPT = "概念不清"
    FORMULA = "公式记错"
    CALCULATION = "计算失误"
    READING = "读题偏差"
    STEP_JUMP = "跳步"


class ReviewState(str, Enum):
    """错题复习状态：未复习 → 复习中 → 已掌握。"""

    UNREVIEWED = "未复习"
    REVIEWING = "复习中"
    MASTERED = "已掌握"


class Independence(str, Enum):
    """收据的独立程度，由本次最高提示层级推导。"""

    INDEPENDENT = "独立完成"
    SEMI_INDEPENDENT = "半独立完成"


class ExerciseKind(str, Enum):
    """8 种题型；judge 按它分派判定函数。"""

    CHOICE = "choice"
    MULTI = "multi"
    TRUEFALSE = "truefalse"
    FILL = "fill"
    EXPR = "expr"
    PROOF_ORDER = "proof_order"
    FIND_ERROR = "find_error"
    MATCH = "match"


class Phase(str, Enum):
    """会话阶段；由 session.engine 推进。"""

    GOAL_CONFIRM = "目标确认"
    EXPLAIN = "讲解"
    QUIZ = "小测"
    JUDGE = "判定"
    DIAGNOSE = "错因诊断"
    HINT = "提示"
    RECEIPT = "收据"
    WRAPUP = "收尾"


@dataclass(frozen=True)
class Exercise:
    """一道练习题。

    ``answer`` 是标准答案，``accepted`` 是等价备选，``variants`` 用于错题变式，
    ``solution_outline`` 供 L4/L5 提示与收尾页复用。
    """

    id: str
    card_id: str
    kind: ExerciseKind
    stem: str
    answer: str
    solution_outline: str
    options: tuple[str, ...] = ()
    accepted: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeCard:
    """一张知识卡片。

    ``intuition`` / ``definition`` / ``mistakes`` / ``example`` 是讲解与学习卡片的
    素材，``exercises`` 至少一道，``source`` 记录内容来源。
    """

    id: str
    name: str
    stage: Stage
    course: str
    chapter: str
    difficulty: Difficulty
    intuition: str
    definition: str
    mistakes: tuple[str, ...]
    example: str
    exercises: tuple[Exercise, ...]
    source: str


@dataclass(frozen=True)
class Receipt:
    """一次成功作答的收据，生成后不再修改。

    ``basis`` 在创建时写入，展示层不补算；``restatement_quality`` 只在 L6 复述后填写。
    """

    card_id: str
    stage: Stage
    course: str
    exercise_type: ExerciseKind
    duration_s: int
    max_hint_level: int
    goal: str
    independence: Independence
    created_at: datetime
    restatement_quality: str | None = None
    exercise_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    basis: str = ""  # 生成时写入的可复核依据，不在展示层补算


@dataclass(frozen=True)
class Consent:
    """本地记忆授权；全关时进入游客模式，不落盘。"""

    memory: bool = True
    mistake_book: bool = True


@dataclass(frozen=True)
class MistakeEntry:
    """错题记录。

    ``exercise_snapshot`` 保存作答时的题目快照，复习时不再回读卡片；
    ``ease`` / ``interval_days`` 供 SM-2，``stability`` / ``difficulty`` /
    ``reps`` / ``lapses`` 供 FSRS。
    """

    id: str
    exercise_id: str
    card_id: str
    stage: Stage
    course: str
    exercise_type: ExerciseKind
    stem: str
    user_answer: str
    correct_answer: str
    error_type: ErrorType
    max_hint_level: int
    created_at: datetime
    review_state: ReviewState = ReviewState.UNREVIEWED
    review_count: int = 0
    consecutive_correct: int = 0
    receipt_ids: tuple[str, ...] = ()
    exercise_snapshot: dict[str, object] = field(default_factory=dict)
    ease: float = DEFAULT_EASE  # SM-2 难度因子，默认 2.5
    interval_days: int = DEFAULT_INTERVAL  # 当前复习间隔，默认 1 天
    next_review_at: datetime | None = None  # 下次到期时间；None 表示按 created_at 立即到期
    stability: float = 0.0  # FSRS 记忆稳定性；0 表示尚未初始化
    difficulty: float = 5.0  # FSRS 难度 1..10
    reps: int = 0  # FSRS 累计复习次数
    lapses: int = 0  # FSRS 累计遗忘次数


@dataclass(frozen=True)
class ReviewItem:
    """复习队列项：错题 + 本次到期时间。"""

    mistake: MistakeEntry
    due_at: datetime


@dataclass(frozen=True)
class AuditEntry:
    """审计日志：只记操作类型、结果与时间，不含作答内容与密钥。"""

    id: int
    op: str
    result: str
    created_at: datetime


@dataclass(frozen=True)
class DailyResult:
    """每日挑战结果；``date`` 为本地 ISO 日期。"""

    date: str  # ISO 日期，如 2026-11-20
    correct: int
    total: int
    duration_s: int
    completed_at: datetime


@dataclass(frozen=True)
class ChallengeResult:
    """挑战赛结果；``id`` 由存储层分配。"""

    score: int
    total: int
    duration_s: int
    created_at: datetime
    id: int = 0


@dataclass
class SessionState:
    """一次会话的可变状态，只存在内存，不直接落库。

    ``attempts`` 保存每次作答快照，``hint_requests`` 记录本题请求过的提示类型，
    ``diagnosis`` 是连错 2 次后的结果，``observed`` 表示本次会话出现过边界请求。
    """

    phase: Phase = Phase.GOAL_CONFIRM
    card_id: str | None = None
    exercise_id: str | None = None
    hint_level: int = 0
    max_hint_level: int = 0
    consecutive_wrong: int = 0
    attempts: list[dict] = field(default_factory=list)  # 每次作答快照，供后续诊断使用
    hint_requests: list[str] = field(default_factory=list)  # 本题主动请求过的提示类型
    diagnosis: ErrorType | None = None  # 连错 2 次后的错因诊断结果
    observed: bool = False  # 本次会话出现过边界请求；只存会话，不写入档案
    goal: str = ""
    started_at: datetime | None = None
    exercise_started_at: datetime | None = None  # 单题计时起点，收据用时按题计算
