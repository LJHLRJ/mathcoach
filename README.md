# 数学陪练（MathCoach）

本地优先的数学陪练 Streamlit 应用。核心循环为：目标确认 → 分层讲解 → 小测 → 错因反馈 → 收据 → 错题本 → 复习。

## 功能

- 覆盖高中 11 个模块、本科 6 门课、研究生 6 门课，共 122 张知识卡片、366 道练习。
- 8 种题型判定：选择、多选、判断、填空、表达式（sympy 等价）、步骤排序、找错、配对。
- 提示阶梯 L1–L6、连错 2 次错因诊断、连错 3 次收尾、独立/半独立收据。
- SQLite 本地记忆：收据、错题本、复习队列；游客模式只存内存。
- 学习仪表盘、每日挑战、挑战赛、学习路径、周报、错因趋势、智能复习包、错题变式。
- 知识点树与学习卡片：122 个知识点、122 张学习卡片、366 道题绑定、答题前“先学习”入口、解析与错因定位、掌握度/待复习学习闭环。
- 年级/难度标注与按年级筛选入口：题目级 `grade`/`difficulty`、知识点 `grade_span`、难度分组与“先学习本年级知识点”。
- 导出学习包：Markdown 学习包、独立收据/错题文件、Anki TSV（不生成 `.apkg`）。
- 安全层：注入守卫、数学伪装检测、写操作红线、脱敏与审计日志。

## 安全与边界

安全判定全部在本地执行，不依赖模型自检；写操作受同意状态、观察状态与确认语句约束。

### 安全测试覆盖

- 安全相关测试用例：22 项（`tests/test_guards.py` 9、`tests/test_redlines.py` 13；`test_safety*.py` 暂无用例）
- 注入样本拦截：9 / 10（按测试函数统计；反向用例计入样本，但不计入拦截）
- 脱敏样本替换：6 / 6（按测试函数统计）
- 数据来源：由 CI 在每次 push 时运行，结果见 GitHub Actions 的 pytest 输出。

统计口径：按文件名匹配 `test_safety*.py` / `test_guards*.py` / `test_redlines*.py`，统计以 `test_` 开头的函数；同一函数内多个样本只计 1 项。注入样本按函数名匹配 block / reject / inject，或函数体断言含 blocked / rejected / injection 识别；`test_safe_learning_text_is_allowed` 作为反向用例计入样本但不计入拦截。脱敏样本按 redact / masked / 已脱敏 识别；同一函数可同时命中两类。`test_audit.py`（2 项）与 `test_engine_safety.py`（4 项）不属于本小节文件口径，未计入。

## 下载与安装

当前版本：**v0.7.0**（2026-11-21）。下载入口以 GitHub Releases 为准：

- 最新稳定版：<https://github.com/LJHLRJ/mathcoach/releases/latest>
- 全部版本与 Release Notes：<https://github.com/LJHLRJ/mathcoach/releases>

| 平台 | 文件 | 安装方式 |
|---|---|---|
| Windows x64 | `MathCoachSetup-0.7.0.exe` | Inno Setup 安装器；按用户安装，无需管理员权限 |
| Windows x64 | `MathCoach-windows.zip` | 便携版；解压后运行 `MathCoach.exe` |
| macOS | `MathCoach-0.7.0.dmg` | 打开后将 `MathCoach.app` 拖到“应用程序” |
| macOS | `MathCoach-macos.zip` | 便携版；解压后打开 `MathCoach.app` |

- 当前仅提供稳定版，没有预览通道；变更记录见 GitHub Releases。
- 首次启动无需登录，也不要求配置 AI；未配置 Key 时使用离线模板。
- 应用“设置”Tab 中的“关于与更新”可检查新版本并打开下载页；启动时不自动联网，点击“检查更新”才请求 GitHub，不自动下载或安装。
- macOS 产物未签名、未公证；Release 未分别说明 Intel / Apple Silicon 架构，构建架构以 GitHub Actions Runner 为准（待确认）。
- Linux 未提供桌面安装包，请按下方“从源码安装”章节运行。

Windows 版 .exe 和 macOS 版 .dmg 未签名。首次运行时：Windows 可能弹出 SmartScreen 提示，点击“更多信息”→“仍要运行”；macOS 可能提示“无法验证开发者”或“已损坏”，前者可在“系统设置 → 隐私与安全性”中允许，后者需执行 `xattr -cr /Applications/MathCoach.app`。这是未签名应用的正常行为，不影响功能。

