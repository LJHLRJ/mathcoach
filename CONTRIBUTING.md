# 贡献指南

感谢你愿意改进 MathCoach。本项目是**本地优先**的数学陪练应用：判定、提示阶梯、错因诊断、安全红线全部由 Python 确定性代码完成，LLM 只负责讲解措辞，可在完全离线的状态下运行完整闭环。

## 环境要求

- Python 3.11 或更高版本；CI 覆盖 3.11 与 3.12
- 不需要 OpenAI API Key；未配置时自动使用离线模板，判分逻辑不变
- 视觉回归测试额外需要 Chrome 与 `requirements-visual.txt`，日常开发不必安装

## 本地开发

```bash
git clone https://github.com/LJHLRJ/mathcoach.git
cd mathcoach
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## 提交前必须执行的检查

```bash
MATHCOACH_CONTENT_STRICT=1 python -m pytest -q
```

Windows PowerShell：

```powershell
$env:MATHCOACH_CONTENT_STRICT="1"; python -m pytest -q
```

PR 描述中请附上该命令的结果摘要（例如 `507 passed, 5 skipped`）。`MATHCOACH_CONTENT_STRICT=1` 会强制校验 `curriculum.yaml` 与卡片双向一致、每道 `expr` 题通过 AST 白名单。

## 代码边界（非常重要）

| 目录 | 可以做 | 不可以做 |
|---|---|---|
| `domain/` | 纯函数、数据模型 | import Streamlit / 网络 / 磁盘 |
| `session/` | 状态机推进 | 直接渲染 UI |
| `llm/` | 措辞生成、答案归一候选 | 决定提示层级、判分 |
| `safety/` | 注入守卫、写操作红线 | 把安全判定交给模型 |
| `verify/` | AST 白名单 + 符号验证 | `eval`、绕过白名单 |

**修改判定、提示阶梯、错因诊断、安全或调度行为时，必须在 PR 中单列“行为变更说明”，并说明为什么这不是设计取舍。** 仅修改测试来让失败的检查变绿是不被接受的。

## 新增知识卡片

1. 在 `content/<highschool|undergraduate|graduate>/<course>.yaml` 增加卡片；
2. 在 `content/learning_cards/<card_id>.md` 增加学习卡片；
3. 在 `content/knowledge_tree.yaml` 绑定 `exercise_id` 与知识点；
4. 如涉及先修关系，更新 `content/prerequisites.yaml`（必须无环）；
5. 运行 `MATHCOACH_CONTENT_STRICT=1 python -m pytest -q`。

题型仅限：`choice`、`multi`、`judge`、`fill`、`expr`、`proof_order`、`find_error`、`match`。`expr` 题的表达式必须能通过 `mathcoach/verify/symbolic.py` 的 AST 白名单。

## 提交与 PR

- 分支：`fix/<short-desc>`、`feat/<short-desc>`、`docs/<short-desc>`、`test/<short-desc>`
- Commit message 使用英文：`fix(ui): ...`、`fix(core): ...`、`feat(content): ...`、`test: ...`、`docs: ...`
- 一个 PR 只做一件事
- 不要提交 `*.db`、`*.sqlite3`、`dist/`、`.env`、`secrets.local`、`tests/visual/artifacts/`
- 新功能请先开 Issue 对齐范围，再提 PR

## 报告问题

请使用 Issue 模板，附上复现步骤、期望行为、实际行为、操作系统与 Python 版本、`pytest` 输出。安全相关问题请勿公开提交 Issue，按 [SECURITY.md](SECURITY.md) 私下报告。
