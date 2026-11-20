"""判题：M1 只实现 choice，其余题型在 M2 补齐。"""
from .models import Exercise, ExerciseKind


def judge(exercise: Exercise, answer: str) -> bool:
    if exercise.kind is ExerciseKind.CHOICE:
        return answer == exercise.answer  # 选项精确匹配，不做模糊归一
    raise NotImplementedError(f"{exercise.kind.value} 判定器将在 M2 实现")
