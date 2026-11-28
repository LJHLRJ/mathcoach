# MathCoach 安装指南

本文覆盖从 GitHub Releases 下载桌面版后的安装、首次启动、未签名放行与 SHA256 校验。当前发布版本为 **v0.9.0**（2026-11-28）。

> v0.9.0 资产由 Release 工作流构建后上传；下表先列文件名，大小与 SHA256 待产物发布后补充。

下载入口：

- 最新稳定版：<https://github.com/LJHLRJ/mathcoach/releases/latest>
- 全部版本与 Release Notes：<https://github.com/LJHLRJ/mathcoach/releases>

当前仅提供稳定版，没有预览通道。

## 支持平台

| 平台 | 发布资产 | 安装方式 |
|---|---|---|
| Windows x64 | `MathCoachSetup-0.9.0.exe` | Inno Setup 安装器，按用户安装 |
| Windows x64 | `MathCoach-windows.zip` | 便携版，解压后运行 |
| macOS | `MathCoach-0.9.0.dmg` | 打开后将应用拖到“应用程序” |
| macOS | `MathCoach-macos.zip` | 便携版，解压后打开 |
| Linux | 无桌面安装包 | 从源码运行，见文末 |

macOS 产物未签名、未公证；Release 未分别说明 Intel / Apple Silicon 架构，构建架构以 GitHub Actions Runner 为准（待确认）。

## Windows 安装器

1. 下载 `MathCoachSetup-0.9.0.exe`。
2. 双击运行。安装器页面标题和按钮为英文；首屏为中文“安装前说明”页，包含未签名、数据边界与安装选项说明。安装按当前用户进行，不需要管理员权限。
3. 选择安装目录。默认路径为 `%LOCALAPPDATA%\Programs\MathCoach`，支持自定义路径。
4. 选择附加任务：桌面快捷方式默认勾选；开机自启默认不勾选，勾选后可在“Windows 设置 → 应用 → 启动”中关闭。开始菜单快捷方式始终创建。
5. 点击安装。完成后，结束页默认勾选 “Launch MathCoach”，取消勾选则不会自动启动。
6. 卸载入口位于 Windows 设置的“应用”列表中的 MathCoach。

安装器会请求关闭正在运行的 MathCoach；安装完成后不会自动重启旧进程。使用静默安装时不会自动启动应用。

若启动后没有出现窗口，请尝试安装 Microsoft Edge WebView2 Runtime 后重新启动；Release 说明记录了该排查项。

### 安装向导页面

当前 Windows 安装器使用 Inno Setup 6，页面标题和按钮为英文，首屏说明页为中文。按当前配置，页面顺序为：

1. Information（中文安装前说明）
2. Select Destination Location
3. Select Additional Tasks
4. Ready to Install
5. Installing
6. Completing

- 不显示 Welcome 和 Start Menu Folder 页面。
- 除标准 Information 说明页外，没有许可协议页、自定义页面、自定义向导图片或安装器图标。
- Select Additional Tasks 页包含桌面快捷方式与开机自启：桌面快捷方式默认勾选；开机自启默认不勾选。
- 完成页的 Launch MathCoach 默认勾选；静默安装不自动启动。

### 数据边界

学习数据仅保存在本机 SQLite 数据库，不会上传到任何服务器。安装器只释放程序文件，不包含学习数据、数据库或 AI 密钥；安装阶段不会请求 AI 密钥。AI 配置可在应用内完全跳过。

### 当前限制

- 没有分组件进度状态，只显示 Inno Setup 默认进度条。
- 安装器不创建数据库结构；数据库与表结构在首次启动时自动创建。
- 未签名构建无法消除 Windows SmartScreen 提示。
- 安装器不提供自定义图标；向导按钮和页面标题为英文，只有首屏说明页为中文。
- 开机自启没有应用内开关；勾选后可通过“Windows 设置 → 应用 → 启动”关闭，卸载时会自动移除。
- 安装期间取消会由 Inno Setup 回滚已写入的更改，取消提示会明确说明回滚；安装进入最后阶段后不再允许取消。

### 安装向导能力判定（最终）

本表仅针对 Windows 安装向导；macOS DMG 没有安装向导，不适用以下页面项。

| 项目 | 状态 | 说明 |
|---|---|---|
| 安装前未签名与数据说明页 | 已实现 | 首屏 Information 页为中文安装前说明；向导按钮与页面标题仍为英文 |
| 安装完成后立即启动默认勾选 | 已实现 | 完成页 Launch MathCoach 默认勾选；静默安装不自动启动 |
| 开机自启默认关闭 | 已实现 | `autostart` 任务默认不勾选；写入 HKCU Run，卸载时移除；无应用内开关，可在 Windows 设置中关闭 |
| 桌面快捷方式默认勾选 | 已实现 | 位于 Select Additional Tasks 页；开始菜单快捷方式始终创建 |
| 分组件进度状态 | 未实现 | 保留 Inno 默认进度条；数据库在首次启动创建，不是安装步骤 |
| 取消安装回滚提示 | 已实现 | Inno 原生回滚；`ExitSetupMessage` 明确提示已写入更改会回滚 |
| 磁盘空间与权限预检 | 部分实现 | 使用 Inno 内置磁盘空间检查；没有自定义权限可写性预检 |
| 首次启动默认游客模式 | 部分实现 | 无登录、无强制 AI、无阻塞欢迎页；默认持久化，游客模式需手动关闭两个记忆开关 |
| AI 配置可完全跳过 | 已实现 | 未配置 Key 时使用离线模板，判分逻辑不变 |

