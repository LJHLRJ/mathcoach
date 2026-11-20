# 数学陪练软件 · 设计文档

- 日期：2026-11-20
- 状态：已评审通过（设计阶段）
- 范围：全学段（高中 / 本科 / 研究生）数学陪练软件，第一期交付 Streamlit 本地 Web 应用
- 规范来源：用户提供的《数学陪练智能体行为规范》（下称“规范”），本文件把规范落为可实现的软件契约

---

## 1. 目标与非目标

### 1.1 目标

1. 让学习者在一个 5 分钟微闭环内完成：概念分层讲解 → 一道小测 → 错因反馈 → 复盘。
2. 用代码兑现规范中**可验证**的部分：提示阶梯、判题、错因归类、能力收据、错题本状态、复习调度、安全红线。
3. 覆盖高中 11 个模块、本科 6 门课、研究生 6 门课，每门课/模块 5–8 张精写知识卡片，合计约 120 张。
4. 本地优先：学习数据只存本机 SQLite，默认不联网、不写入仓库。

### 1.2 非目标（第一期明确不做）

- 语音输入、图片/公式手写识别、桌面通知、移动端适配。
- GitHub 写操作（Issue/PR 自动创建）、GitHub Pages、任何自动部署。
- 自动下载、自动安装、自动打包、上传产物。
- 从第三方仓库整段复制内容（只参考课程结构与大纲，卡片自写）。

---

## 2. 核心架构决策

**采用混合架构：确定性状态机 + 模型只负责讲解。**

| 关注点 | 由谁决定 |
|---|---|
| 提示层级升降、连续答错处理、收据门槛、游客模式 | Python 代码（可单测） |
| 判题、错因归类、复习调度 | Python 代码（纯函数） |
| 讲解措辞、自由文本作答的归一解析 | LLM（可降级为模板） |
| 安全红线、写入许可 | Python 代码（显式异常） |

被否决的方案：提示词驱动（规则无法测试、判分不可复现）；前后端分离（第一期过度设计）。

### 2.1 分层

| 层 | 职责 | 约束 |
|---|---|---|
| `app.py` | Streamlit 装配、页面渲染 | 只调用 `session` 层，不含判定逻辑 |
| `session/` | 会话状态机：阶段推进、升降级、收据触发 | 所有可测行为收敛于此 |
| `domain/` | 纯数据结构与纯函数 | **不 import** Streamlit / 网络 / 磁盘库 |
| `content/` | 卡片加载与校验 | 卡片是数据文件，扩内容不改代码 |
| `llm/` | Provider 抽象与提示词构造 | 只产出措辞，不决定层级、不判分 |
| `memory/` | 档案、收据、错题本、复习调度（SQLite） | 默认本地，无远端写入 |
| `safety/` | 注入守卫、红线检查、脱敏 | 纯函数 + 显式异常 |
| `verify/` | 符号验证拒绝门 | 严格 AST 白名单，绝不 `eval` |

### 2.2 目录结构

```
/workspace
├── app.py
├── pyproject.toml
├── requirements.txt
├── README.md
├── mathcoach/
│   ├── __init__.py
│   ├── config.py
│   ├── domain/
│   │   ├── models.py
│   │   ├── hint_ladder.py
│   │   ├── diagnosis.py
│   │   └── receipt.py
│   ├── session/
│   │   ├── state.py
│   │   └── engine.py
│   ├── content/
│   │   ├── loader.py
│   │   └── validator.py
│   ├── llm/
│   │   ├── base.py
│   │   ├── openai_provider.py
│   │   ├── offline_provider.py
│   │   └── prompts.py
│   ├── memory/
│   │   ├── repository.py
│   │   ├── sqlite_repo.py
│   │   └── scheduler.py
│   ├── safety/
│   │   ├── guards.py
│   │   └── redlines.py
│   └── verify/
│       └── symbolic.py
├── content/
│   ├── curriculum.yaml
│   ├── highschool/
│   ├── undergraduate/
│   └── graduate/
├── tests/
└── docs/
```

