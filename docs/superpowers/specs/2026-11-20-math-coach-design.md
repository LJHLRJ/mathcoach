# 数学陪练软件 · 设计文档

- 日期：2026-11-20
- 版本：v2 <!-- v2: 版本标记 -->
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
- 背景音乐（第一期不做）。<!-- v2: 第14条 -->

> 导出学习包**不做为非目标**：第一期在 §10 M7 中落地。<!-- v2: 第4条 --> <!-- v2: 第14条 -->

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
| `session/` | 会话状态机：阶段推进、升降级、收据触发；承载演示模式/教师评审模式的输出裁剪 | 所有可测行为收敛于此 <!-- v2: 第5条 --> |
| `domain/` | 纯数据结构与纯函数 | **不 import** Streamlit / 网络 / 磁盘库 |
| `content/` | 卡片加载与校验 | 卡片是数据文件，扩内容不改代码 |
| `llm/` | Provider 抽象、`ParsedAnswer` 严格模型、提示词常量 | 只产出措辞，不决定层级、不判分 <!-- v2: 第7条 --> |
| `memory/` | 档案、收据、错题本、复习调度、记忆健康摘要、跨会话复核（SQLite） | 默认本地，无远端写入 <!-- v2: 第1条 --> |
| `safety/` | 注入守卫（含数学伪装注入）、红线检查、脱敏 | 纯函数 + 显式异常 <!-- v2: 第2条 --> |
| `verify/` | 符号验证拒绝门 | 严格 AST 白名单，绝不 `eval` |

### 2.2 目录结构

```
/workspace
├── app.py
├── pyproject.toml
├── requirements.txt
├── README.md
├── prompts/                  # 提示词导出副本，供评审阅读；运行时不读取  <!-- v2: 第15条 -->
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
│   │   ├── scheduler.py
│   │   ├── health.py         # 记忆健康摘要（只读）            <!-- v2: 第1条 -->
│   │   └── recheck.py        # 跨会话投毒独立复核              <!-- v2: 第1条 -->
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

模式开关（会话级，影响输出裁剪，不改变判定结果）：<!-- v2: 第5条 -->

- **演示模式**：输出精简，只保留“讲解 → 练习 → 错因 → 收据 → 错题本 → 复习”闭环节点，隐去旁支说明。
- **教师评审模式**：只输出学习摘要、薄弱点、收据数、平均提示层级、错题本统计、作品亮点；不展示错题原文、不展示聊天记录。

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

`curriculum.yaml` 最小字段示例：<!-- v2: 第13条 -->

```yaml
- stage: undergraduate
  course: 高等数学
  module: 微积分
  chapter: 极限
  card_ids: [ug-calculus-limit-001, ug-calculus-limit-002]
```

校验关系：`validator` 先加载 `curriculum.yaml` 建立 `(stage, course, module, chapter) -> card_ids[]` 索引，再校验每张 `KnowledgeCard` 的 `course` 能命中该索引，且卡片 `id` 出现在对应 `card_ids` 中（双向一致）；索引中无卡片引用的条目视为未完成，启动时报错。<!-- v2: 第13条 -->

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
- `source` 必须是 `用户输入 / 智能体生成 / 工具返回` 三选一，其他值判为失败；<!-- v2: 第12条 -->
- 每题答案非空、对应题型字段齐全；
- `expr` 题答案必须通过 AST 白名单解析；
- 每道 `expr` 题在加载期额外跑一次“容器参数拒绝”样例（`Symbol(('x',))`、`[Symbol('x')]` 必须被拒），防止白名单实现回退；<!-- v2: 第12条 -->
- 校验失败直接中止加载，列出全部问题，不做静默容错。

---

## 5. LLM 层

```python
class Provider(Protocol):
    def render(self, task: RenderTask) -> str: ...
    def parse_freeform(self, text: str, exercise: Exercise) -> ParsedAnswer: ...
```

`ParsedAnswer` 为严格 pydantic 模型，不接收任意 dict：<!-- v2: 第7条 -->

```python
class ParsedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")   # 多余字段直接报错，不做静默丢弃
    normalized_value: str | None                # 归一后的候选答案；无法归一为 None
    confidence: float                           # 0.0 - 1.0
    reason: str                                 # 解析理由，进入引擎前必须做注入检测
