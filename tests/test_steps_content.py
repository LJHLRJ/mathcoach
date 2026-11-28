"""hs-trig 全部步骤：每条元数据的标准答案都能被判为正确。"""
from mathcoach.steps import STEP_SPECS, StepVerdict, check_step


def test_every_step_accepts_its_expected_answer() -> None:
    """逐条检查步骤元数据，防止拼写或符号与判定器不一致。"""
    failures: list[str] = []
    for exercise_id, specs in STEP_SPECS.items():
        for spec in specs:
            verdict = check_step(spec, spec.expected)
            if verdict is not StepVerdict.CORRECT:
                failures.append(
                    f"{exercise_id} L{spec.index}: "
                    f"{spec.expected!r} -> {verdict.value}"
                )

    assert failures == []
