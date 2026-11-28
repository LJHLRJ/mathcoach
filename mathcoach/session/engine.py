"""会话状态机：只调用 domain 纯函数，不 import Streamlit。"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from ..domain.diagnosis import diagnose
from ..domain.hint_ladder import (
    MAX_REQUESTED_LEVEL,
    automatic_next_level,
    grant_requested_level,
    initial_level,
)
from ..domain.judge import evaluate
from ..domain.models import (
    Consent,
    ErrorType,
    Exercise,
    Independence,
    KnowledgeCard,
    MistakeEntry,
    Phase,
    Receipt,
    SessionState,
)
from ..domain.receipt import RESTATEMENT_SPARSE, assess_restatement, build_receipt
from ..domain.representation import (
    LoadSignals,
    Representation,
    choose_representation,
)
from ..domain.spaced_repetition import Quality
from ..llm.base import Provider, RenderTask
from ..memory.repository import InMemoryRepository, Repository
from ..mastery import (
    observation_weight,
    quality_for_correct,
    reference_seconds_from_history,
)
from ..representation import RepresentationEvent, RepresentationRecorder
from ..safety.guards import REFUSAL_TEXT, detect_injection
from ..safety.redlines import (
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
    sanitize_text,
)
from ..tutor.dialog import (
    DialogEvent,
    DialogEventKind,
    DialogOutcome,
    FollowUpClient,
    FollowUpSpec,
    VerifyFn,
    build_follow_up,
    judge_follow_up,
)
from .state import FollowUpView, SessionView


@dataclass
class _ActiveFollowUp:
    """当前正在等待学生回答的追问。"""

    spec: FollowUpSpec
    prompt: str
    level: int
    supplement: bool
    shown_at: datetime
    anchor_step_index: int | None = None


class SessionEngine:
    """单卡会话状态机。

    每次操作返回 ``SessionView`` 并同步到 ``self.view``；
    写仓储前统一过安全写入门，被拦时只记审计、不打断会话。

    Attributes:
        card: 当前知识点卡。
        provider: 文案提供方。
        repository: 仓储。
        consent: 授权状态。
        state: 会话状态。
        receipts: 本次会话已生成的收据。
        view: 最近一帧视图。
    """

    def __init__(
        self,
        card: KnowledgeCard,
        provider: Provider,
        goal: str = "",
        repository: Repository | None = None,
        consent: Consent | None = None,
        *,
        dialog_client: FollowUpClient | None = None,
        dialog_recorder: Callable[[DialogEvent], None] | None = None,
        dialog_verify_fn: VerifyFn | None = None,
        representation_recorder: RepresentationRecorder | None = None,
        hint_ceiling: int | None = None,
    ) -> None:
        """创建会话并停在目标确认阶段。

        Args:
            card: 知识点卡，题量取自卡片。
            provider: 文案提供方。
            goal: 初始目标，通常为空。
            repository: 仓储，缺省用内存实现。
            consent: 授权状态，缺省全关。
            dialog_client: 追问问法客户端；None 时 L3–L4 保持陈述式提示。
            dialog_recorder: 追问事件落库回调；None 时只存内存。
            dialog_verify_fn: 追问内容验证函数；None 使用默认 verify。
            representation_recorder: 表示降级事件记录器；None 时只做决策。
            hint_ceiling: 主动提示上限，仅用于依赖度防护；None 表示不限制。
        """
        self.card = card
        self.provider = provider
        self.repository = repository or InMemoryRepository()
        self.consent = consent or Consent()
        self.state = SessionState(card_id=card.id, hint_level=initial_level(), goal=goal)
        self._exercise_pos = 0
        self.receipts: list[Receipt] = []
        self.dialog_client = dialog_client
        self.dialog_recorder = dialog_recorder
        self.dialog_verify_fn = dialog_verify_fn
        self.representation_recorder = representation_recorder
        self._hint_ceiling = (
            max(1, min(MAX_REQUESTED_LEVEL, int(hint_ceiling)))
            if hint_ceiling is not None
            else None
        )
        self._hint_ceiling_active = self._hint_ceiling is not None
        self._active_follow_up: _ActiveFollowUp | None = None
        self._dialog_misses = 0
        self.dialog_events: list[DialogEvent] = []
        self._representation = Representation.FORMULA
        self._representation_decided_for: str | None = None
        self._pending_representation: RepresentationEvent | None = None
        self.view = SessionView(
            phase=Phase.GOAL_CONFIRM,
            title=f"目标确认 · {card.name}",
            body="用一句话说说你今天想练到什么？例如：搞懂函数的概念。",
        )

    @property
    def current_exercise(self) -> Exercise:
        """返回当前题；题号由 ``advance`` 推进。"""
        return self.card.exercises[self._exercise_pos]

    def _set(self, view: SessionView) -> SessionView:
        """记录并返回当前视图；降级后自动带上表示形态。"""
        if (
            view.representation is None
            and self._representation is not Representation.FORMULA
        ):
            view = replace(view, representation=self._representation)
        self.view = view
        return view

    @property
    def hint_ceiling_active(self) -> bool:
        """当前是否处于依赖度防护的主动提示上限内。"""
        return self._hint_ceiling_active

    @property
    def hint_ceiling(self) -> int | None:
        """当前提示上限；未启用时为 None。"""
        return self._hint_ceiling if self._hint_ceiling_active else None

    def release_hint_ceiling(self, reason: str = "manual") -> bool:
        """解除主动提示上限；重复解除返回 False。

        只影响后续主动请求，不回溯已展示的提示，也不改变收据独立程度。
        """
        if not self._hint_ceiling_active:
            return False
        self._hint_ceiling_active = False
        try:
            self.repository.record_audit("hint_ceiling", f"release:{reason}")
        except (OSError, sqlite3.Error):
            pass
        return True

    def confirm_goal(self, goal: str) -> SessionView:
        """确认学习目标并进入讲解阶段。

        空目标抛 ValueError；注入检测命中时标记观察会话、记审计并抛出。

        Args:
            goal: 目标文本，会去掉首尾空白。

        Returns:
            讲解阶段视图。

        Raises:
            RuntimeError: 当前不在目标确认阶段。
            ValueError: 目标为空。
            Blocked: 目标命中注入规则。
        """
        if self.state.phase is not Phase.GOAL_CONFIRM:
            raise RuntimeError("当前不在目标确认阶段")
        goal = goal.strip()
        if not goal:
            raise ValueError("目标不能为空")
        blocked = detect_injection(goal)
        if blocked is not None:
            self.state.observed = True
            self.repository.record_audit("goal", f"blocked:{blocked.reason}")
            raise blocked
        self.state.goal = goal
        self.state.started_at = datetime.now(timezone.utc)
        self.state.phase = Phase.EXPLAIN
        text = self.provider.render(
            RenderTask(
                kind="explain",
                card_name=self.card.name,
                content=(
                    f"目标：{goal}\n\n"
                    f"直觉：{self.card.intuition}\n\n"
                    f"定义：{self.card.definition}\n\n"
                    f"常见误区：{'；'.join(self.card.mistakes)}"
                ),
            )
        )
        return self._set(
            SessionView(
                phase=Phase.EXPLAIN,
                title=f"讲解 · {self.card.name}",
                body=text,
                notice="看完后点“开始小测”，只有做对才生成收据。",
            )
        )

    def begin_quiz(self) -> SessionView:
        """进入小测，重置本题的提示、连错与诊断状态。"""
        if self.state.phase is not Phase.EXPLAIN:
            raise RuntimeError("当前不在讲解阶段")
        self.state.phase = Phase.QUIZ
        self.state.exercise_id = self.current_exercise.id
        self.state.hint_level = initial_level()
        self.state.consecutive_wrong = 0
        self.state.hint_requests = []
        self.state.diagnosis = None
        self.state.exercise_started_at = datetime.now(timezone.utc)
        self._active_follow_up = None
        self._dialog_misses = 0
        self._reset_representation()
        return self._render_quiz()

    def _render_quiz(self, notice: str | None = None) -> SessionView:
        """渲染当前题；notice 为空时显示当前提示层级。"""
        exercise = self.current_exercise
        return self._set(
            SessionView(
                phase=Phase.QUIZ,
                title=f"小测 · 第 {self._exercise_pos + 1} / {len(self.card.exercises)} 题",
                body=exercise.stem,
                options=exercise.options,
                notice=notice
                if notice is not None
                else f"当前提示层级 L{self.state.hint_level}",
            )
        )

    def submit_answer(self, answer: str) -> SessionView:
        """提交当前题的作答。

        注入命中只提示不计分；无法自动核对时留在本题、不计连错；
        答对生成收据；答错累计连错，2 次进入错因诊断，3 次收尾。

        Args:
            answer: 作答文本。

        Returns:
            下一帧视图。

        Raises:
            RuntimeError: 当前不在小测阶段。
        """
        if self.state.phase is not Phase.QUIZ:
            raise RuntimeError("当前不在小测阶段")
        exercise = self.current_exercise
        answer_level = self.state.hint_level  # 本次作答实际用到的层级
        blocked = detect_injection(answer)
        if blocked is not None:
            self.state.observed = True
            self.repository.record_audit("answer", f"blocked:{blocked.reason}")
            return self._render_quiz(
                notice=f"{REFUSAL_TEXT} 本次不计入连错。"
            )
        judgement = evaluate(exercise, answer)
        self._record_representation_outcome(judgement.correct)
        self.state.attempts.append(
            {
                "exercise_id": exercise.id,
                "answer": answer,
                "hint_level": answer_level,
                "correct": judgement.correct,
            }
        )
        self.state.max_hint_level = max(self.state.max_hint_level, answer_level)

        if judgement.correct is None:
            # 符号验证超时/被拒：不伪装成判分，也不计入连错。
            return self._render_quiz(
                notice=(
                    f"这一步无法自动核对（{judgement.reason}），"
                    "建议人工核对后重试；本次不计入连错。"
                )
            )

        if judgement.correct:
            return self._issue_receipt()

        self.state.consecutive_wrong += 1
        released = False
        if self._hint_ceiling_active and self.state.consecutive_wrong >= 2:
            released = self.release_hint_ceiling("two_wrong")
        self._prepare_representation()
        self._record_mistake(exercise, answer)
        if self.state.consecutive_wrong >= 3:
            self.state.phase = Phase.WRAPUP
            return self._set(
                SessionView(
                    phase=Phase.WRAPUP,
                    title="先停一下",
                    body=(
                        f"这道题连续答错 3 次。完整思路：{exercise.solution_outline}\n\n"
                        "本次不生成收据。建议先降一档难度，从更基础的保底题重新开始。"
                    ),
                    receipts=tuple(self.receipts),
                )
            )

        if self.state.consecutive_wrong == 2:
            diagnosis = diagnose(
                exercise,
                self._wrong_answers(exercise.id),
                tuple(self.state.hint_requests),
            )
            self.state.diagnosis = diagnosis.error_type
            self.state.phase = Phase.DIAGNOSE
            return self._set(
                SessionView(
                    phase=Phase.DIAGNOSE,
                    title="先诊断一下错因",
                    body=(
                        f"这道题连续答错 2 次。初步判断：{diagnosis.error_type.value}"
                        f"——{diagnosis.reason}。\n\n"
                        f"请确认，或改选更贴近的一类；确认后回到提示 L"
                        f"{automatic_next_level(self.state.hint_level)}。"
                        + ("\n\n本轮已恢复完整提示。" if released else "")
                    ),
                    options=tuple(item.value for item in ErrorType),
                    notice="错因诊断只影响提示措辞，不改变判分。",
                )
            )

        self.state.phase = Phase.HINT
        self.state.hint_level = automatic_next_level(self.state.hint_level)
        self._start_follow_up(self.state.hint_level)
        if self._active_follow_up is not None:
            return self._render_follow_up(
                self._active_follow_up,
                "先回答追问，再回到原题。",
            )
        return self._set(
            SessionView(
                phase=Phase.HINT,
                title=f"提示 L{self.state.hint_level}",
                body=self._hint_text(self.state.hint_level),
                notice="看完提示后回到原题再试一次。",
            )
        )

    def _wrong_answers(self, exercise_id: str) -> list[str]:
        """收集指定题目判错的作答文本。"""
        return [
            attempt["answer"]
            for attempt in self.state.attempts
            if attempt["exercise_id"] == exercise_id
            and attempt.get("correct") is False
        ]

    def _safe_write(self, op: str, action: Callable[[], None]) -> bool:
        """过安全写入门；被拦时记审计并返回 False。"""
        try:
            assert_write_allowed(
                op, consent=self.consent, observed=self.state.observed
            )
        except (WriteBlocked, ConfirmationRequired) as exc:
            self.repository.record_audit(op, f"blocked:{exc.reason}")
            return False
        action()
        self.repository.record_audit(op, "ok")
        return True

    def _record_mistake(self, exercise: Exercise, answer: str) -> None:
        """写入错题；错因未确认时先跑一次诊断。"""
        if not self.consent.mistake_book:
            return
        now = datetime.now(timezone.utc)
        duration_s = 0
        if self.state.exercise_started_at is not None:
            duration_s = max(
                0,
                int(
                    (
                        now - self.state.exercise_started_at
                    ).total_seconds()
                ),
            )
        error_type = self.state.diagnosis
        if error_type is None:
            error_type = diagnose(
                exercise,
                self._wrong_answers(exercise.id),
                tuple(self.state.hint_requests),
            ).error_type
        entry = MistakeEntry(
            id=uuid4().hex,
            exercise_id=exercise.id,
            card_id=self.card.id,
            stage=self.card.stage,
            course=self.card.course,
            exercise_type=exercise.kind,
            stem=exercise.stem,
            user_answer=answer,
            correct_answer=exercise.answer,
            error_type=error_type,
            max_hint_level=self.state.max_hint_level,
            created_at=now,
            exercise_snapshot={
                "id": exercise.id,
                "kind": exercise.kind.value,
                "stem": exercise.stem,
                "options": list(exercise.options),
                "solution_outline": exercise.solution_outline,
                "variants": list(exercise.variants),
                "duration_s": duration_s,
            },
        )
        self._safe_write("mistake", lambda: self.repository.save_mistake(entry))

    def confirm_diagnosis(self, error_type: str | None = None) -> SessionView:
        """确认或改选错因，然后升一档提示。

        Args:
            error_type: 错因值；为空时保留诊断出的结果。

        Returns:
            提示阶段视图。

        Raises:
            RuntimeError: 当前不在错因诊断阶段。
            ValueError: 错因值不在枚举里。
        """
        if self.state.phase is not Phase.DIAGNOSE:
            raise RuntimeError("当前不在错因诊断阶段")
        if error_type is not None:
            try:
                self.state.diagnosis = ErrorType(error_type)
            except ValueError as exc:
                raise ValueError(f"未知错因：{error_type}") from exc
        self.state.phase = Phase.HINT
        self.state.hint_level = automatic_next_level(self.state.hint_level)
        self._prepare_representation()
        if self.state.diagnosis is not None and self.consent.mistake_book:
            self._safe_write(
                "mistake",
                lambda: self.repository.update_mistake_error_type(
                    self.current_exercise.id, self.state.diagnosis
                ),
            )
        label = self.state.diagnosis.value if self.state.diagnosis else "未确定"
        self._start_follow_up(self.state.hint_level)
        if self._active_follow_up is not None:
            return self._render_follow_up(
                self._active_follow_up,
                f"错因：{label}。先回答追问，再回到原题。",
            )
        return self._set(
            SessionView(
                phase=Phase.HINT,
                title=f"提示 L{self.state.hint_level} · 错因：{label}",
                body=self._hint_text(self.state.hint_level),
                notice="带着错因再看一遍提示，然后回到原题。",
            )
        )

    def _hint_text(self, level: int) -> str:
        """按层级返回提示文案，L6 要求复述思路。"""
        exercise = self.current_exercise
        if level <= 1:
            return "先说说这题在问什么、考哪个概念？"
        if level == 2:
            return "先看题目里的关键条件/最高阶项。"
        if level == 3:
            return f"回到概念：{self.card.intuition}"
        if level == 4:
            return f"关键思路：{exercise.solution_outline}"
        if level == 5:
            return f"完整推导：{exercise.solution_outline}"
        return "请用自己的话复述本题思路，再说出答案。"

    def _reset_representation(self) -> None:
        """换题时重置表示形态与待回填事件。"""
        self._representation = Representation.FORMULA
        self._representation_decided_for = None
        self._pending_representation = None

    def _load_representation_signals(self) -> LoadSignals:
        """收集当前题可用的会话内行为信号。"""
        elapsed_ratio = 0.0
        if self.state.exercise_started_at is not None:
            elapsed = max(
                0.0,
                (
                    datetime.now(timezone.utc)
                    - self.state.exercise_started_at
                ).total_seconds(),
            )
            try:
                reference = reference_seconds_from_history(
                    self.repository.list_receipts(limit=None),
                    self.card.id,
                )
            except (OSError, sqlite3.Error):
                reference = 0.0
            if reference > 0:
                elapsed_ratio = elapsed / reference
        return LoadSignals(
            consecutive_wrong=self.state.consecutive_wrong,
            dialog_misses=self._dialog_misses,
            hint_requests=len(self.state.hint_requests),
            elapsed_ratio=elapsed_ratio,
        )

    def _prepare_representation(self) -> None:
        """按行为信号决定是否降级；降级后同题不再重复决策。"""
        exercise_id = self.current_exercise.id
        if self._representation_decided_for == exercise_id:
            return
        decision = choose_representation(
            self._representation,
            self._load_representation_signals(),
        )
        if not decision.downgraded:
            return
        self._representation_decided_for = exercise_id
        self._representation = decision.target
        event = RepresentationEvent(
            exercise_id=exercise_id,
            card_id=self.card.id,
            from_repr=decision.base,
            to_repr=decision.target,
            triggers=decision.reasons,
        )
        self._pending_representation = event
        if self.representation_recorder is None:
            return
        try:
            self.representation_recorder.record(event)
        except (OSError, sqlite3.Error):
            pass

    def _record_representation_outcome(
        self, correct: bool | None
    ) -> None:
        """回填降级后的第一次作答；没有待回填事件时跳过。"""
        event = self._pending_representation
        if event is None:
            return
        self._pending_representation = None
        if self.representation_recorder is None:
            return
        try:
            self.representation_recorder.record_outcome(
                event.id,
                correct=correct,
                hint_level=self.state.hint_level,
            )
        except (OSError, sqlite3.Error):
            pass

    def _follow_up_view(self, active: _ActiveFollowUp) -> FollowUpView:
        """把内部追问状态转成视图。"""
        return FollowUpView(
            level=active.level,
            prompt=active.prompt,
            supplement=active.supplement,
            anchor_step_index=active.anchor_step_index,
        )

    def _render_follow_up(
        self, active: _ActiveFollowUp, notice: str
    ) -> SessionView:
        """渲染当前追问，等待学生回答。"""
        title = (
            f"提示 L{active.level} · 补充追问"
            if active.supplement
            else f"提示 L{active.level} · 追问"
        )
        return self._set(
            SessionView(
                phase=Phase.HINT,
                title=title,
                body=active.prompt,
                notice=notice,
                follow_up=self._follow_up_view(active),
            )
        )

    def _start_follow_up(
        self,
        level: int,
        *,
        supplement: bool = False,
        anchor_step_index: int | None = None,
    ) -> FollowUpView | None:
        """尝试在 L3/L4 生成追问；失败时记录降级并返回 None。"""
        if level not in (3, 4):
            return None
        if self._dialog_misses >= 2:
            self._record_dialog_fallback(
                level=level,
                supplement=supplement,
                reason="two_misses",
            )
            return None
        result = build_follow_up(
            self.current_exercise.id,
            level,
            client=self.dialog_client,
            supplement=supplement,
            verify_fn=self.dialog_verify_fn,
        )
        if result.follow_up is None:
            if result.spec is not None:
                reason = result.fallback_reason
                if result.verify_verdict:
                    reason = f"{reason}:{result.verify_verdict}"
                self._record_dialog_fallback(
                    level=level,
                    supplement=supplement,
                    reason=reason,
                    spec=result.spec,
                )
            return None
        now = datetime.now(timezone.utc)
        self._active_follow_up = _ActiveFollowUp(
            spec=result.follow_up.spec,
            prompt=result.follow_up.prompt,
            level=level,
            supplement=supplement,
            shown_at=now,
            anchor_step_index=anchor_step_index,
        )
        return self._follow_up_view(self._active_follow_up)

    def _record_dialog_event(
        self,
        active: _ActiveFollowUp,
        kind: DialogEventKind,
        *,
        answer: str = "",
        reason: str = "",
        downgraded: bool = False,
    ) -> None:
        """记录一次追问结果，供效果信号使用。"""
        now = datetime.now(timezone.utc)
        event = DialogEvent(
            exercise_id=self.current_exercise.id,
            card_id=self.card.id,
            kc_ids=active.spec.kc_ids,
            level=active.level,
            supplement=active.supplement,
            kind=kind,
            downgraded=downgraded,
            answer=sanitize_text(answer),
            reason=reason,
            shown_at=active.shown_at,
            resolved_at=now,
        )
        self.dialog_events.append(event)
        if self.dialog_recorder is not None:
            self.dialog_recorder(event)

    def _record_dialog_fallback(
        self,
        *,
        level: int,
        supplement: bool,
        reason: str,
        spec: FollowUpSpec | None = None,
    ) -> None:
        """记录未生成追问的降级事件。"""
        now = datetime.now(timezone.utc)
        event = DialogEvent(
            exercise_id=self.current_exercise.id,
            card_id=self.card.id,
            kc_ids=spec.kc_ids if spec is not None else (),
            level=level,
            supplement=supplement,
            kind=DialogEventKind.FALLBACK,
            downgraded=False,
            reason=reason,
            shown_at=now,
            resolved_at=now,
        )
        self.dialog_events.append(event)
        if self.dialog_recorder is not None:
            self.dialog_recorder(event)

    def _downgrade_to_l5(self, notice: str) -> SessionView:
        """结束追问并降到 L5 完整讲解。"""
        self._active_follow_up = None
        self.state.phase = Phase.HINT
        self.state.hint_level = 5
        self.state.max_hint_level = max(self.state.max_hint_level, 5)
        return self._set(
            SessionView(
                phase=Phase.HINT,
                title="提示 L5 · 完整讲解",
                body=self._hint_text(5),
                notice=notice,
            )
        )

    def submit_follow_up(self, answer: str) -> SessionView:
        """提交追问回答并按命中/部分命中/未命中三档推进。"""
        active = self._active_follow_up
        if active is None or self.state.phase is not Phase.HINT:
            raise RuntimeError("当前没有追问")
        text = answer.strip()
        if not text:
            return self._render_follow_up(active, "先写下你的回答。")
        blocked = detect_injection(text)
        if blocked is not None:
            self.state.observed = True
            self.repository.record_audit(
                "dialog", f"blocked:{blocked.reason}"
            )
            self._record_dialog_event(
                active,
                DialogEventKind.BLOCKED,
                answer=text,
                reason=blocked.reason,
            )
            return self._render_follow_up(
                active, f"{REFUSAL_TEXT} 请重新回答追问。"
            )
        outcome = judge_follow_up(active.spec, text)
        if outcome is DialogOutcome.HIT:
            self._record_dialog_event(
                active, DialogEventKind.HIT, answer=text
            )
            self._dialog_misses = 0
            self._active_follow_up = None
            if active.level == 3:
                self._start_follow_up(
                    4, anchor_step_index=active.anchor_step_index
                )
                if self._active_follow_up is not None:
                    self.state.hint_level = 4
                    self.state.max_hint_level = max(
                        self.state.max_hint_level, 4
                    )
                    return self._render_follow_up(
                        self._active_follow_up,
                        "L3 追问命中，进入 L4 追问。",
                    )
            return self._render_quiz(
                notice="追问命中，回到原题再试一次。"
            )
        if outcome is DialogOutcome.PARTIAL:
            if not active.supplement:
                self._start_follow_up(
                    active.level,
                    supplement=True,
                    anchor_step_index=active.anchor_step_index,
                )
                if self._active_follow_up is not None:
                    self._record_dialog_event(
                        active,
                        DialogEventKind.PARTIAL,
                        answer=text,
                    )
                    return self._render_follow_up(
                        self._active_follow_up,
                        "部分命中，再补充一个更具体的问题。",
                    )
            self._record_dialog_event(
                active,
                DialogEventKind.PARTIAL,
                answer=text,
                downgraded=True,
            )
            return self._downgrade_to_l5(
                "补充追问后仍未完全命中，降到 L5 完整讲解。"
            )
        self._dialog_misses += 1
        self._record_dialog_event(
            active,
            DialogEventKind.MISS,
            answer=text,
            downgraded=True,
        )
        return self._downgrade_to_l5(
            "追问未命中，降到 L5 完整讲解。"
        )

    def request_hint(
        self, kind: str, *, step_index: int | None = None
    ) -> SessionView:
        """按门槛发放请求的提示。

        步骤与答案请求只把展示层级压到 L4，状态层级不回退；
        其余请求按 ``grant_requested_level`` 的结果展示。

        Args:
            kind: 请求类型，如 ``step`` / ``answer``。
            step_index: 可选步骤序号；生成追问时作为锚点，便于学生从
                当前步骤继续问，而不是回到整道题。

        Returns:
            提示阶段视图。

        Raises:
            RuntimeError: 当前不在小测或提示阶段。

        Note:
            ``level5`` 的门槛按当前卡片会话累计：前面题目提交过 L1–L4 也计入，
            不要求在同一题内集齐。单题连错 3 次即收尾，跨题累计是唯一可达路径。
        """
        if self.state.phase not in (Phase.QUIZ, Phase.HINT):
            raise RuntimeError("当前不能请求提示")
        if self._active_follow_up is not None:
            raise RuntimeError("请先回答当前追问")
        # 门槛按卡片会话累计：单题最多 3 次连错，集不齐 L1–L4
        attempted = {attempt["hint_level"] for attempt in self.state.attempts}
        # M1 只做门槛判定，实际可达性依赖 M2 连错诊断；测试覆盖门槛逻辑即可。
        level, message = grant_requested_level(self.state.hint_level, kind, attempted)
        if self._hint_ceiling_active:
            ceiling = self._hint_ceiling or 2
            if kind == "level5":
                level = self.state.hint_level
                message = (
                    "本轮先自己试一步，暂不开放 L5；"
                    "连续两次答错会自动恢复完整提示。"
                )
            else:
                requested = level
                level = min(
                    requested, max(ceiling, self.state.hint_level)
                )
                if level < requested:
                    message += (
                        f" 本轮先自己试一步，主动请求最高到 L{ceiling}。"
                    )
        self.state.hint_requests.append(kind)
        self.state.hint_level = level
        self.state.max_hint_level = max(self.state.max_hint_level, level)
        self.state.phase = Phase.HINT
        self._prepare_representation()
        # 请求步骤/答案只降展示层级，不把 L5 状态退回 L4
        display_level = (
            min(level, MAX_REQUESTED_LEVEL)
            if kind in ("step", "answer")
            else level
        )
        self._start_follow_up(
            display_level, anchor_step_index=step_index
        )
        if self._active_follow_up is not None:
            return self._render_follow_up(
                self._active_follow_up,
                "先回答追问，再回到原题。",
            )
        return self._set(
            SessionView(
                phase=Phase.HINT,
                title=f"提示 L{display_level}",
                body=f"{message}\n\n{self._hint_text(display_level)}",
                notice="看完提示后回到原题再试一次。",
            )
        )

    def retry(self) -> SessionView:
        """从提示回到小测；若有未完成追问，按跳过记录。"""
        if self.state.phase is not Phase.HINT:
            raise RuntimeError("当前不在提示阶段")
        if self._active_follow_up is not None:
            self._record_dialog_event(
                self._active_follow_up,
                DialogEventKind.SKIPPED,
                reason="retry",
            )
            self._active_follow_up = None
        self.state.phase = Phase.QUIZ
        return self._render_quiz()

    def _persist_receipt(self, receipt: Receipt) -> None:
        """按授权写入收据并登记复习；弱正确降低 BKT 权重与 FSRS 间隔。"""
        exercise = self.current_exercise
        reference = reference_seconds_from_history(
            self.repository.list_receipts(limit=None),
            self.card.id,
        )
        weight = observation_weight(receipt.duration_s, reference)
        quality = quality_for_correct(
            receipt.duration_s, reference, receipt.max_hint_level
        )
        if self.consent.memory:
            self._safe_write(
                "receipt",
                lambda: self.repository.save_receipt(
                    receipt,
                    exercise.id,
                    mastery_weight=weight,
                ),
            )
        if self.consent.mistake_book:
            # 弱正确按 HINTED 处理，复用现有 FSRS 的 HARD 间隔
            self._safe_write(
                "review",
                lambda: self.repository.record_review(
                    exercise.id,
                    independent=quality,
                    now=datetime.now(timezone.utc),
                ),
            )

    def _issue_receipt(self) -> SessionView:
        """生成收据、写入仓储并返回收据视图。"""
        self.state.phase = Phase.RECEIPT
        elapsed = 0
        if self.state.exercise_started_at is not None:
            elapsed = int(
                (datetime.now(timezone.utc) - self.state.exercise_started_at).total_seconds()
            )
        receipt = build_receipt(
            card=self.card,
            exercise=self.current_exercise,
            goal=self.state.goal,
            max_hint_level=self.state.max_hint_level,
            duration_s=elapsed,
        )
        if self._hint_ceiling_active and self.state.max_hint_level <= 3:
            self.release_hint_ceiling("independent_correct")
        self.receipts.append(receipt)
        self._persist_receipt(receipt)
        return self._set(
            SessionView(
                phase=Phase.RECEIPT,
                title="收据已生成",
                body=(
                    f"题型：{self.current_exercise.kind.value} · "
                    f"独立程度：{receipt.independence.value}\n\n"
                    f"最高提示层级：L{receipt.max_hint_level} · 用时：{receipt.duration_s} 秒"
                ),
                receipt=receipt,
                receipts=tuple(self.receipts),
            )
        )

    def submit_restatement(self, text: str) -> SessionView:
        """记录 L6 费曼复述质量，并把待补充的结果回流到复习状态。

        只补写收据上的 ``restatement_quality``，不重新生成收据、不重复推进掌握概率；
        复述为 ``RESTATEMENT_SPARSE`` 且本题已有错题记录时，补记一次半独立复习，
        连续独立次数清零，避免仅凭答对就记为已掌握。

        Args:
            text: 复述文本，空文本视为未完成。

        Returns:
            收据阶段视图，``notice`` 带本次质量。

        Raises:
            RuntimeError: 当前不在收据阶段或没有收据。
            ValueError: 复述为空。
        """
        if self.state.phase is not Phase.RECEIPT:
            raise RuntimeError("当前不在收据阶段")
        receipt = self.view.receipt
        if receipt is None:
            raise RuntimeError("没有可更新的收据")
        quality = assess_restatement(
            text, self.current_exercise.solution_outline
        )
        if quality is None:
            raise ValueError("复述不能为空")
        updated = replace(receipt, restatement_quality=quality)
        self.receipts = [
            updated if item.id == receipt.id else item
            for item in self.receipts
        ]
        if self.consent.memory:
            self._safe_write(
                "receipt",
                lambda: self.repository.update_receipt_restatement(
                    updated.id, quality
                ),
            )
        notice = f"L6 复述质量：{quality}"
        if quality is RESTATEMENT_SPARSE and self._record_restatement_review():
            notice += "；已按半独立记录，需继续复习"
        return self._set(
            SessionView(
                phase=Phase.RECEIPT,
                title="收据已生成",
                body=self.view.body,
                receipt=updated,
                receipts=tuple(self.receipts),
                notice=notice,
            )
        )

    def _record_restatement_review(self) -> bool:
        """弱复述补记一次半独立复习；没有错题记录或被拦截时返回 False。"""
        exercise_id = self.current_exercise.id
        if self.repository.find_mistake(exercise_id) is None:
            return False
        recorded = False

        def _action() -> None:
            nonlocal recorded
            recorded = (
                self.repository.record_review(
                    exercise_id,
                    Quality.HINTED,
                    now=datetime.now(timezone.utc),
                )
                is not None
            )

        self._safe_write("review", _action)
        return recorded

    def advance(self) -> SessionView:
        """推进到下一题；最后一题后进入收尾。

        Returns:
            下一题视图或收尾视图。

        Raises:
            RuntimeError: 当前不在收据阶段。
        """
        if self.state.phase is not Phase.RECEIPT:
            raise RuntimeError("当前不在收据阶段")
        if self._hint_ceiling_active:
            self.release_hint_ceiling("exercise_completed")
        if self._exercise_pos + 1 < len(self.card.exercises):
            self._exercise_pos += 1
            self.state.phase = Phase.QUIZ
            self.state.hint_level = initial_level()
            self.state.consecutive_wrong = 0
            self.state.hint_requests = []
            self.state.diagnosis = None
            self.state.max_hint_level = 0  # 跨题不继承上一题的提示层级
            self.state.exercise_id = self.current_exercise.id
            self.state.exercise_started_at = datetime.now(timezone.utc)
            self._active_follow_up = None
            self._dialog_misses = 0
            self._reset_representation()
            return self._render_quiz()

        self.state.phase = Phase.WRAPUP
        independent = sum(
            1
            for receipt in self.receipts
            if receipt.independence is Independence.INDEPENDENT
        )
        return self._set(
            SessionView(
                phase=Phase.WRAPUP,
                title="本次闭环完成",
                body=(
                    f"共完成 {len(self.receipts)} 道题，其中独立完成 {independent} 道。\n\n"
                    "复习建议：今天先回顾收据里标为半独立的题目。"
                ),
                receipts=tuple(self.receipts),
            )
        )