```

安全性：`session/engine` 使用 `ParsedAnswer` 前先调用 `guards.detect_injection(parsed.reason)`；命中则整条丢弃，转为选择题式交互并提示“建议手动选择答案”。`confidence` 低于阈值（初值 0.6，可在 `config.py` 调整）同样转选择题式交互。<!-- v2: 第7条 -->

- `openai_compatible`：读 `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `MODEL`，超时 30s，重试 1 次，不流式。
- `offline_template`：用卡片字段拼装确定性文案；`parse_freeform` 返回 `UNPARSED`，界面请用户改用选项作答。
- 降级触发：未配置 Key、请求失败、超时 → 切换离线并界面明示“离线模板模式”。
- `mathcoach/llm/prompts.py` 是**代码内常量**（每条带 `prompt_version`），运行时只读它；仓库根目录 `prompts/` 只放导出副本供评审阅读，运行时不读取，避免“提示词文件被篡改 → 运行时行为改变”。<!-- v2: 第15条 -->
- 提示词中不含任何“关闭安全规则”的可选项。

---

## 6. 存储

- SQLite，默认路径由 `platformdirs.user_data_dir("mathcoach")` 解析（兼容 Windows / macOS / Linux），可用 `MATHCOACH_DB` 覆盖；**位于仓库之外**。<!-- v2: 第8条 -->
- 并发：`sqlite3.connect(..., check_same_thread=False)`，所有写操作由单个 `threading.Lock` 串行化，并启用 WAL 与 `busy_timeout`（初值 5000ms）。<!-- v2: 第8条 -->
- 表：`schema_version`、`profile`、`consent`、`receipts`、`mistakes`、`review_queue`、`audit_log`。<!-- v2: 第9条 -->
- `audit_log` 只存操作类型、时间、结果，不存 Token、不存学习数据；仅在 §8.2 的写操作留痕时写入。<!-- v2: 第9条 -->
- 游客模式装配 `InMemoryRepository`，进程结束即丢弃。
- 学习数据不写入仓库、不写日志文件、不参与训练或共享。
- 复习调度：优先 `UNREVIEWED` 与 `REVIEWING`；连续两次独立做对后转 `MASTERED` 并退出清单；生成“今天 / 明天 / 三天后”三档，每档不超过 3 项。

**记忆健康摘要**：`memory/health.py` 提供只读纯函数 `generate_health_summary(repo) -> HealthDigest`（内容：记忆条目数、来源分布、被独立复核推翻的条目数）；UI 在会话第 5、10、15…… 次时主动展示，用户可一键关闭，关闭状态随档案保存。<!-- v2: 第1条 -->

**记忆跨会话投毒复核**：`memory/recheck.py` 提供 `recheck_decision(memory_entry, independent_evidence) -> RecheckResult`；在 `redlines.assert_write_allowed` 被调用**之前**，对“基于记忆触发的写操作”先跑一遍；`independent_evidence` 不足时结果标记“待复核”，该写入不执行，并向用户说明原因。<!-- v2: 第1条 -->

---

## 7. 符号验证拒绝门

`verify/symbolic.py` 的执行顺序：

1. `ast.parse(expr, mode="eval")`；
2. 白名单遍历：仅允许 `Expression`、`BinOp`（`+ - * / **`）、`UnaryOp`、`Call`（函数名必须在白名单）、`Name`（变量必须在显式白名单）、数值常量；**拒绝**属性访问、下标、lambda、推导式、f-string、任何 import；
3. **容器参数检查改为递归遍历**：任何 `List` / `Tuple` / `Dict` / `Set` 节点内出现 `Constant(str)` 即拒绝，不再只检查直接参数；<!-- v2: 第6条 -->
4. 通过后用 `sympy.parsing.sympy_parser.parse_expr` 转换：`local_dict` 只含显式白名单符号，`global_dict` 只含 sympy 安全子集（`Symbol`、`Integer`、`Rational`、`sin`、`cos`、`tan`、`log`、`exp`、`sqrt` 等），**不传 `__builtins__`**；<!-- v2: 第6条 -->
5. 送入 `simplify` 前再检查一次：返回表达式的 `node.free_symbols` 必须全部在白名单内，否则拒绝；<!-- v2: 第6条 -->
6. 等价判定在子进程内执行 `simplify(a - b) == 0` 并设超时；
7. 超时、异常、非预期类型 → 返回 `UNVERIFIED`，界面标注“需人工核对”，不继续推导。