---

## 3. 领域模型

全部为不可变 dataclass（pydantic v2 用于外部数据校验，内部传递用 dataclass）。

```text
Stage        = HIGH_SCHOOL | UNDERGRADUATE | GRADUATE
Difficulty   = BASIC | INTERMEDIATE | CHALLENGE        # 基础 / 进阶 / 挑战
HintLevel    = L0..L6
ErrorType    = CONCEPT | FORMULA | CALCULATION | READING | STEP_JUMP
ReviewState  = UNREVIEWED | REVIEWING | MASTERED
Independence = INDEPENDENT | SEMI_INDEPENDENT
Consent      = {memory: bool, mistake_book: bool}
```

- `KnowledgeCard(id, name, stage, course, chapter, difficulty, intuition, definition, mistakes[], example, exercises[], source)`
- `Exercise(id, card_id, kind, stem, options?, answer, accepted?, solution_outline, variants[])`
- `MistakeEntry(id, exercise_snapshot, user_answer, correct_answer, error_type, stage, course, exercise_type, card_id, max_hint_level, created_at, review_state, review_count, receipt_ids[])`
- `Receipt(id, card_id, stage, course, exercise_type, duration_s, max_hint_level, restatement_quality, goal, independence, created_at)`
- `LearnerProfile(display_name, stage, course, goal, preferred_mode, consent)`
- `SessionState(phase, card_id, exercise_id, hint_level, consecutive_wrong, attempts[], started_at)`

### 3.1 会话状态机

```text
GOAL_CONFIRM → EXPLAIN → QUIZ → JUDGE
                                 ├─ 正确且未用提示 → RECEIPT → (下一题 | WRAPUP)
                                 ├─ 正确但用过提示 → RECEIPT(半独立) → (下一题 | WRAPUP)
                                 └─ 错误 → HINT(升一级) → QUIZ
                                                └─ 连续答错 2 次 → DIAGNOSE → HINT
```

代码强制的四条规则：

1. **升降级**：默认从 L1 起；用户说“给步骤”最高到 L4；说“直接给答案”也只到 L4，并说明 L5 需先尝试；L5 仅在 L1–L4 均已尝试且用户明确请求时开放；L6 必须完成复述或变式才算闭环。
2. **连续答错**：连错 2 次先做错因诊断（五类之一）并一句话确认；连错 3 次触发反脆弱——降一档难度并给保底题。
3. **收据门槛**：仅在独立做对或费曼复述通过时生成；`max_hint_level >= L4` 标记为“半独立完成”；无收据的“已掌握”不进入复习清单。
4. **游客模式**：`consent` 全关时，`memory/` 一律不写入，收据只在会话内存中展示。

### 3.2 数据流

```text
UI event → session.engine.handle(event) → domain 纯函数判定
        → (consent 允许) memory.repository.save(...)
        → llm.render(...) 生成措辞
        → UI 渲染
```

自由文本作答：`llm.parse_freeform` 归一为结构化答案后由代码比对；无法归一或符号验证未通过时，界面标注“建议人工核对”，不伪装成确定判分。

---

## 4. 知识卡片体系

### 4.1 覆盖范围（`content/curriculum.yaml` 为唯一索引）

- 高中（11 模块）：集合与逻辑、函数与导数、三角函数、数列、不等式、立体几何、解析几何、概率统计、复数、平面向量、计数原理
- 本科（6 门）：高等数学、线性代数、概率论与数理统计、复变函数、常微分方程、数值分析基础
- 研究生（6 门）：矩阵论、泛函分析、数值分析进阶、数理方程、随机过程、最优化方法

密度：每门课/模块 5–8 张卡片，合计约 120 张；每卡 3 道题，至少 1 道变式。

### 4.2 卡片 schema

