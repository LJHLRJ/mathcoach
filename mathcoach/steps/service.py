"""步骤运行编排：判定、落库与 KC 影子观测。"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from ..domain.spaced_repetition import Quality
from ..tutor.attempts import TeachingAttempt
from ..tutor.mastery_store import KCMasteryStore
from .checker import StepVerifyFn, check_step
from .models import (
    StepAttempt,
    StepObservation,
    StepRun,
    StepSpec,
    StepVerdict,
    observations_for,
)
from .store import StepStore

FAST_STEP_SECONDS = 120.0


class StepRecorder:
    """一次分步作答的记录器。

    判定始终执行；只有 ``enabled`` 为真时才写步骤库与 KC 影子库。
    这样游客模式仍能获得步骤反馈，但不会留下学习记录。
    """

    def __init__(
        self,
        store: StepStore | None = None,
        kc_store: KCMasteryStore | None = None,
        *,
        enabled: bool = True,
        verify_fn: StepVerifyFn | None = None,
    ) -> None:
        self.store = store
        self.kc_store = kc_store
        self.enabled = enabled
        self.verify_fn = verify_fn

    def start(
        self, exercise_id: str, card_id: str, specs: tuple[StepSpec, ...]
    ) -> str:
        """创建一条步骤运行；未启用或没有存储时返回空串。"""
        if not (self.enabled and self.store is not None):
            return ""
        for pending in self.store.list_pending(exercise_id):
            self.abandon(pending.id)
        run = StepRun(
            exercise_id=exercise_id,
            card_id=card_id,
            kc_ids=tuple(
                dict.fromkeys(
                    spec.kc_id for spec in specs if spec.kc_id
                )
            ),
            step_count=len(specs),
        )
        self.store.save_run(run)
        return run.id

    def record(
        self,
        run_id: str,
        spec: StepSpec,
        answer: str,
        *,
        elapsed_s: float | None = None,
    ) -> StepAttempt:
        """判定并记录一条步骤作答。"""
        attempt = StepAttempt(
            run_id=run_id,
            exercise_id=spec.exercise_id,
            step_index=spec.index,
            input=answer,
            verdict=check_step(
                spec, answer, verify_fn=self.verify_fn
            ),
            expected=spec.expected,
            kc_id=spec.kc_id,
            step_tag=spec.step_tag,
            elapsed_s=elapsed_s,
        )
        if self.enabled and self.store is not None and run_id:
            self.store.add_attempt(attempt)
        return attempt

    def finalize(
        self,
        run_id: str,
        *,
        final_answer: str,
        final_correct: bool | None,
    ) -> StepRun | None:
        """补写最终答案，并在首次结算时应用 KC 影子观测。"""
        if not (self.enabled and self.store is not None and run_id):
            return None
        run = self.store.get_run(run_id)
        if run is None:
            return None
        attempts = tuple(
            sorted(run.attempts, key=lambda item: item.step_index)
        )
        failed_step = next(
            (
                attempt.step_index
                for attempt in attempts
                if attempt.verdict is StepVerdict.INCORRECT
            ),
            None,
        )
        missing = self._missing_steps(run)
        mismatch = (
            final_correct is False
            and bool(attempts)
            and not missing
            and all(
                attempt.verdict is StepVerdict.CORRECT
                for attempt in attempts
            )
        )
        apply_kc = not run.kc_applied
        updated = replace(
            run,
            final_answer=final_answer,
            final_correct=final_correct,
            failed_step_index=failed_step,
            missing_steps=missing,
            mismatch=mismatch,
            abandoned=False,
            kc_applied=run.kc_applied or apply_kc,
            updated_at=datetime.now(timezone.utc),
        )
        self.store.finalize_run(
            run_id,
            final_answer=final_answer,
            final_correct=final_correct,
            failed_step_index=failed_step,
            mismatch=mismatch,
            kc_applied=updated.kc_applied,
            missing_steps=missing,
            abandoned=False,
            now=updated.updated_at,
        )
        if apply_kc:
            self._apply_observations(updated)
        return updated

    def abandon(self, run_id: str) -> StepRun | None:
        """把未提交最终答案的步骤运行标记为放弃，并应用已有观测。"""
        if not (self.enabled and self.store is not None and run_id):
            return None
        run = self.store.get_run(run_id)
        if run is None:
            return None
        if run.kc_applied:
            return run
        attempts = tuple(
            sorted(run.attempts, key=lambda item: item.step_index)
        )
        failed_step = next(
            (
                attempt.step_index
                for attempt in attempts
                if attempt.verdict is StepVerdict.INCORRECT
            ),
            None,
        )
        missing = self._missing_steps(run)
        updated = replace(
            run,
            failed_step_index=failed_step,
            missing_steps=missing,
            mismatch=False,
            abandoned=True,
            kc_applied=True,
            updated_at=datetime.now(timezone.utc),
        )
        self.store.finalize_run(
            run_id,
            final_answer="",
            final_correct=None,
            failed_step_index=failed_step,
            mismatch=False,
            kc_applied=True,
            missing_steps=missing,
            abandoned=True,
            now=updated.updated_at,
        )
        self._apply_observations(updated)
        return updated

    @staticmethod
    def _missing_steps(run: StepRun) -> tuple[int, ...]:
        """返回没有提交记录的步骤序号。"""
        if run.step_count <= 0:
            return ()
        present = {attempt.step_index for attempt in run.attempts}
        return tuple(
            index
            for index in range(1, run.step_count + 1)
            if index not in present
        )

    def _apply_observations(self, run: StepRun) -> None:
        """把步骤观测写入 KC 影子库；没有影子库时跳过。"""
        if self.kc_store is None:
            return
        for observation in observations_for(run):
            quality = self._quality_for(run, observation)
            self.kc_store.record(
                TeachingAttempt(
                    kc_ids=(observation.kc_id,),
                    correct=observation.correct,
                    quality=quality,
                    source="immediate",
                )
            )

    @staticmethod
    def _quality_for(
        run: StepRun, observation: StepObservation
    ) -> Quality | None:
        """按过程信号选择观测质量；不修改 BKT 公式。"""
        if not observation.correct:
            return None
        if (
            run.abandoned
            or observation.missing_before
            or observation.elapsed_s is None
            or observation.elapsed_s > FAST_STEP_SECONDS
        ):
            return Quality.HINTED
        return Quality.INDEPENDENT

    def close(self) -> None:
        """关闭步骤库与影子库连接。"""
        if self.store is not None:
            self.store.close()
        if self.kc_store is not None:
            self.kc_store.close()
