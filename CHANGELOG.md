# Changelog

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