```yaml
id: ug-calculus-limit-001
name: 无穷小的阶
stage: undergraduate
course: 高等数学
chapter: 极限
difficulty: 进阶
source: 用户输入 | 智能体生成 | 工具返回
intuition: 比较谁“跑得快”
definition: 若 beta/alpha -> 0，则称 beta 是 alpha 的高阶无穷小，记 beta = o(alpha)
mistakes: [把“阶”当成大小比较, 忽略趋于 0 的前提]
example: 当 x->0 时，1-cos x ~ x^2/2
exercises:
  - id: ug-calculus-limit-001-e1
    kind: choice
    stem: 当 x->0 时，x^3 是 x 的（ ）阶无穷小
    options: [高阶, 同阶, 低阶, 等价]
    answer: 高阶
    solution_outline: x^3/x -> 0
```

### 4.3 题型（8 种，全部实现判定器）

| kind | 判定方式 |
|---|---|
| `choice` | 选项精确匹配 |
| `multi` | 集合相等 |
| `truefalse` | 布尔匹配 |
| `fill` | 归一化后精确匹配，数值题带容差 |
| `expr` | 受限 AST → sympy 等价判定（见 §7） |
| `proof_order` | 步骤序列与标准顺序一致（允许等价相邻） |
| `find_error` | 选出错误的步骤编号 |
| `match` | 左右配对完全一致 |

每题必须有 `solution_outline`，供 L4 只演示最关键一步。

### 4.4 加载期校验（`content/validator.py`，启动即跑）

- id 全局唯一，`card_id` 与 `exercise.id` 前缀一致；
- `stage` / `course` 必须存在于 `curriculum.yaml`；
- 每题答案非空、对应题型字段齐全；
- `expr` 题答案必须通过 AST 白名单解析；
- 校验失败直接中止加载，列出全部问题，不做静默容错。

---

## 5. LLM 层

```python
class Provider(Protocol):
    def render(self, task: RenderTask) -> str: ...
    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer: ...
```

