"""先修链诊断文字视图：只渲染，不做判定。"""
from ..domain.prerequisites import Gap


def render_gaps(gaps: list[Gap]) -> str:
    if not gaps:
        return ""
    lines = ["**先修诊断**"]
    for gap in gaps:
        chain = " → ".join(gap.chain)
        target = gap.chain[-1]
        lines.append(f"- 当前卡点：{chain}\n  原因：{gap.reason}\n  建议先复习：{target}")
        if gap.basis:
            lines.append(f"  依据：{gap.basis}")
    return "\n".join(lines)
