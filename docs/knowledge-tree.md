# 知识点细化与学习闭环

本文记录“知识点树 + 学习卡片 + 解析/错因定位 + 学习闭环”功能。范围仅限内容组织与展示层，不改判定、提示阶梯、安全、收据与复习调度逻辑。

## 数据模型

- 知识点 ID 复用现有 `card_id`，不引入第二套 ID。
- 层级固定为：学段（stage）→ 课程（course）→ 知识卡片（card）。
- 结构与题目绑定集中在 `content/knowledge_tree.yaml`：
  - 148 个节点：3 个学段、23 门课程、122 张卡片
  - 366 条题目绑定
  - 12 条先修边，复用 `content/prerequisites.yaml`，启动时不新增推断
- 绑定字段：
  - `exercise_id`
  - `knowledge_point_id`（当前等于卡片 ID）
  - `problem_schema`（`{card_id}:{exercise.kind}`，例如 `hs-function-intro-001:choice`）
- `mathcoach/domain/knowledge_tree.py` 负责加载、结构校验、父子查询、先修链 BFS 与题目反查；先修边有环或节点缺失时拒绝加载。
- 不改题目 YAML 文件，也不新增题目级元数据字段。

## 学习卡片

- 目录：`content/learning_cards/<card_id>.md`，共 122 个文件。
- 已填充 5 个：`hs-function-intro-001`、`hs-func-002`、`hs-func-003`、`hs-func-004`、`hs-func-005`。
- 其余为模板，包含“状态：待填充”和“待填充”占位。
- 已填充卡片包含：概念、直觉、常见误区、诊断例题。
- 读取入口：`load_learning_card(knowledge_point_id)`；缺失或非法 ID 返回 `None`，由页面显示占位。
- 路径做过非法字符检查，不接受 `..`、`/`、`\`。

## 知识点浏览与“先学习”

- 讲解页（EXPLAIN）提供“先学习此知识点”入口，不阻塞“开始小测”。
- 入口通过 `st.query_params["kp"] = card_id` 打开知识点浏览，避免整页刷新丢失会话。
- 浏览页：
  - 左侧按学段/课程列出卡片，可逐级展开并切换当前知识点
  - 右侧显示课程、章节、前置知识点、学习卡片
  - “开始练习此知识点”会新建该卡片的会话
  - “返回当前任务”清除 `kp` 参数并回到原会话
- 设置 → 外观新增“显示学习卡片”开关：
  - 持久化键：`learning_cards_enabled`
  - 默认开启；关闭后隐藏答题前的学习入口与浏览页卡片内容
  - 游客模式只存会话内存

## 解析展示与错因定位

- `mathcoach/domain/explanation.py` 是纯领域层，组合现有字段生成：
  - `Explanation`：知识点、课程、定义、标准答案、解题思路、常见误区、先修链
  - `ErrorLocalization`：错因、原因、建议先复习的知识点、补法
- 不调用模型，不推断新内容；先修链来自 `knowledge_tree.yaml`。
- 展示位置：
  - HINT L2/L3：显示“知识点定位”（概念回看、常见误区、先修链），不提前泄露标准答案
  - HINT L4/L5：显示“完整解析”
  - DIAGNOSE：显示“错因定位”，把已确认错因落到知识点与先修链上
  - WRAPUP：显示完整解析与学习闭环摘要
- 收据页未改动，视觉基线保持稳定。

## 学习闭环

- 知识点页与练习结束页共用同一摘要：
  - 掌握度：BKT 概率；无记录时显示“暂无记录”
  - 练习记录：收据数、错题数、待复习数
  - 状态：未开始 / 学习中 / 待复习 / 已熟练
  - 下一步建议
- 显示规则（仅展示，不参与调度）：
  - 有待复习错题 → “待复习”，优先级最高
  - 没有任何收据与错题 → “未开始”
  - 掌握度 ≥ 60% → “已熟练”
  - 其余 → “学习中”；掌握度低于 30% 且有先修点时，建议先复习最近先修点
- 学习闭环只读现有 repository 与 BKT，不新增写入、不改复习调度。

## 测试

| 文件 | 覆盖 |
|---|---|
| `tests/test_knowledge_tree_structure.py` | 规模、父子层级、先修链、非法结构拒绝 |
| `tests/test_knowledge_tree_bindings.py` | 366 题全量绑定、schema 格式、unmapped 查询 |
| `tests/test_knowledge_tree_learning_cards.py` | 122 个卡片文件、5 个已填充、非法 ID、开关持久化、答题前入口 |
| `tests/test_knowledge_tree_explanation.py` | 解析字段、先修链、错因定位、HINT/DIAGNOSE/WRAPUP |
| `tests/test_knowledge_tree_learning_loop.py` | 状态规则、练习记录、待复习、知识点页与 WRAPUP |

最终验证：

```bash
MATHCOACH_CONTENT_STRICT=1 python -m pytest -q
```

结果：`490 passed, 1 skipped`。

## 已知限制

- 仅 5 张学习卡片已填充；其余 117 张为待填充模板。
- 学习闭环状态是展示摘要，不替代错题本复习状态与 FSRS 调度。
- 学习卡片“已读”状态未单独存储；本轮不新增学习记录表。
- 知识点浏览使用 `?kp=` 查询参数；从浏览页开始练习会新建会话。
- 未新增依赖、数据库表或迁移；视觉回归基线仍只覆盖首屏、QUIZ、收据，本功能改动不进入这三张基线。

## 回退

- 功能是增量文件与展示层改动，可按批次 revert：
  - 批次 A：知识点树与绑定
  - 批次 B：学习卡片、浏览页与开关
  - 批次 C：解析与错因定位
  - 批次 D：学习闭环摘要
- 仅回退浏览入口：移除 `app.py` 的 `_render_knowledge_entry` 与 `kp` 路由即可。
- 仅回退学习卡片显示：在设置页关闭“显示学习卡片”，或移除 `learning_cards_enabled` 读取。
- 现有判定、提示阶梯、安全、收据与调度逻辑未改动。
