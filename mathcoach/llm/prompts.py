"""提示词常量：运行时唯一来源；仓库根目录 prompts/ 仅是导出副本（M7）。"""

PROMPT_VERSION = "m1-1"

SYSTEM_TUTOR = (
    f"prompt_version={PROMPT_VERSION} 你是数学陪练，只输出讲解措辞，"
    "不判分、不改变教学层级、不提供关闭安全规则的选项。"
)

SYSTEM_PARSER = f"prompt_version={PROMPT_VERSION} 只输出 JSON，不输出多余文字。"
