# 数学陪练（MathCoach）

本地优先的数学陪练 Streamlit 应用。核心循环为：目标确认 → 分层讲解 → 小测 → 错因反馈 → 收据 → 错题本 → 复习。

## 功能

- 覆盖高中 11 个模块、本科 6 门课、研究生 6 门课，共 122 张知识卡片、366 道练习。
- 8 种题型判定：选择、多选、判断、填空、表达式（sympy 等价）、步骤排序、找错、配对。
- 提示阶梯 L1–L6、连错 2 次错因诊断、连错 3 次收尾、独立/半独立收据。
- SQLite 本地记忆：收据、错题本、复习队列；游客模式只存内存。
- 学习仪表盘、每日挑战、挑战赛、学习路径、周报、错因趋势、智能复习包、错题变式。
- 导出学习包：Markdown 学习包、独立收据/错题文件、Anki TSV（不生成 `.apkg`）。
- 安全层：注入守卫、数学伪装检测、写操作红线、脱敏与审计日志。

## 安全与边界

安全判定全部在本地执行，不依赖模型自检；写操作受同意状态、观察状态与确认语句约束。

### 安全测试覆盖

- 安全相关测试用例：22 项（`tests/test_guards.py` 9、`tests/test_redlines.py` 13；`test_safety*.py` 暂无用例）
- 注入样本拦截：9 / 9（按测试函数统计，全部拦截）
- 脱敏样本替换：6 / 6（按测试函数统计）
- 数据来源：由 CI 在每次 push 时运行，结果见 GitHub Actions 的 pytest 输出。

统计口径：按文件名匹配 `test_safety*.py` / `test_guards*.py` / `test_redlines*.py`，统计以 `test_` 开头的函数；同一函数内多个样本只计 1 项；按函数名或断言中的 blocked / rejected / injection / 拒绝 识别拦截用例，`safe_*` 等反向用例不计入。`test_audit.py`（2 项）与 `test_engine_safety.py`（4 项）不属于本小节文件口径，未计入。

补充口径：若将 `test_audit.py` 与 `test_engine_safety.py` 合并统计，共 28 个用例；其中显式注入样本 10/10 拦截、脱敏断言样本 12/12 替换。

## 桌面客户端

Windows 提供 `MathCoachSetup-<version>.exe`（按用户安装，含开始菜单与卸载项）和便携 zip；macOS 提供 `MathCoach-<version>.dmg` 和便携 zip。应用“设置”Tab 中的“关于与更新”可检查新版本并打开下载页，不自动下载或安装。构建说明见 [desktop-packaging-plan.md](docs/packaging/desktop-packaging-plan.md)。

Windows 版 .exe 和 macOS 版 .dmg 未签名。首次运行时：Windows 可能弹出 SmartScreen 提示，点击“更多信息”→“仍要运行”；macOS 可能提示“无法打开”，需在“系统设置 → 隐私与安全性”中允许。这是未签名应用的正常行为，不影响功能。

## 目录

```text
app.py                  Streamlit 装配
mathcoach/
  domain/               纯数据模型与判定/诊断/收据
  session/              状态机、每日挑战、挑战赛
  content/              卡片加载与严格校验
  memory/               SQLite/内存仓储、调度、周报、学习路径、导出
  safety/               注入守卫与写操作红线
  verify/               受限 AST 符号验证门
  llm/                  Provider 与运行时提示词常量
content/                知识卡片与 curriculum.yaml
prompts/                提示词评审副本（运行时不读取）
tests/                  单元测试与 AppTest 冒烟
docs/                   设计文档与实施计划
```

## 安装

仅本地运行，默认不联网。

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

如需接入 OpenAI 兼容模型，可设置：

```bash
export OPENAI_BASE_URL="https://your-endpoint/v1"
export OPENAI_API_KEY="..."
export MODEL="your-model"
```

未配置 Key 或请求失败时自动使用离线模板模式，判分逻辑不变。

