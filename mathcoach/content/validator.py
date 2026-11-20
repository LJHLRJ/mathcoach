"""加载期校验：一次列出全部问题；未完成条目受严格模式开关影响。"""
from dataclasses import dataclass, field

from ..verify.symbolic import expr_variables, validate_expression

ALLOWED_SOURCES = {"用户输入", "智能体生成", "工具返回"}
VALID_STAGES = {"highschool", "undergraduate", "graduate"}
CARD_FIELDS = (
    "id",
    "name",
    "stage",
    "course",
    "chapter",
    "difficulty",
    "intuition",
    "definition",
    "mistakes",
    "example",
    "exercises",
    "source",
)
KIND_REQUIRED = {
    "choice": ("options",),
    "multi": ("options",),
    "truefalse": (),
    "fill": (),
    "expr": (),
    "proof_order": (),
    "find_error": ("options",),
    "match": ("options",),
}
VALID_KINDS = set(KIND_REQUIRED)


@dataclass(frozen=True)
class Issue:
    location: str
    message: str


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _blank(data: dict, key: str) -> bool:
    """字段缺失或为空；注意 False / 0 是合法答案，不算空。"""
    return key not in data or data[key] is None or data[key] == "" or data[key] == []


_CONTAINER_SAMPLES = ("Symbol(('x',))", "[Symbol('x')]")


def _validate_expr_answer(
    exercise: dict, location: str, result: ValidationResult
) -> None:
    """expr 答案必须过白名单，并防止容器参数检查回退。"""
    answer = str(exercise.get("answer", ""))
    variables = expr_variables(answer)
    reason = validate_expression(answer, variables)
    if reason is not None:
        result.issues.append(Issue(location, f"expr 答案未通过 AST 白名单：{reason}"))

    for accepted in exercise.get("accepted") or []:
        text = str(accepted)
        accepted_reason = validate_expression(text, expr_variables(text))
        if accepted_reason is not None:
            result.issues.append(
                Issue(location, f"expr accepted 未通过 AST 白名单：{accepted_reason}")
            )

    for sample in _CONTAINER_SAMPLES:
        if validate_expression(sample, {"x"}) is None:
            result.issues.append(Issue(location, "符号验证门容器参数检查失效"))


def validate(curriculum: list[dict], cards: list[dict], strict: bool) -> ValidationResult:
    result = ValidationResult()
    pairs: set[tuple[str, str]] = set()
    referenced: set[str] = set()

    for index, entry in enumerate(curriculum):
        location = f"curriculum[{index}]"
        for key in ("stage", "course", "module", "chapter", "card_ids"):
            if _blank(entry, key):
                result.issues.append(Issue(location, f"缺少字段 {key}"))
        stage, course = entry.get("stage"), entry.get("course")
        if stage not in VALID_STAGES:
            result.issues.append(Issue(location, f"非法 stage：{stage!r}"))
        if stage and course:
            pairs.add((stage, course))
        referenced.update(entry.get("card_ids") or [])

    seen: set[str] = set()
    loaded: set[str] = set()
    for index, card in enumerate(cards):
        location = f"card[{index}]"
        for key in CARD_FIELDS:
            if key not in card:
                result.issues.append(Issue(location, f"缺少字段 {key}"))
        card_id = card.get("id")
        if not card_id:
            continue
        location = f"card[{card_id}]"
        if card_id in seen:
            result.issues.append(Issue(location, "id 重复"))
        seen.add(card_id)
        loaded.add(card_id)

        if card.get("stage") not in VALID_STAGES:
            result.issues.append(Issue(location, f"非法 stage：{card.get('stage')!r}"))
        if (card.get("stage"), card.get("course")) not in pairs:
            result.issues.append(Issue(location, "stage/course 不在 curriculum.yaml 索引中"))
        if card_id not in referenced:
            result.issues.append(Issue(location, "卡片未出现在任何 card_ids 中"))
        if card.get("source") not in ALLOWED_SOURCES:
            result.issues.append(
                Issue(location, f"source 必须是 {sorted(ALLOWED_SOURCES)} 之一")
            )

        exercises = card.get("exercises") or []
        if not exercises:
            result.issues.append(Issue(location, "至少需要 1 道题"))
        for ex_index, exercise in enumerate(exercises):
            ex_location = f"{location}.exercises[{ex_index}]"
            for key in ("id", "kind", "stem", "answer", "solution_outline"):
                if _blank(exercise, key):
                    result.issues.append(Issue(ex_location, f"缺少字段 {key}"))
            if exercise.get("id") and not str(exercise["id"]).startswith(f"{card_id}-"):
                result.issues.append(Issue(ex_location, "exercise.id 必须以 card_id 为前缀"))
            kind = exercise.get("kind")
            if kind not in VALID_KINDS:
                result.issues.append(Issue(ex_location, f"未知题型：{kind!r}"))
                continue
            for key in KIND_REQUIRED[kind]:
                if _blank(exercise, key):
                    result.issues.append(Issue(ex_location, f"{kind} 题缺少 {key}"))
            if kind in ("choice", "find_error"):
                options = exercise.get("options") or []
                if exercise.get("answer") not in options:
                    result.issues.append(Issue(ex_location, "answer 不在 options 中"))
            if kind == "multi":
                answers = exercise.get("answer")
                if not isinstance(answers, list):
                    result.issues.append(Issue(ex_location, "multi 的 answer 必须是列表"))
                else:
                    options = set(exercise.get("options") or [])
                    if not set(answers).issubset(options):
                        result.issues.append(
                            Issue(ex_location, "multi 的 answer 含 options 外的元素")
                        )
            if kind == "expr":
                _validate_expr_answer(exercise, ex_location, result)

    for card_id in sorted(referenced - loaded):
        issue = Issue(f"curriculum.card_ids[{card_id}]", "索引引用了未加载的卡片（未完成条目）")
        if strict:
            result.issues.append(issue)
        else:
            result.warnings.append(issue)

    return result