完整安装步骤、安装向导页面与当前限制、SHA256 校验、版本更新说明见 [docs/install.md](docs/install.md)。构建说明见 [desktop-packaging-plan.md](docs/packaging/desktop-packaging-plan.md)。

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

## 从源码安装

仅本地运行，默认不联网。未提供桌面安装包的平台（包括 Linux）按本节运行。

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
| M18 | 知识点树 + 学习卡片 + 解析/错因定位 + 学习闭环 | 已完成 | `content/knowledge_tree.yaml`、`content/learning_cards/`、`mathcoach/domain/explanation.py` |
| M19 | 年级/难度标注与按年级筛选入口 | 已完成 | `mathcoach/domain/grade_index.py`、`mathcoach/ui/grade_page.py`、`docs/grade-navigation.md` |

当前发布：**v0.7.0**（2026-11-21），Release 资产包含 Windows 安装器/便携版与 macOS DMG/便携版。

## 第三方资源与许可证

背景图案、反馈音与专注音频入口的来源、许可证和使用方式见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；背景、声音与专注音频的使用边界见 [docs/audio-and-backgrounds.md](docs/audio-and-backgrounds.md)。

## 动效与第三方资源

- 动态背景：Radiant（MIT），仅用于仪表盘/空状态装饰面板。
- 全屏庆祝：canvas-confetti（ISC），仅在明确里程碑触发。
- 微交互：自写常量 CSS，未引入 streamlit-animate 工具链。
- 未集成：css-doodle、weft-ui、matanim、handanim；许可证或依赖条件不满足。
- 完整来源、版权声明与使用方式见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 界面主题与交互

主题使用 Streamlit 原生 `[theme]` 配置；局部常量样式、按钮层级、骨架占位与布局密度集中在 `mathcoach/ui/theme.py` 与 `mathcoach/ui/components.py`。深浅色主题通过 `.streamlit/config.toml` 的 `base` 切换，修改后需重启；设置页“主题”只记录偏好，不会即时生效。完整说明、交互步骤与回退方式见 [docs/ui-polish.md](docs/ui-polish.md)。

## 知识点与学习闭环

知识点 ID 复用卡片 ID，层级与题目绑定集中在 `content/knowledge_tree.yaml`；学习卡片位于 `content/learning_cards/`。讲解页可“先学习此知识点”，答错后展示知识点定位、完整解析与错因定位；知识点页与练习结束页展示掌握度、收据/错题/待复习数量与下一步建议。完整说明、测试与回退方式见 [docs/knowledge-tree.md](docs/knowledge-tree.md)。

## 按年级与难度

题目级 `grade`/`difficulty` 与知识点 `grade_span` 已接入；侧边栏“按年级”提供年级/难度筛选、难度分组与“先学习本年级知识点”。当前所有题目年级统一标为 `mixed`，收据、错题本与复习队列保持全局共享。完整说明、分布与回退方式见 [docs/grade-navigation.md](docs/grade-navigation.md)。

## 免责声明

本项目集成的背景图案、音效与环境音来自第三方开源项目，其许可证以各项目仓库声明为准。我们已尽力核实许可证信息，但**不对第三方资源的版权状态作任何法律保证**，也不构成法律建议。

- CC0 / 公有领域资源：无需署名，但我们仍在 THIRD_PARTY_NOTICES.md 中列出来源以示尊重。
- MIT 资源：保留原版权声明与许可声明。
- 来源不明或许可证不清的资源：一律不使用。

若你是权利人并认为本项目使用不当，请通过仓库 Issue 联系，我们将在核实后移除相关内容。

用户自行选择的外部曲库与外部链接，其许可证与使用条款由对应项目负责，本项目仅提供入口，不承担相关责任。

### 动效与微交互

本项目的动态背景、庆祝动效与微交互参考了第三方开源资源，其许可证以各项目仓库声明为准。我们已尽力核实许可证信息，但**不对第三方资源的版权状态作任何法律保证**，也不构成法律建议。

- MIT / ISC / CC0 / 公有领域资源：按对应许可证使用；需要保留版权声明的，已在 THIRD_PARTY_NOTICES.md 中保留。
- 仅参考设计模式、未引入代码的资源：已注明“仅参考”。
- 来源不明或许可证不清的资源：一律不集成。

若你是权利人并认为本项目使用不当，请通过仓库 Issue 联系，我们将在核实后移除相关内容。

用户自行启用的动效与背景，其性能表现可能因设备而异，本项目不对特定设备上的帧率或耗电作保证。

## 设计文档

完整契约见 `docs/superpowers/specs/2026-11-20-math-coach-design.md`。
