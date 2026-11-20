"""领域模型：不可变 dataclass + 枚举，供各层共享。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class Stage(str, Enum):
    HIGH_SCHOOL = "highschool"
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"


class Difficulty(str, Enum):
    BASIC = "基础"
    INTERMEDIATE = "进阶"
    CHALLENGE = "挑战"


class HintLevel(int, Enum):
    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4
    L5 = 5
    L6 = 6


class ErrorType(str, Enum):
    CONCEPT = "概念不清"
    FORMULA = "公式记错"
    CALCULATION = "计算失误"
    READING = "读题偏差"
    STEP_JUMP = "跳步"


class ReviewState(str, Enum):
    UNREVIEWED = "未复习"
    REVIEWING = "复习中"
    MASTERED = "已掌握"


class Independence(str, Enum):
    INDEPENDENT = "独立完成"
    SEMI_INDEPENDENT = "半独立完成"


class ExerciseKind(str, Enum):
    CHOICE = "choice"
    MULTI = "multi"
    TRUEFALSE = "truefalse"
    FILL = "fill"
    EXPR = "expr"
    PROOF_ORDER = "proof_order"
    FIND_ERROR = "find_error"
    MATCH = "match"


class Phase(str, Enum):
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
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True)
class Consent:
    """本地记忆授权；全关时进入游客模式，不落盘。"""

    memory: bool = True
    mistake_book: bool = True


@dataclass(frozen=True)
class MistakeEntry:
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


@dataclass(frozen=True)
class ReviewItem:
    mistake: MistakeEntry
    due_at: datetime


@dataclass(frozen=True)
class AuditEntry:
    id: int
    op: str
    result: str
    created_at: datetime


@dataclass
class SessionState:
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
