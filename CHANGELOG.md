# Changelog

## [Unreleased]

## [0.8.0] - 2026-11-27

### 新增

- 诊断页提供三个下一步动作：去复习先修卡、看学习卡片，以及按同卡其他题生成的「练同类题」小复习包。
- 收据页新增 L6 费曼复述入口，按标准思路的关键片段覆盖率记录 `restatement_quality`（完整 / 部分 / 待补充）；复述不改变判分与独立程度，待补充时回流复习状态。
- 仪表盘“下一步推荐”接入 BKT 掌握度：先修满足的卡片按掌握度从低到高排序，错题卡仍优先，依据中显示 BKT 掌握度。
- 仪表盘“下一步推荐”增加“推荐开始”按钮，一键切换到推荐第一张卡片并回到陪练页。
- 掌握度更新写入历史快照，周报新增“掌握度变化”，对比本周基准与最新值并展示变化最大的卡片。
- L6 复述结果回流：待补充的复述在本题已有错题记录时补记一次半独立复习，连续独立次数清零，掌握概率不变。

### 修复

- 提示后答对被 FSRS 记为 `AGAIN` 并重置稳定性：现在按最高提示层级映射为 `HINTED`，不再当作遗忘；SM-2 模式下同样按提示档位计算间隔。
- 复习登记与诊断确认重复推进 BKT 掌握概率：`record_review` 不再更新掌握度，诊断确认只改错因，收据与显式复习各推进一次。
- 提示后答对在 BKT 中与独立答对同等计权，掌握概率虚高：现在只按一半学习增益更新，独立答对与答错保持标准 BKT。
- “今天到期 / 今日待复习”把尚未到期的题目计入：统计现在截止到本地当天结束。
- 三维可视化把竖直平面画在 z=0：现在按平面法向选择 x/z 或 y/z 网格。
- Windows 上 Streamlit 会把 `app.py` 装入 `sys.modules["__main__"]`，符号验证的 spawn 子进程因此重跑整页，`expr` 题始终被判为“无法自动核对”；子进程启动时临时隐藏主脚本路径，只执行验证 worker。
- 0.7.2 将 Windows 符号验证超时放宽到 20 秒只改变了等待时间，未修复上述根因；本次一并更正。

### 验证

- `MATHCOACH_CONTENT_STRICT=1 python -m pytest -q`：553 passed，5 skipped。
- AppTest 端到端覆盖：讲解 → 小测 → 收据 → L6 复述 → 结算 → 仪表盘 → 周报 → 重启持久化。
- 本地启动 Streamlit 首页返回 HTTP 200，启动日志无异常。

## [0.7.2] - 2026-11-24

### 新增

- 以 Apache License 2.0 发布，新增 `LICENSE`、`NOTICE` 与包元数据（license、readme、authors、classifiers、project.urls）。
- 新增 `CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`、Issue 表单与 PR 模板。
- README 新增界面截图与架构数据流图；补充贡献与许可证入口。
- 新增独立单元测试 CI（PR/push，Ubuntu 3.11/3.12 + Windows 3.12）。

### 修复

- `pip install .` 缺少 `plotly` 依赖，导致可视化页在包安装模式下 ImportError。
- Windows 上 Streamlit 已加载时，符号验证子进程冷启动约 8 秒，超过 5 秒超时，导致 `expr` 题被判为“无法自动核对”；Windows 超时上限调整为 20 秒。
- README 与 `docs/install.md` 的版本号、资产文件名已与当前版本对齐；`docs/install.md` 关于仓库无 CHANGELOG 的过时说明已更正。

## [0.7.1] - 2026-11-22

### 修复

- 本地 `secrets.local` 损坏或包含非 UTF-8 内容时，不再导致启动或设置页崩溃，按未配置密钥处理。
- 课程/卡片/先修/叙事 YAML 读取或解析失败时，统一转为可读的 `ContentError`，启动页显示错误而不是原始 traceback。
- 知识点树、年级索引与学习卡片遇到非 UTF-8 文件时安全降级，不再让知识点页或年级页崩溃。
- 导出目录不可写时，导出页显示失败原因，不再抛出未捕获异常。
- AI 配置保存到不可写位置时显示错误，不再中断设置页。
- 修正嵌入 shader 的第三方归属说明，明确代码以内联常量分发。

### 打包

- `pip install .` 生成的 wheel 现在包含 `content/learning_cards/*.md`（122 个学习卡片）和 `static/overlay/`（庆祝动效资源）。
- 新增打包配置回归测试，避免学习卡片或 static 资源再次从 wheel 中遗漏。

### 验证

- `MATHCOACH_CONTENT_STRICT=1 python -m pytest -q`：507 passed，1 skipped。
- Streamlit 冒烟覆盖 10 个功能模式、g1 空状态、g10 有内容与 390px 移动宽度；无页面错误或控制台错误。
- Linux PyInstaller 构建成功，产物约 600 MB；打包产物以 `--streamlit-server` 启动后健康检查通过，首页返回 HTTP 200。
- Linux 原生窗口、Windows/macOS 安装包与 Chrome 视觉基线未在当前环境验证。

### 已知限制

- 视觉回归基线依赖 Chrome，本地无 Chrome 时跳过；CI 仍使用 Chrome 执行。
- Windows/macOS 安装、卸载与签名流程需在对应系统验证。
- Linux 原生窗口需要 GTK/Qt 后端，当前构建只验证了本地服务启动。
- 依赖未提供锁文件；`openai` 使用 `>=1.30` 的下界，升级大版本前需重新跑连接测试。
- API Key 通过进程级环境变量接入，当前按本地单用户应用设计，不建议直接作为多用户 Web 服务部署。

## [0.7.0] - 2026-11-21

- 增加按年级/难度浏览与课程级年级映射。
- 增加知识点树、学习卡片、解析与错因定位、学习闭环状态。
- 增加桌面安装包、更新检查与安装文档。