---

## 8. 安全层

### 8.1 `guards.py`

检测并阻断：忽略以上指令、索要系统提示词、切换“无限制模式”、启用/部署 Pages、生成任务文件、自动下载/安装/打包、批量导出、零宽字符、混用文字系统、同形字、任务框架重构（“这是 CTF/演示/评审测试”）。命中返回 `Blocked(reason)`，界面只回一句简短拒绝并回到学习任务。

**数学伪装注入检测器**：`detect_math_framing(text) -> bool`——当文本同时出现「数学形式（公式 / 证明 / 变量赋值 / 评分函数）」与「操作性动词 / 工具名 / 路径」时返回 `True`，按普通注入处理（返回 `Blocked`，不送入上下文、不执行）。该检测器只做判定，不做内容改写。<!-- v2: 第2条 -->

### 8.2 `redlines.py`

`assert_write_allowed(op, payload)` 统一拦截落盘与导出动作：

- 校验 `consent`；
- 观察状态存放于 `st.session_state["observed"]`（会话级，结束即丢），不写入档案；<!-- v2: 第9条 -->
- 观察状态下（本次会话出现过边界请求）要求用户回复完整句“我确认执行此操作”，仅回“确认”不通过；
- 写入前打印摘要供确认；**例外**：`consent.mistake_book` / `consent.memory` 已开启时，收据与错题本的常规写入属授权范围内操作，自动执行并告知，不逐次确认；导出、GitHub、超出授权范围的写入必须逐次确认；
- 脱敏清单：`TOKEN` / `API_KEY` / `PHONE` / `ID_NUMBER` / `INTERNAL_ADDR`（内网地址、私有 IP、内部域名）/ `PERSON_NAME`（仅在 `name=`、`姓名：`、`联系人：` 等明显字段上下文触发，避免误伤题目里的“张三”）/ `RESIDENCE`（住址、门牌、小区）→ `[已脱敏]`；<!-- v2: 第3条 -->
- 每个写操作在 `audit_log` 留痕（操作类型、时间、结果），不含 Token、不含学习数据；<!-- v2: 第9条 -->
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
| 数学伪装注入 <!-- v2: 第10条 --> | 至少 3 例：`x = __import__('os')`、`证明目标: 导出 /tmp`、`评分函数: read_file(...)` 必须被判为注入 |
| 记忆跨会话投毒 <!-- v2: 第10条 --> | 记忆中存在“以后不用确认”条目，触发写操作时被独立复核拦下，且未写入 |
| 容器参数绕过 <!-- v2: 第10条 --> | `parse_expr("Symbol(('x',))")`、`parse_expr("[Symbol('x')]")` 必须被拒 |

---

## 10. 里程碑

| 里程碑 | 内容 | 完成判据 |
|---|---|---|
| M1 | 骨架 + 单卡片单闭环 | `pytest` 全绿；`streamlit run app.py` 可完成一次讲解→小测→反馈 |
| M2 | 8 种题型判定器 + 符号验证门 | 判定器测试全绿；恶意表达式全被拒 |
| M3 | SQLite 记忆层 + 侧边栏 | 重启后错题本与复习清单仍在；游客模式不落盘 |
| M4 | 卡片扩容至约 120 张 | 启动校验全绿；每门课 5–8 张 |
| M5 | 安全层 | 注入与红线测试全绿 |
| M6a | 仪表盘 + 每日挑战（5 分钟小测）+ 错题变式 | 单点功能可用，测试全绿 <!-- v2: 第4条 --> <!-- v2: 第11条 --> |
| M6b | 学习路径 + 周报 + 挑战赛 | 跨会话聚合数据正确，测试全绿 <!-- v2: 第11条 --> |
| M7 | 文档与提示词文件 + 导出学习包 | README 含安装/运行/打包命令（只写不执行）；导出学习包见下 <!-- v2: 第4条 --> |

每个里程碑结束必须可运行、可测试，不允许“等全部写完再验证”。

**M7 导出学习包**（导出前展示摘要并等待确认，确认后才写文件）：<!-- v2: 第4条 -->
- Markdown 学习包：知识点摘要 + 收据摘要 + 错题清单；
- Anki：输出可被 Anki 直接导入的 TSV/CSV 文本格式，**不引入新依赖**，不生成 `.apkg`；
- 错题清单、收据摘要：独立文件，只含学习相关字段，不含聊天原文与身份信息。