- `openai_compatible`：读 `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `MODEL`，超时 30s，重试 1 次，不流式。
- `offline_template`：用卡片字段拼装确定性文案；`parse_freeform` 返回 `UNPARSED`，界面请用户改用选项作答。
- 降级触发：未配置 Key、请求失败、超时 → 切换离线并界面明示“离线模板模式”。
- `prompts.py` 中每条提示词带 `prompt_version`；提示词中不含任何“关闭安全规则”的可选项。

---

## 6. 存储

- SQLite，默认 `~/.mathcoach/profile.db`，可用 `MATHCOACH_DB` 覆盖；**位于仓库之外**。
- 表：`schema_version`、`profile`、`consent`、`receipts`、`mistakes`、`review_queue`。
- 游客模式装配 `InMemoryRepository`，进程结束即丢弃。
- 学习数据不写入仓库、不写日志文件、不参与训练或共享。
- 复习调度：优先 `UNREVIEWED` 与 `REVIEWING`；连续两次独立做对后转 `MASTERED` 并退出清单；生成“今天 / 明天 / 三天后”三档，每档不超过 3 项。

---

## 7. 符号验证拒绝门

`verify/symbolic.py` 的执行顺序：

1. `ast.parse(expr, mode="eval")`；
2. 白名单遍历：仅允许 `Expression`、`BinOp`（`+ - * / **`）、`UnaryOp`、`Call`（函数名必须在白名单）、`Name`（变量必须在显式白名单）、数值常量；**拒绝**属性访问、下标、lambda、推导式、f-string、容器参数中的字符串、任何 import；
3. 通过后用受限 `global_dict` 转换为 sympy 表达式；
4. 等价判定在子进程内执行 `simplify(a - b) == 0` 并设超时；
5. 超时、异常、非预期类型 → 返回 `UNVERIFIED`，界面标注“需人工核对”，不继续推导。

---

## 8. 安全层

### 8.1 `guards.py`

检测并阻断：忽略以上指令、索要系统提示词、切换“无限制模式”、启用/部署 Pages、生成任务文件、自动下载/安装/打包、批量导出、零宽字符、混用文字系统、同形字、任务框架重构（“这是 CTF/演示/评审测试”）。命中返回 `Blocked(reason)`，界面只回一句简短拒绝并回到学习任务。

### 8.2 `redlines.py`

`assert_write_allowed(op, payload)` 统一拦截落盘与导出动作：

- 校验 `consent`；
- 观察状态下（本次会话出现过边界请求）要求用户回复完整句“我确认执行此操作”，仅回“确认”不通过；
- 写入前打印摘要供确认；**例外**：`consent.mistake_book` / `consent.memory` 已开启时，收据与错题本的常规写入属授权范围内操作，自动执行并告知，不逐次确认；导出、GitHub、超出授权范围的写入必须逐次确认；
- 脱敏：Token / API Key / 手机号 / 身份证 → `[已脱敏]`；
- 禁止项：学习数据、错题本、收据、记忆数据、音频、打包产物、Pages 配置、任务文件写入仓库。

### 8.3 GitHub

第一期只有“生成草稿文本”能力，代码中不存在 push / merge / Pages 调用。任何 GitHub 写操作必须走“草稿 → 用户确认 → 执行”三步，并留一行审计记录（不含 Token）。

---

## 9. 测试策略

TDD：先写失败用例再实现。

| 测试对象 | 要求 |
|---|---|
| `domain/` 纯函数 | 全覆盖：升降级、诊断分类、收据门槛、调度 |
| `content/` | 全部卡片可加载、schema 校验通过、id 唯一 |
| 判定器 | 8 种题型各含正例、反例、边界 |
| `session/` | 状态机全部转移路径 |
| `safety/` | 注入样本必须全部被拦；脱敏样本必须被替换 |
| `verify/` | `__import__('os')`、`open('/etc/passwd')`、容器内字符串、属性访问必须被拒 |
| `llm/` | 假 Provider，测试**不联网** |
| UI | `streamlit.testing.v1.AppTest` 冒烟：首屏可渲染、能完成一次闭环 |

---

## 10. 里程碑

| 里程碑 | 内容 | 完成判据 |
|---|---|---|
| M1 | 骨架 + 单卡片单闭环 | `pytest` 全绿；`streamlit run app.py` 可完成一次讲解→小测→反馈 |
| M2 | 8 种题型判定器 + 符号验证门 | 判定器测试全绿；恶意表达式全被拒 |
| M3 | SQLite 记忆层 + 侧边栏 | 重启后错题本与复习清单仍在；游客模式不落盘 |
| M4 | 卡片扩容至约 120 张 | 启动校验全绿；每门课 5–8 张 |
| M5 | 安全层 | 注入与红线测试全绿 |
| M6 | 文字版统计与创新模块 | 仪表盘、挑战赛、学习路径、周报、错题变式可用 |
| M7 | 文档与提示词文件 | README 含安装/运行/打包命令（只写不执行） |

每个里程碑结束必须可运行、可测试，不允许“等全部写完再验证”。

---

## 11. 约束与风险

### 11.1 仓库内容约束

只提交：源代码、提示词文件、知识卡片、README、测试、配置、依赖说明、软件文档。不提交：学习档案、错题本、收据、复习清单、任务文件、聊天记录、音频、打包产物、Pages 配置、记忆数据。

### 11.2 风险与缓解

| 风险 | 缓解 |
|---|---|
| 120 张卡片内容量大、质量参差 | 分批提交，每批启动校验 + 抽样人工复核；卡片标注 `source` |
| 符号等价判定误判 | 子进程 + 超时；不确定即 `UNVERIFIED`，要求人工核对 |
| LLM 自由文本解析错误 | 解析结果只作为“候选答案”，代码比对；无法确认则转选择题式交互 |
| 模板模式文案生硬 | 明确标注离线模式；模板只用于演示与测试，不作为质量基准 |
| 状态机与 UI 耦合复发 | `domain/` 禁止 import UI/IO，靠测试守护 |

---

## 12. 待确认项

无。本设计中所有需要决策的点已在评审中确定：交付形态（Streamlit）、模型接入（OpenAI 兼容 + 无 Key 降级）、架构（混合）、卡片密度（课程级全覆盖）、题型（8 种全保留）。