## Windows 便携版

1. 下载 `MathCoach-windows.zip`。
2. 解压到任意目录。
3. 运行解压目录中的 `MathCoach.exe`。

便携版不写入开始菜单，不注册卸载项；学习数据仍保存在用户数据目录，而不是解压目录。

## macOS 安装镜像

1. 下载 `MathCoach-0.9.0.dmg`。
2. 双击打开磁盘映像。窗口内包含 `MathCoach.app` 和 `Applications` 快捷方式（即“应用程序”）。
3. 将 `MathCoach.app` 拖到“应用程序”。
4. 推出磁盘映像，然后从“应用程序”启动 MathCoach。

DMG 不包含安装向导，也没有自定义安装路径步骤；拖拽复制即完成安装。应用不会自动启动，也不会创建登录项。

## macOS 便携版

1. 下载 `MathCoach-macos.zip`。
2. 解压后得到 `MathCoach.app`。
3. 将应用移动到任意目录并打开。

便携版同样未签名，首次启动仍需按下一节放行。

## 未签名应用的首次启动

当前 Windows 与 macOS 产物均未签名。未签名不影响应用功能，但系统会给出安全提示。请只从上面的 GitHub Releases 页面下载，并先按 SHA256 校验文件。

### Windows：SmartScreen

出现“Windows 已保护你的电脑”时：

1. 确认文件来自本仓库 Release 且 SHA256 校验一致。
2. 点击“更多信息”。
3. 点击“仍要运行”。

### macOS：无法验证开发者

出现“无法验证开发者”或“Apple 无法验证”提示时：

1. 在 Finder 中右键 `MathCoach.app`，选择“打开”。
2. 在再次出现的对话框中点击“打开”。
3. 也可以前往“系统设置 → 隐私与安全性”，在安全区域点击“仍要打开”，然后重新启动应用。

### macOS：提示“已损坏”

浏览器下载通常会给应用附加 quarantine 属性。未签名应用可能因此提示“已损坏，无法打开”。确认文件来源与 SHA256 后执行：

```bash
xattr -cr /Applications/MathCoach.app
open /Applications/MathCoach.app
```

如提示权限不足，在 `xattr` 命令前加 `sudo`。不要为了安装应用而全局关闭 Gatekeeper。

## SHA256 校验

仓库不提供独立的 `SHA256SUMS` 文件。下表列出 v0.9.0 资产；大小与 SHA256 待产物发布后补充，请以 GitHub Release 页面与 Release Notes 为准。

| 文件 | 大小（字节） | SHA256 |
|---|---|---|
| `MathCoachSetup-0.9.0.exe` | 待补充 | 待补充 |
| `MathCoach-windows.zip` | 待补充 | 待补充 |
| `MathCoach-0.9.0.dmg` | 待补充 | 待补充 |
| `MathCoach-macos.zip` | 待补充 | 待补充 |

macOS / Linux：

```bash
shasum -a 256 ~/Downloads/MathCoach-0.9.0.dmg
# 或
sha256sum ~/Downloads/MathCoach-0.9.0.dmg
```

Windows PowerShell：

```powershell
Get-FileHash "$env:USERPROFILE\Downloads\MathCoachSetup-0.9.0.exe" -Algorithm SHA256
```

预期输出包含 64 位十六进制哈希；PowerShell 还会显示算法名与文件路径。待上表补齐 SHA256 后，将输出与上表逐字符比较；一致即表示文件完整。`shasum` 的常见格式为：

```text
<64 位十六进制 SHA256>  MathCoach-0.9.0.dmg
```

校验值随版本变化。升级后请以对应 Release 页面公布的 SHA256 为准。

## 首次启动

默认配置下，首次启动会自动创建本地 SQLite 数据库和所需表结构，无需手动执行迁移。

安装完成后首次启动不会弹出阻塞式欢迎页；应用内新手引导只在完成首次练习后以非阻塞卡片出现，可关闭或跳过。

- 不需要登录。
- 不要求配置 AI；未配置 Key 时使用离线模板，判分逻辑不变。
- 默认开启本机记忆；可在侧边栏关闭两个记忆开关进入游客模式，游客模式只存内存。

学习数据与 AI 密钥的位置：

| 内容 | Windows | macOS |
|---|---|---|
| 学习数据库 | `%LOCALAPPDATA%\mathcoach\mathcoach.sqlite3` | `~/Library/Application Support/mathcoach/mathcoach.sqlite3` |
| AI 密钥 | `%USERPROFILE%\.mathcoach\secrets.local` | `~/.mathcoach/secrets.local` |

