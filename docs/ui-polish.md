# 界面主题与交互优化

本文记录本次 UI 美化与交互性能改造。范围仅限展示层，不改判定、诊断、收据、调度与安全逻辑。

## 主题与样式

- 运行时升级为 **Streamlit 1.59.0**：`st.skeleton` 与 `st.fragment(parallel=...)` 的最低可用版本。
- 主题仍使用 `.streamlit/config.toml` 的原生 `[theme]` 键；本次未改颜色值，只补充原值注释与重启说明。
- 常量样式集中在 `mathcoach/ui/theme.py`：
  - 内容区最大宽度 `920px`
  - 卡片极淡边框与阴影（`st-key-mc-card-*`）
  - 主按钮 hover 过渡
  - `prefers-reduced-motion` 降级
  - 空 `<style>` 容器隐藏，避免布局位移
- 布局密度：宽松（默认）/ 紧凑；在“设置 → 外观”切换，保存后立即生效。
  - 持久化键：`layout_density`
  - 宽松模式不注入额外 CSS；紧凑模式减少 `stVerticalBlock` 间距
- 深色/浅色主题仍需修改 config 并重启，不提供运行时假切换。

### 主题值与原值

| 键 | 当前值 | 原值 |
|---|---|---|
| `base` | `light` | `light` |
| `primaryColor` | `#4F8BF9` | `#4F8BF9` |
| `backgroundColor` | `#FFFFFF` | `#FFFFFF` |
| `secondaryBackgroundColor` | `#F0F2F6` | `#F0F2F6` |
| `textColor` | `#262730` | `#262730` |
| `font` | `sans serif` | `sans serif` |
| `greenColor` | `#28a745` | `#28a745` |
| `redColor` | `#dc3545` | `#dc3545` |

原值同时保留在 `.streamlit/config.toml` 注释中。

## 深浅色主题切换

- 主题由 `.streamlit/config.toml` 的 `[theme] base` 决定，可选 `light` 或 `dark`。
- 切换步骤：
  1. 修改 `base = "dark"`（或改回 `"light"`）。
  2. 保存文件。
  3. 重启 Streamlit：源码运行需 `Ctrl+C` 后重新执行 `streamlit run app.py`；桌面版关闭窗口后重新打开。
- 设置页“主题”下拉只记录偏好，**不会即时改写 config**；不要把它当作运行时开关。
- 背景 CSS 通过 `st.get_option("theme.base")` 自动选择浅/深变体；动态背景与 confetti 不受影响。
- 当前视觉基线只覆盖浅色主题；切换深色后请人工检查对比度、背景图案与卡片阴影。
- 回退：把 `base` 改回 `light` 并重启。

## 按钮层级

| 角色 | 用途 | 示例 |
|---|---|---|
| primary | 主操作 | 确认目标、提交答案、保存设置 |
| secondary | 次操作 | 提示、重试、检查更新、试听 |
| danger | 不可恢复操作 | 永久清除学习数据 |

- 通过 `mathcoach/ui/components.py` 的 `button_kwargs()` 复用，不在页面散落 CSS。
- 危险按钮使用 `st-key-settings_clear_submit` 定向样式；仍需输入 `DELETE` 确认。
- `st.button` 没有原生 `loading` 参数，耗时操作不使用假 loading。

## 加载反馈

- `st.skeleton` 固定高度占位：
  - 确认目标：`SKELETON_CARD`（140px）
  - 智能复习包：`SKELETON_CARD`
  - 导出 artifact：`SKELETON_PANEL`（220px）
  - 设置页导出：`SKELETON_PANEL`
  - AI 连接测试：`SKELETON_INLINE`（56px）
- `:shimmer[]`：检查更新时的纯文本状态。
- 骨架占位实测可渲染为 `stSkeletonElement`，并保留固定高度。
- 内容出现时页面会正常增长，但不会从空白直接跳到内容；未使用像素级骨架匹配。

## form / fragment 改造

| 区域 | 原交互 | 新交互 | 说明 |
|---|---|---|---|
| 目标确认 | 输入 + 点击确认（2 步） | 输入 + 点击确认（2 步） | 改为 form；输入不再触发整页 rerun；`enter_to_submit=False` 避免 Enter 误提交 |
| 每日/挑战倒计时 | 静态文本 | 静态文本 + 每 5 秒局部刷新 | `@st.fragment(run_every=5)`；时间到提示提交后结算 |
| 导出区域 | 3 步 | 未改造 | 目录/确认语句需要先看到摘要；form 化会增加一次“生成预览”点击 |
| 设置页导出 | 直接下载（1 步） | 生成 / 刷新 + 下载（2 步） | 点击“生成 / 刷新导出数据”后才构建 4 个 payload；下载阶段不再重建 |
| 并行 fragment | — | 未启用 | 当前没有互不依赖、可并行的独立区域 |

