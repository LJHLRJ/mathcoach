"""先修链诊断的文字视图：链路 + 原因 + 建议先复习卡片。"""
from mathcoach.domain.prerequisites import Gap
from mathcoach.session.diagnosis_view import render_gaps


def test_render_empty():
    """没有先修缺口时输出空字符串。"""
    assert render_gaps([]) == ""


def test_render_single_gap():
    """单个缺口输出完整链路与复习建议。"""
    gap = Gap(
        chain=("hs-calculus-derivative-001", "hs-calculus-limit-001", "hs-function-intro-001"),
        reason="前置知识点概念错 3/4 次",
    )
    text = render_gaps([gap])
    assert "hs-calculus-derivative-001" in text
    assert "hs-function-intro-001" in text
    assert "建议先复习" in text
