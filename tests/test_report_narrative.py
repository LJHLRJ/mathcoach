"""报告受限叙事：结论绑定、数字白名单、因果拒绝与模板回退。"""
import json
from datetime import datetime, timedelta, timezone

from mathcoach.llm import OfflineProvider
from mathcoach.report import (
    EvidenceAnchor,
    ExplainableReport,
    ReportConclusion,
    ReportMetric,
    build_report_client,
    generate_report_narrative,
    render_narrative_markdown,
)

NOW = datetime(2026, 11, 28, 9, 0, tzinfo=timezone.utc)
CONCLUSION_ID = "weak-kc:kc-hs-trig-002-f1"


def _report() -> ExplainableReport:
    """构造一条带数字与证据的结论。"""
    conclusion = ReportConclusion(
        id=CONCLUSION_ID,
        kind="weak_kc",
        statement=(
            "「同角平方关系」当前掌握度 20%，"
            "是近 7 天最需要优先补强的知识点。"
        ),
        metrics=(
            ReportMetric(
                "kc.mastery", 0.2, "概率", "同角平方关系掌握度"
            ),
        ),
        evidence=(
            EvidenceAnchor(
                kind="mistake",
                id="m1",
                exercise_id="hs-trig-002-e2",
                card_id="hs-trig-002",
                occurred_at=NOW - timedelta(days=1),
                snippet="作答 9/25 → 正确答案 16/25",
            ),
        ),
    )
    return ExplainableReport(
        start=NOW - timedelta(days=7),
        end=NOW,
        conclusions=(conclusion,),
        generated_at=NOW,
    )


class _Client:
    """返回固定 JSON 的假客户端。"""

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(self.payload, ensure_ascii=False)


class _RawClient:
    """返回原始文本的假客户端。"""

    def __init__(self, text: str) -> None:
        self.text = text

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.text


def _payload(text: str, conclusion_id: str = CONCLUSION_ID) -> dict:
    """构造一份叙事 JSON。"""
    return {
        "sections": [
            {"conclusion_id": conclusion_id, "text": text}
        ]
    }


def test_valid_narrative_is_accepted_and_keeps_evidence() -> None:
    """合规改写被接受，证据锚点仍来自统计层。"""
    report = _report()
    client = _Client(_payload("同角平方关系掌握度 20%，建议优先补强。"))

    narrative, reason = generate_report_narrative(
        report, client=client
    )

    assert reason == ""
    assert narrative is not None
    markdown = render_narrative_markdown(report, narrative)
    assert "建议优先补强" in markdown
    assert "mistake:m1" in markdown


def test_new_number_is_rejected() -> None:
    """叙事新增统计层之外的数字时回退。"""
    report = _report()
    client = _Client(_payload("同角平方关系掌握度 35%，建议优先补强。"))

    narrative, reason = generate_report_narrative(
        report, client=client
    )

    assert narrative is None
    assert "未授权数字" in reason


def test_new_conclusion_is_rejected() -> None:
    """叙事新增或替换结论 ID 时回退。"""
    report = _report()
    client = _Client(_payload("掌握度 20%。", conclusion_id="new-id"))

    narrative, reason = generate_report_narrative(
        report, client=client
    )

    assert narrative is None
    assert "结论集合不一致" in reason


def test_causal_claim_is_rejected() -> None:
    """叙事加入因果判断时回退。"""
    report = _report()
    client = _Client(
        _payload("因为掌握度只有 20%，所以建议优先补强。")
    )

    narrative, reason = generate_report_narrative(
        report, client=client
    )

    assert narrative is None
    assert "因果" in reason


def test_missing_number_is_rejected() -> None:
    """叙事没有保留任何统计层数字时回退。"""
    report = _report()
    client = _Client(_payload("同角平方关系需要优先补强。"))

    narrative, reason = generate_report_narrative(
        report, client=client
    )

    assert narrative is None
    assert "缺少统计层数字" in reason


def test_invalid_json_falls_back() -> None:
    """非 JSON 输出回退到模板。"""
    report = _report()
    client = _RawClient("not json")

    narrative, reason = generate_report_narrative(
        report, client=client
    )

    assert narrative is None
    assert reason == "llm_unavailable"


def test_offline_provider_has_no_report_client() -> None:
    """离线 Provider 没有 complete，不启用 LLM 叙事。"""
    assert build_report_client(OfflineProvider()) is None
