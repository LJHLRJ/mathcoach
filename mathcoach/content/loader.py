"""卡片加载：YAML → dataclass，启动即校验，失败中止。"""
from pathlib import Path

import yaml

from ..domain.models import Difficulty, Exercise, ExerciseKind, KnowledgeCard, Stage
from .validator import ValidationResult, validate

CURRICULUM_FILE = "curriculum.yaml"
PREREQUISITES_FILE = "prerequisites.yaml"


class ContentError(RuntimeError):
    """内容校验失败：启动中止。"""


def _read_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or []


def load_curriculum(root: Path) -> list[dict]:
    return _read_yaml(Path(root) / CURRICULUM_FILE)


def load_raw_cards(root: Path) -> list[dict]:
    root = Path(root)
    cards: list[dict] = []
    for path in sorted(root.rglob("*.yaml")):
        # 顶层 YAML 是课程索引或参数配置；知识卡片必须放在学段子目录
        if path.parent == root:
            continue
        data = _read_yaml(path)
        if isinstance(data, list):
            cards.extend(data)
        elif isinstance(data, dict):
            cards.append(data)
    return cards


def load_prerequisites(root: Path) -> dict[str, list[str]]:
    """读取先修关系；文件不存在时返回空关系，便于渐进启用。"""
    path = Path(root) / PREREQUISITES_FILE
    if not path.exists():
        return {}
    data = _read_yaml(path)
    if not isinstance(data, dict):
        raise ContentError(f"{PREREQUISITES_FILE} 必须是字典：card_id -> [先修 card_id]")
    return {
        str(child): [str(parent) for parent in (parents or [])]
        for child, parents in data.items()
    }


def _canonical_answer(value) -> str:
    """把 YAML 的列表/字典答案规范成判定器约定的字符串形式。"""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (list, tuple)):
        return ",".join(_canonical_answer(item) for item in value)
    if isinstance(value, dict):
        return ";".join(
            f"{_canonical_answer(key)}={_canonical_answer(item)}"
            for key, item in value.items()
        )
    return str(value)


def _exercise_from_dict(card_id: str, data: dict) -> Exercise:
    return Exercise(
        id=data["id"],
        card_id=card_id,  # 由所属卡片注入，避免 YAML 重复维护
        kind=ExerciseKind(data["kind"]),
        stem=data["stem"],
        answer=_canonical_answer(data["answer"]),
        solution_outline=data["solution_outline"],
        options=tuple(data.get("options") or ()),
        accepted=tuple(_canonical_answer(item) for item in (data.get("accepted") or ())),
        variants=tuple(data.get("variants") or ()),
    )


def _card_from_dict(data: dict) -> KnowledgeCard:
    return KnowledgeCard(
        id=data["id"],
        name=data["name"],
        stage=Stage(data["stage"]),
        course=data["course"],
        chapter=data["chapter"],
        difficulty=Difficulty(data["difficulty"]),
        intuition=data["intuition"],
        definition=data["definition"],
        mistakes=tuple(data.get("mistakes") or ()),
        example=data["example"],
        exercises=tuple(_exercise_from_dict(data["id"], ex) for ex in data["exercises"]),
        source=data["source"],
    )


def load_content(root: Path, strict: bool) -> tuple[list[KnowledgeCard], ValidationResult]:
    root = Path(root)
    curriculum = load_curriculum(root)
    raw_cards = load_raw_cards(root)
    result = validate(curriculum, raw_cards, strict=strict)
    if not result.ok:
        lines = [f"{issue.location}: {issue.message}" for issue in result.issues]
        raise ContentError("内容校验失败：\n" + "\n".join(lines))
    return [_card_from_dict(card) for card in raw_cards], result