Linux 从源码运行时，数据库由 `platformdirs` 决定，通常为 `~/.local/share/mathcoach/mathcoach.sqlite3`；可用环境变量 `MATHCOACH_DB` 覆盖。

## 版本与更新

当前版本：**v0.9.0**（2026-11-27）。仓库没有常驻更新进程，**不支持后台静默更新或自动安装**。

应用“设置”Tab 中的“关于与更新”提供“检查更新”按钮。点击后会查询 GitHub 最新 Release：

- 有新版本时显示版本号、Release Notes 摘要与下载链接。
- 没有新版本时显示“已是最新版本”。
- 离线或网络不可用时提示无法检查更新。
- 下载链接只会打开浏览器，不会下载或安装。

### 确认当前版本

“关于与更新”会显示当前版本号；Release 资产文件名也包含版本号，例如 `MathCoachSetup-0.9.0.exe`。

### 更新检查的网络与行为边界

- 启动和日常使用不会自动请求 GitHub；只有点击“检查更新”才发起一次只读 API 请求。
- 请求失败（离线、限流或接口不可用）只显示提示，不影响讲解、判分和本地数据。
- 不会在后台下载安装包，也不会替换或重启应用。

手动更新方式：

- Windows 安装器：下载新版本安装器，按相同或新的路径安装。安装目录中的程序文件会被替换。
- Windows 便携版：下载新 zip，解压到新目录并运行；旧目录可删除。
- macOS DMG：下载新 DMG，将 `MathCoach.app` 拖到“应用程序”，系统询问时选择替换。
- macOS 便携版：解压新 zip 并替换旧 `MathCoach.app`。

学习数据与 AI 密钥不在安装目录中，覆盖安装或替换应用不会清除这些数据。

### 升级兼容性

- 新版本可能升级本地数据库结构。升级后不要再用旧版本打开同一数据库；如果提示数据库版本高于当前应用版本，请升级应用，不要删除数据。
- 如需回退到旧版本，先备份数据库文件，再安装旧版本；旧版本可能无法读取新结构。
- 升级前关闭应用并备份数据库，是更稳妥的做法；数据库默认位置见“首次启动”一节。

各版本变更记录见仓库根目录的 [CHANGELOG.md](../CHANGELOG.md)；安装资产与校验值以 GitHub Releases 页面为准。

## 卸载与数据保留

- Windows：在 Windows 设置的“应用”列表中卸载 MathCoach。卸载程序移除安装目录、开始菜单快捷方式和卸载项。
- macOS：退出应用，将 `MathCoach.app` 移到废纸篓。
- 便携版：直接删除解压目录。

卸载不会自动删除学习数据库和 AI 密钥。如需彻底清除，请手动删除上表中的数据库文件、`~/.mathcoach/secrets.local`，以及数据库同目录下的 WAL/SHM 文件。删除后不可恢复。

## Linux：从源码运行

Linux 当前没有官方桌面安装包，发布矩阵仅包含 Windows 与 macOS。若你自行用 PyInstaller 构建了 Linux 产物，直接运行可能只启动本地服务而不出现窗口，并提示缺少 Qt/GTK：

```text
[pywebview] GTK cannot be loaded
[pywebview] QT cannot be loaded
webview.errors.WebViewException: You must have either QT or GTK with Python extensions installed in order to use pywebview.
```

原因：pywebview 在 Linux 需要 GTK（PyGObject + WebKit2GTK）或 Qt（PySide6/PyQt + qtpy + QtWebEngine），而 `requirements-packaging.txt` 只包含 PyInstaller 与 pywebview，不包含 GUI 后端。`--windowed` 产物会隐藏标准输出，需用 `--console` 构建或从终端运行才能看到上述错误。

规避方式：

1. 推荐从源码运行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

2. 复用打包产物的服务模式，无需 GUI 后端：

```bash
./MathCoach --streamlit-server 8501
```

然后在浏览器打开 <http://127.0.0.1:8501>。启动器会设置 `STREAMLIT_SERVER_ENABLE_STATIC_SERVING=true`，`static/` 下的庆祝动效资源仍可正常访问。

3. 若必须在 Linux 使用原生窗口，需要在构建环境安装 Qt 或 GTK 后端后重新构建，并自行验证 PyInstaller 是否收集了后端依赖。Qt 路线需 `PySide6` 与 `qtpy`；GTK 路线需 PyGObject 与 WebKit2GTK 4.1。详见 [桌面打包方案](packaging/desktop-packaging-plan.md#51-linux-打包产物的-gui-后端限制)。

无头或 CI 环境可用 Xvfb + Qt WebEngine；以 root 运行时需设置 `QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu"` 与 `QTWEBENGINE_DISABLE_SANDBOX=1`。

更多背景见 [README](../README.md) 与 [桌面打包方案](packaging/desktop-packaging-plan.md)。