## 延迟与缓存

| 位置 | 原时机 | 新时机 |
|---|---|---|
| 设置页审计日志 | 每次设置页渲染查询 200 条并构建 CSV/JSON | 展开“查看审计日志”后才查询；下载入口移到 expander 内 |
| 设置页导出 | 每次设置页渲染查询并构建 4 个 payload | 点击“生成 / 刷新导出数据”后构建，缓存到 session；下载不再重建 |
| 背景主题读取 | 每次 rerun 读 settings 表 | 首次读取后缓存到 `session_state`，保存时更新 |
| 庆祝/减少动效读取 | 每次 rerun 读 settings 表 | 同上 |
| 动态背景读取 | 每次渲染读 settings 表 | 同上 |
| 错题本先修诊断 | 最多 10 条错题逐条全量查询 | 一次取统计与错题列表后复用 |

- 审计日志下载从 1 次点击变为“展开 + 下载”2 次，这是本次明确的权衡。
- 设置页导出从 1 次点击变为“生成 / 刷新 + 下载”2 步；生成后的下载不会重建 payload。
- 缓存只在本会话内有效；外部修改数据库不会实时反映，重新保存或重启后更新。

## 验证

- 全量测试：`455 passed, 1 skipped`
- 新增测试：
  - `tests/test_ui_theme_config.py`
  - `tests/test_ui_theme_constants.py`
  - `tests/test_ui_theme_layout.py`
  - `tests/test_ui_theme_buttons.py`
  - `tests/test_ui_theme_interactions.py`
- 本地使用 Chrome 155 验证；最终基线使用 CI Chrome 的实际截图对齐（1440×900，阈值 0.5%），PR CI 已通过。
- 视觉基线仅覆盖首屏、QUIZ、收据，不做像素级断言。

## 回退

- 主题颜色：`.streamlit/config.toml` 注释保留了原值。
- 布局宽度/卡片/按钮 hover：移除 `app.py` 中的 `inject_theme()` 调用即可回退。
- 按钮层级：`type="primary"` 可逐处移除。
- 设置页导出：移除 `EXPORT_PAYLOAD_KEY` 的 session_state 缓存与生成按钮，恢复渲染时构建。
- 缓存：删除 `*_CACHE_KEY` 的 session_state 读写即可恢复每次读库。
- 审计延迟：恢复 `_render_audit` 的 eager 查询与 expander 外下载按钮。

## 已知限制

- 动态背景仍是组件区域装饰面板，不是浏览器全屏背景。
- `st.skeleton` 高度是近似值，不能保证与最终内容完全等高。
- 审计日志下载入口需要先展开 expander。
- 设置页导出需要先点击“生成 / 刷新导出数据”；学习数据变化后需手动刷新。
- 未引入第三方 UI 主题库，未新增前端依赖。
- Linux 桌面产物仍缺少 GTK/Qt 后端，说明见 [install.md](install.md)。

## 2026-11-28 追加：交互延迟优化

- 周报 AI 叙事改为按需生成：进入周报只渲染确定性报告，点击“生成 / 刷新 AI 叙事”才调用模型；结果按报告结论签名缓存在会话中，重复 rerun 不重复请求。
- 仪表盘与周报共用 `RepositorySnapshot`：同一轮渲染中收据、错题、复习项各取一次全量，避免同一指标重复查询 4 次。
- KC 影子掌握度改为 `load_with_samples()` 一次批量读取；会话内缓存，并在步骤提交、步骤放弃、切换记忆授权后失效。
- 小测答案区改为 `st.form`：选择选项不再立即触发整页 rerun，点击“提交答案”时统一提交。
- 分步填写改为 `st.fragment`：检查单步只重跑步骤区，不再重建可视化与小测控件；局部 rerun 不可用时回退全局 `st.rerun()`。
- 卡片级与 KC 级可视化改为 fragment：拖动滑块只重跑图表区域。
- 已知权衡：快照不跨 rerun 缓存，学习数据更新后不会展示过期统计；周报叙事缓存按结论签名失效，数据变化后需重新点击生成。

## 2026-11-28 追加：KC 动态可视化讲解

- 新增 KC 级可视化注册表：`get_kc_visual` / `render_kc_visual` / `kc_visuals_for_exercises`；未登记 KC 返回 `None`，渲染异常返回 `failed`，均不阻断学习流程。
- 首批组件：
  - `kc-hs-trig-002-p1` 象限符号判定：四象限底色、单位圆投影与 sin/cos 符号。
  - `kc-hs-trig-003-f1` 补角公式：x 与 π−x 关于 y 轴对称，正弦相同、余弦相反。
  - `kc-hs-trig-004-f1` 振幅与周期：滑块调节 A/ω，实时显示 `|A|` 与 `2π/|ω|`。