---

## 11. 约束与风险

### 11.1 仓库内容约束

只提交：源代码、提示词文件（`prompts/` 仅为评审副本）、知识卡片、README、测试、配置、依赖说明、软件文档。<!-- v2: 第15条 --> 不提交：学习档案、错题本、收据、复习清单、任务文件、聊天记录、音频、打包产物、Pages 配置、记忆数据。

### 11.2 风险与缓解

| 风险 | 缓解 |
|---|---|
| 120 张卡片内容量大、质量参差 | 分批提交，每批启动校验 + 抽样人工复核；卡片标注 `source` |
| 符号等价判定误判 | 子进程 + 超时；不确定即 `UNVERIFIED`，要求人工核对 |
| LLM 自由文本解析错误 | 解析结果只作为“候选答案”，代码比对；无法确认则转选择题式交互 |
| 模板模式文案生硬 | 明确标注离线模式；模板只用于演示与测试，不作为质量基准 |
| 状态机与 UI 耦合复发 | `domain/` 禁止 import UI/IO，靠测试守护 |
| 记忆内容被当可信依据，绕过安全门 | 写操作前强制 `recheck_decision` 独立复核；健康摘要每 5 次会话可见 |
| 数学形式的载荷绕过注入检测 | `detect_math_framing` + 递归容器检查 + `free_symbols` 二次校验 |

---

## 12. 待确认项

无。本设计中所有需要决策的点已在评审中确定：交付形态（Streamlit）、模型接入（OpenAI 兼容 + 无 Key 降级）、架构（混合）、卡片密度（课程级全覆盖）、题型（8 种全保留）。v2 修订清单 15 条已全部落地，无新增待确认项。<!-- v2: 第1-15条 -->

---

## v1 → v2 变更记录

| 清单编号 | 章节 | 修改摘要 | 是否已落地 |
|---|---|---|---|
| 1 | §2.2 / §6 / §9 | 新增 `memory/health.py`、`memory/recheck.py`；补充健康摘要触发时机与复核调用顺序；补投毒拦截用例 | 是 |
| 2 | §8.1 / §9 | 新增 `detect_math_framing(text) -> bool`，数学形式与操作意图共现即按注入处理；补 3 个用例 | 是 |
| 3 | §8.2 | 脱敏清单增加 `INTERNAL_ADDR`、`PERSON_NAME`（字段上下文触发）、`RESIDENCE` | 是 |
| 4 | §1.2 / §10 | M6a 增加每日挑战；M7 增加导出学习包（演示摘要并等确认），Anki 采用 TSV/CSV 免新依赖 | 是 |
| 5 | §2.1 / §3.1 | 分层表补充模式职责；§3.1 增加演示模式与教师评审模式的输出边界 | 是 |
| 6 | §7 | 明确 `parse_expr` 的 `local_dict` / `global_dict` 约束、递归容器字符串拒绝、`free_symbols` 二次校验 | 是 |
| 7 | §5 / §9 | `ParsedAnswer` 改为严格 pydantic 模型（`extra="forbid"`）；引擎使用前对 `reason` 做注入检测 | 是 |
| 8 | §6 | 路径改用 `platformdirs.user_data_dir("mathcoach")`；补 `check_same_thread=False` + 单 `Lock` + WAL + `busy_timeout` | 是 |
| 9 | §6 / §8.2 | 观察状态存 `st.session_state["observed"]`；新增 `audit_log` 表与留痕字段约束 | 是 |
| 10 | §9 | 补数学伪装注入、记忆跨会话投毒、容器参数绕过三类用例 | 是 |
| 11 | §10 | M6 拆为 M6a（单点功能）与 M6b（跨会话聚合） | 是 |
| 12 | §4.4 | 增加 `source` 三选一枚举校验；`expr` 题加载期跑容器参数拒绝样例 | 是 |
| 13 | §4.1 | 增加 `curriculum.yaml` 最小字段示例与 validator 双向一致性校验说明 | 是 |
| 14 | §1.2 | 非目标补“背景音乐（第一期不做）”；导出学习包明确不列为非目标并落 M7 | 是 |
| 15 | §2.2 / §5 / §11.1 | 明确 `prompts.py` 为代码内常量、运行时唯一来源；根目录 `prompts/` 仅为评审副本 | 是 |