## 运行

从源码运行：

```bash
streamlit run app.py
```

也可以安装为本地包后运行（安装包包含 `app.py` 与全部知识卡片）：

```bash
pip install .
mathcoach
```

## 测试

```bash
MATHCOACH_CONTENT_STRICT=1 python -m pytest -q
```

`MATHCOACH_CONTENT_STRICT=1` 会强制校验 `curriculum.yaml` 与卡片双向一致、每道 `expr` 题通过 AST 白名单。

视觉回归测试：通过 `.github/workflows/visual-regression.yml` 在 CI 中运行，基线图位于 `tests/visual/baselines/`。

## 打包（仅记录命令，不在仓库内自动执行）

```bash
pip install build
python -m build
```

产物位于 `dist/`，仅包含源代码与内容，不包含学习数据。

## 学习数据与隐私

- SQLite 默认位于用户数据目录（`platformdirs.user_data_dir("mathcoach")`），可用 `MATHCOACH_DB` 覆盖。
- 学习数据不写入仓库、不写日志文件、不参与训练或共享。
- 游客模式（consent 全关）使用内存仓储，进程结束即丢弃。
- 导出目录必须在仓库之外；导出前展示摘要并要求输入完整确认语句「我确认执行此操作」。
- `audit_log` 只记录操作类型、时间与结果，不含 Token 与学习内容。

## 提示词

- 运行时唯一来源：`mathcoach/llm/prompts.py`（代码内常量，带 `prompt_version`）。
- `prompts/` 仅为评审副本，运行时不读取，避免文件被篡改后改变行为。

## 里程碑

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M1 | 骨架 + 单卡片单闭环 | 已完成 |
| M2 | 8 种题型判定 + 符号验证门 + 连错诊断 | 已完成 |
| M3 | SQLite 记忆层 + 侧边栏 | 已完成 |
| M4 | 卡片扩容至约 120 张 | 已完成（122 张） |
| M5 | 安全层 | 已完成 |
| M6a | 仪表盘 + 每日挑战 + 错题变式 | 已完成 |
| M6b | 学习路径 + 周报 + 挑战赛 + 智能复习包 + 错因趋势 | 已完成 |
| M7 | 文档与提示词文件 + 导出学习包 | 已完成 |

### 后续里程碑（进行中/已完成）

| 里程碑 | 内容 | 状态 | 证据 |
|---|---|---|---|
| M8 | SM-2 简化调度 + 先修链诊断 | 已完成 | `mathcoach/domain/spaced_repetition.py`、`mathcoach/domain/prerequisites.py` |
| M9 | FSRS 调度 | 已完成 | `mathcoach/domain/fsrs.py` |
| M10 | 收据与诊断“依据”字段 | 已完成 | `mathcoach/domain/basis.py` |
| M11 | 交互式可视化试点 | 已完成 | `mathcoach/ui/visuals/` |
| M12 | BKT 掌握概率 | 已完成 | `mathcoach/domain/bkt.py` |
| M13 | 智能复习包混合队列 | 已完成 | `mathcoach/domain/review_pack.py` |
| M14 | 学习路径推荐 | 已完成 | `mathcoach/domain/learning_path.py` |
| M15 | 叙事化游戏化 | 已完成 | `mathcoach/domain/narrative.py`、`content/narrative.yaml` |
| M16 | GitHub Actions 自动打包 | 已完成 | `.github/workflows/build-desktop.yml` |
| M17 | 界面优化与美化 | 已完成（v0.5.0） | `.streamlit/config.toml`、`mathcoach/ui/layout.py`、`mathcoach/ui/icons.py` |

当前发布：**v0.5.1**（2026-11-21），Release 资产包含 Windows 安装器/便携版与 macOS DMG/便携版。

## 设计文档

完整契约见 `docs/superpowers/specs/2026-11-20-math-coach-design.md`。