- 入口：
  - 知识点浏览页：按卡片题目映射展示“KC 动态讲解”区块。
  - 分步填写答错：在该步骤下方就地提供对应 KC 的动态讲解。
  - 错因诊断页：汇总当前题目关联的可视化 KC。
- 全部组件只读，不修改判分、BKT、FSRS、错题或 KC 影子库；渲染失败只提示“动态讲解暂不可用，已保留文字讲解”。

## 2026-11-28 追加验证

- 交互延迟优化完成后：`786 passed, 5 skipped`。
- KC 动态可视化讲解完成后：`816 passed, 5 skipped`。
- 新增测试：
  - `tests/test_ui_snapshot.py`、`tests/test_ui_latency.py`
  - `tests/test_visuals_quadrant_sign.py`、`tests/test_visuals_supplement_angle.py`、`tests/test_visuals_amplitude_period.py`
  - `tests/test_kc_visuals_ui.py`

## 2026-11-28 追加：REMSJ、草稿原位标注与情境仿真

- REMSJ 小切片：提示页显示当前阶段（复述题意/提取条件/关联概念/求解/说明理由）；步骤判定新增步骤级错因映射。
- 草稿原位标注：已判定步骤显示输入、徽标与可展开的“为什么这样判定”，不展示标准答案；错误步骤保留 KC 动态讲解。
- 情境仿真：讲解页新增切点斜率与向量合成两个参数可调情境，探索不计入掌握度。
- 分步板书：振幅周期与余弦定理题目按步骤展示图形帧；帧内数学声明先过 verify，失败回退文字。
- 语音追问：本地 Whisper 可选，未安装或识别失败回退文字。
- 验证：`900 passed, 5 skipped`。

## 2026-11-28 追加回退

- 交互延迟：删除 `RepositorySnapshot` 接入、恢复周报渲染时直接调用 `generate_report_narrative`、移除 `quiz_answer_form` 与相关 `@st.fragment` 即可回到逐次重算。
- KC 可视化：移除 `_KC_VISUALS` 中的登记项即可隐藏入口；删除对应 `mathcoach/ui/visuals/*.py` 不影响卡片级可视化。

## 2026-11-28 追加回退（第二批）

- 移除 `_render_scenario_block` 与 `content/scenario/` 即回退情境入口。
- 移除 `_render_step_result` 的“为什么这样判定”与阶段标签即回退原位标注/REMSJ。
- 移除 `mathcoach/board/` 与 `_render_board_frame` 即回退分步板书。
- 卸载 `faster-whisper` 即隐藏语音入口。
- 移除 `mathcoach/representation/` 与 `SessionView.representation` 即回退表示降级。

## 2026-11-28 追加：依赖度防护、多解检验与本地步骤洞察

- 依赖度防护：新增只读信号模块，按卡片汇总历史收据、追问事件与步骤运行；最近五条收据中三条 L4/L5、包含 L5 且掌握度不低于 0.4 时，把主动请求提示暂时限制到 L2。连续两次答错、独立答对、换题或手动点击“恢复完整提示”即解除；不修改 BKT 公式、收据独立程度与 FSRS。
- 独立验证邀请：依赖度较高时，收据页提供一道无提示同类题；结果只在本页展示，不写收据、BKT 或错题本，可随时跳过。
- 多解策略检验：新增 `content/paths/*.yaml`，静态登记备选解法的关键检查点；加载期用 verify 预检，收据后先验证检查点，通过后才显示路径名称与总结。没有登记路径的题目不显示入口。
- 本地步骤洞察：只读本机 `step-signals.sqlite3`，聚合最近三次运行中反复出错的步骤，在分步填写区展示“近期卡点”，并提供到该步的追问锚点；不做跨用户同伴聚合。
- 隐私边界：所有洞察均为本机数据；依赖度信号在游客模式或读取失败时为空，不新增任何上传。
- 验证：`942 passed, 5 skipped`。新增测试：
  - `tests/test_dependence.py`、`tests/test_engine_hint_ceiling.py`、`tests/test_dependence_ui.py`
  - `tests/test_paths_catalog.py`、`tests/test_paths_checker.py`、`tests/test_paths_ui.py`
  - `tests/test_insights.py`、`tests/test_insights_ui.py`
- 回退：移除 `SessionEngine` 的 `hint_ceiling` 参数与 `_render_hint_ceiling_banner` / `_render_independent_check` 即回退依赖度防护；移除 `mathcoach/paths/`、`content/paths/` 与 `_render_strategy_probe` 即回退多解检验；移除 `mathcoach/insights/` 与 `_render_step_insight` 即回退步骤洞察。
