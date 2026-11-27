"""会话状态机：只调用 domain 纯函数，不 import Streamlit。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
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
from ..domain.spaced_repetition import Quality, quality_from_outcome
from ..llm.base import Provider, RenderTask
from ..memory.repository import InMemoryRepository, Repository
from ..safety.guards import REFUSAL_TEXT, detect_injection
from ..safety.redlines import (
    ConfirmationRequired,
    WriteBlocked,
    assert_write_allowed,
)
from .state import SessionView


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
    ) -> None:
        """创建会话并停在目标确认阶段。

        Args:
            card: 知识点卡，题量取自卡片。
            provider: 文案提供方。
            goal: 初始目标，通常为空。
            repository: 仓储，缺省用内存实现。
            consent: 授权状态，缺省全关。
        """
        self.card = card
        self.provider = provider
        self.repository = repository or InMemoryRepository()
        self.consent = consent or Consent()
        self.state = SessionState(card_id=card.id, hint_level=initial_level(), goal=goal)
        self._exercise_pos = 0
        self.receipts: list[Receipt] = []
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
        """记录并返回当前视图。"""
        self.view = view
        return view

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
                    ),
                    options=tuple(item.value for item in ErrorType),
                    notice="错因诊断只影响提示措辞，不改变判分。",
                )
            )

        self.state.phase = Phase.HINT
        self.state.hint_level = automatic_next_level(self.state.hint_level)
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
        if self.state.diagnosis is not None and self.consent.mistake_book:
            self._safe_write(
                "mistake",
                lambda: self.repository.update_mistake_error_type(
                    self.current_exercise.id, self.state.diagnosis
                ),
            )
        label = self.state.diagnosis.value if self.state.diagnosis else "未确定"
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

    def request_hint(self, kind: str) -> SessionView:
        """按门槛发放请求的提示。

        步骤与答案请求只把展示层级压到 L4，状态层级不回退；
        其余请求按 ``grant_requested_level`` 的结果展示。

        Args:
            kind: 请求类型，如 ``step`` / ``answer``。

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
        # 门槛按卡片会话累计：单题最多 3 次连错，集不齐 L1–L4
        attempted = {attempt["hint_level"] for attempt in self.state.attempts}
        # M1 只做门槛判定，实际可达性依赖 M2 连错诊断；测试覆盖门槛逻辑即可。
        level, message = grant_requested_level(self.state.hint_level, kind, attempted)
        self.state.hint_requests.append(kind)
        self.state.hint_level = level
        self.state.max_hint_level = max(self.state.max_hint_level, level)
        self.state.phase = Phase.HINT
        # 请求步骤/答案只降展示层级，不把 L5 状态退回 L4
        display_level = (
            min(level, MAX_REQUESTED_LEVEL)
            if kind in ("step", "answer")
            else level
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
        """从提示回到小测。"""
        if self.state.phase is not Phase.HINT:
            raise RuntimeError("当前不在提示阶段")
        self.state.phase = Phase.QUIZ
        return self._render_quiz()

    def _persist_receipt(self, receipt: Receipt) -> None:
        """按授权写入收据并登记复习。"""
        exercise = self.current_exercise
        if self.consent.memory:
            self._safe_write(
                "receipt",
                lambda: self.repository.save_receipt(receipt, exercise.id),
            )
        if self.consent.mistake_book:
            # 半独立答对降为 HINTED，避免被 FSRS 当作遗忘
            quality = quality_from_outcome(True, receipt.max_hint_level)
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
