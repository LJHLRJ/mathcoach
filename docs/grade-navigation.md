# 年级/难度标注与按年级入口

本文记录“年级/难度标注与分页入口”功能。范围仅限内容元数据与展示层，不改判定、提示、安全、收据与复习调度逻辑。

## 元数据

- 题目级字段：
  - `grade`：`g1..g12`、`u1..u4`、`m1..m3`、`mixed`；无法确认时允许 `unclassified`。
  - `difficulty`：`basic`、`intermediate`、`advanced`、`challenge`；无法确认时允许 `unclassified`。
- 年级与难度是两个独立字段，不合并。
- 题目自身 `grade` 优先于知识点树推断。
- 现有卡片级 `difficulty`（基础/进阶/挑战）保留不变，题目级 `difficulty` 为新增字段。
- 本轮按用户确认的课程级映射：
  - 题目级 `difficulty` 继承卡片级难度：基础→`basic`、进阶→`intermediate`、挑战→`challenge`。
  - 同一门课程下的卡片使用同一 `grade`；不在课程内再细分子章节。
- 课程→年级映射：

| 学段 | 年级 | 课程 |
|---|---|---|
| 高中 | g10 | 集合与逻辑、函数与导数、不等式、平面向量 |
| 高中 | g11 | 三角函数、数列、立体几何、解析几何 |
| 高中 | g12 | 概率统计、复数、计数原理 |
| 本科 | u1 | 高等数学、线性代数 |
| 本科 | u2 | 概率论与数理统计、常微分方程 |
| 本科 | u3 | 复变函数 |
| 本科 | u4 | 数值分析基础 |
| 研究生 | m1 | 矩阵论、泛函分析 |
| 研究生 | m2 | 数值分析进阶、数理方程 |
| 研究生 | m3 | 随机过程、最优化方法 |

- g1–g9 没有对应内容，页面保持空状态，不编造题目。
- `knowledge_tree.yaml` 的 148 个节点均添加 `grade_span`：
  - 卡片节点：对应课程年级
  - 课程节点：该课程年级
  - 学段节点：`[g10,g11,g12]`、`[u1,u2,u3,u4]`、`[m1,m2,m3]`

分布：

| 维度 | 分布 |
|---|---|
| grade（题数） | g10 63、g11 60、g12 45、u1 30、u2 30、u3 15、u4 15、m1 36、m2 36、m3 36 |
| grade（卡片数） | g10 21、g11 20、g12 15、u1 10、u2 10、u3 5、u4 5、m1 12、m2 12、m3 12 |
| difficulty | `basic` 138、`intermediate` 141、`advanced` 0、`challenge` 87 |
| mixed / unclassified | 0 / 0 |

学段分布：高中 56 张 / 168 题，本科 30 张 / 90 题，研究生 36 张 / 108 题。

## 查询索引

`mathcoach/domain/grade_index.py` 提供只读索引：

- `GradeRecord`：`exercise_id`、`card_id`、`grade`、`difficulty`
- `GradeIndex.by_grade()`、`by_difficulty()`、`filter()`、`card_ids()`、`grade_counts()`、`difficulty_counts()`
- `load_grade_index()`：读取三个学段目录下的卡片 YAML
- `load_grade_spans()`：读取知识点树节点的 `grade_span`
- `node_ids_for_grade()`：按年级查询知识点节点

缺失或非法元数据统一回退为 `unclassified`；重复题目 ID 会拒绝加载。

## 页面方案

采用 **方案 A（筛选式切换）**，未使用 `st.navigation`：

- 现有应用是单页 + 侧边栏功能 selectbox + 4 个 `st.tabs`。
- 现有测试有 16 个文件、27 处依赖 `selectbox[1]` / `main_tabs` / `at.tabs`；改为 `st.navigation` 需要重构 app.py 并修改现有测试与视觉基线，超出本轮授权。
- 因此在现有侧边栏“功能”中新增“按年级”，页面内部使用：
  - 年级 selectbox
  - 难度 selectbox
  - `@st.fragment` 隔离筛选刷新
  - 难度 expander 分组，按 `basic → challenge` 展示卡片数与卡片列表

深链接：

- 支持 `?grade=<grade>` 打开对应年级筛选。
- 当前不把用户后续选择同步回 URL；URL 主要用于入口分享。
- `?kp=<card_id>` 仍优先于 `?grade=`，用于打开学习卡片。

## 入口与学习数据

- “先学习本年级知识点”入口按 `grade_span` 过滤知识点卡片，复用现有知识点浏览页。
- 今日复习使用 `repository.list_review_items()` 全局聚合，跨年级显示。
- 收据、错题本、复习队列全局共享，不按年级/难度隔离；只有会话上下文按年级筛选。
- 设置 → 学习入口新增“默认进入年级”：
  - 持久化键：`default_grade`
  - 优先级：URL `grade` > 上次选择 > 默认进入年级 > 全部年级
- 游客模式默认年级只存会话内存。

## 测试

| 文件 | 覆盖 |
|---|---|
| `tests/test_grade_difficulty_metadata.py` | 枚举、366 题全量元数据、查询过滤、unclassified、grade_span、原有字段保留 |
| `tests/test_grade_difficulty_routing.py` | 按年级页渲染、筛选、难度分组、学习卡片入口、跨年级复习、默认年级、设置页控件 |

最终验证：

```bash
MATHCOACH_CONTENT_STRICT=1 python -m pytest -q
```

结果：`506 passed, 1 skipped`。

## 已知限制

- g1–g9 没有对应内容，页面保持空状态；年级映射为课程级，同一课程内不细分子章节。
- 题目级难度继承卡片级难度，同一卡片内题目难度相同；后续可逐题标注 `advanced` 等更细级别。
- 未使用 `st.navigation` 独立页面；当前为筛选式切换，文档已说明。
- `?grade=` 为单向深链接，用户选择不会持续同步到 URL。
- 未新增依赖、数据库表或迁移；未改判定、提示、安全与调度逻辑。

## 回退

- 内容：移除题目级 `grade`/`difficulty` 与节点 `grade_span` 即可。
- 页面：移除 `app.py` 的 `MODE_GRADE` 与 `?grade=` 路由，或移除 `ui/grade_page.py`。
- 设置：移除“学习入口”表单与 `default_grade` 键。
- 索引：移除 `domain/grade_index.py` 与对应测试。
