"""会话状态机：只调用 domain 纯函数，不 import Streamlit。"""
from __future__ import annotations

from datetime import datetime, timezone

from ..domain.hint_ladder import (
    grant_requested_level,
    initial_level,
    next_level,
)
from ..domain.judge import judge
from ..domain.models import Exercise, KnowledgeCard, Phase, Receipt, SessionState
from ..domain.receipt import build_receipt
from ..llm.base import Provider, RenderTask
from .state import SessionView


class SessionEngine:
    def __init__(self, card: KnowledgeCard, provider: Provider, goal: str = "") -> None:
        self.card = card
        self.provider = provider
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
        return self.card.exercises[self._exercise_pos]

    def _set(self, view: SessionView) -> SessionView:
        self.view = view
        return view

    def confirm_goal(self, goal: str) -> SessionView:
        if self.state.phase is not Phase.GOAL_CONFIRM:
            raise RuntimeError("当前不在目标确认阶段")
        goal = goal.strip()
        if not goal:
            raise ValueError("目标不能为空")
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
        if self.state.phase is not Phase.EXPLAIN:
            raise RuntimeError("当前不在讲解阶段")
        self.state.phase = Phase.QUIZ
        self.state.exercise_id = self.current_exercise.id
        self.state.hint_level = initial_level()
        self.state.consecutive_wrong = 0
        return self._render_quiz()

    def _render_quiz(self) -> SessionView:
        exercise = self.current_exercise
        return self._set(
            SessionView(
                phase=Phase.QUIZ,
                title=f"小测 · 第 {self._exercise_pos + 1} / {len(self.card.exercises)} 题",
                body=exercise.stem,
                options=exercise.options,
                notice=f"当前提示层级 L{self.state.hint_level}",
            )
        )

    def submit_answer(self, answer: str) -> SessionView:
        if self.state.phase is not Phase.QUIZ:
            raise RuntimeError("当前不在小测阶段")
        exercise = self.current_exercise
        answer_level = self.state.hint_level  # 本次作答实际用到的层级
        self.state.attempts.append(
            {"exercise_id": exercise.id, "answer": answer, "hint_level": self.state.hint_level}
        )
        self.state.max_hint_level = max(self.state.max_hint_level, answer_level)
        if judge(exercise, answer):
            return self._issue_receipt()

        self.state.consecutive_wrong += 1
        if self.state.consecutive_wrong >= 3:
            self.state.phase = Phase.WRAPUP
            return self._set(
                SessionView(
                    phase=Phase.WRAPUP,
                    title="先停一下",
                    body=(
                        f"这道题连续答错 3 次。完整思路：{exercise.solution_outline}\n\n"
                        "本次不生成收据，建议换个时间重新练这道题。"
                    ),
                    receipts=tuple(self.receipts),
                )
            )

        self.state.phase = Phase.HINT
        self.state.hint_level = next_level(self.state.hint_level)
        return self._set(
            SessionView(
                phase=Phase.HINT,
                title=f"提示 L{self.state.hint_level}",
                body=self._hint_text(self.state.hint_level),
                notice="看完提示后回到原题再试一次。",
            )
        )

    def _hint_text(self, level: int) -> str:
        exercise = self.current_exercise
        if level <= 1:
            return "先说说这题在问什么、考哪个概念？"
        if level == 2:
            return "先看题目里的关键条件/最高阶项。"
        if level == 3:
            return f"回到概念：{self.card.intuition}"
        if level == 4:
            return f"只演示最关键一步：{exercise.solution_outline}"
        if level == 5:
            return f"完整推导：{exercise.solution_outline}"
        return "请用自己的话复述本题思路，再说出答案。"

    def request_hint(self, kind: str) -> SessionView:
        if self.state.phase not in (Phase.QUIZ, Phase.HINT):
            raise RuntimeError("当前不能请求提示")
        attempted = {attempt["hint_level"] for attempt in self.state.attempts}
        # M1 只做门槛判定，实际可达性依赖 M2 连错诊断；测试覆盖门槛逻辑即可。
        level, message = grant_requested_level(self.state.hint_level, kind, attempted)
        self.state.hint_level = level
        self.state.max_hint_level = max(self.state.max_hint_level, level)
        self.state.phase = Phase.HINT
        return self._set(
            SessionView(
                phase=Phase.HINT,
                title=f"提示 L{level}",
                body=f"{message}\n\n{self._hint_text(level)}",
                notice="看完提示后回到原题再试一次。",
            )
        )

    def retry(self) -> SessionView:
        if self.state.phase is not Phase.HINT:
            raise RuntimeError("当前不在提示阶段")
        self.state.phase = Phase.QUIZ
        return self._render_quiz()

    def _issue_receipt(self) -> SessionView:
        self.state.phase = Phase.RECEIPT
        elapsed = 0
        if self.state.started_at is not None:
            elapsed = int((datetime.now(timezone.utc) - self.state.started_at).total_seconds())
        receipt = build_receipt(
            card=self.card,
            exercise=self.current_exercise,
            goal=self.state.goal,
            max_hint_level=self.state.max_hint_level,
            duration_s=elapsed,
        )
        self.receipts.append(receipt)
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

    def advance(self) -> SessionView:
        if self.state.phase is not Phase.RECEIPT:
            raise RuntimeError("当前不在收据阶段")
        if self._exercise_pos + 1 < len(self.card.exercises):
            self._exercise_pos += 1
            self.state.phase = Phase.QUIZ
            self.state.hint_level = initial_level()
            self.state.consecutive_wrong = 0
            self.state.max_hint_level = 0  # 跨题不继承上一题的提示层级
            self.state.exercise_id = self.current_exercise.id
            return self._render_quiz()

        self.state.phase = Phase.WRAPUP
        independent = sum(
            1 for receipt in self.receipts if receipt.independence.value == "独立完成"
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
