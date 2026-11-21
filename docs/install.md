# MathCoach 安装指南

本文覆盖从 GitHub Releases 下载桌面版后的安装、首次启动、未签名放行与 SHA256 校验。当前版本为 **v0.6.1**（2026-11-21）。

下载入口：

- 最新稳定版：<https://github.com/LJHLRJ/mathcoach/releases/latest>
- 全部版本与 Release Notes：<https://github.com/LJHLRJ/mathcoach/releases>

当前仅提供稳定版，没有预览通道。

## 支持平台

| 平台 | 发布资产 | 安装方式 |
|---|---|---|
| Windows x64 | `MathCoachSetup-0.6.1.exe` | Inno Setup 安装器，按用户安装 |
| Windows x64 | `MathCoach-windows.zip` | 便携版，解压后运行 |
| macOS | `MathCoach-0.6.1.dmg` | 打开后将应用拖到“应用程序” |
| macOS | `MathCoach-macos.zip` | 便携版，解压后打开 |
| Linux | 无桌面安装包 | 从源码运行，见文末 |

macOS 产物未签名、未公证；Release 未分别说明 Intel / Apple Silicon 架构，构建架构以 GitHub Actions Runner 为准（待确认）。

## Windows 安装器

1. 下载 `MathCoachSetup-0.6.1.exe`。
2. 双击运行。安装器为英文向导，按当前用户安装，不需要管理员权限。
3. 选择安装目录。默认路径为 `%LOCALAPPDATA%\Programs\MathCoach`，支持自定义路径。
4. 选择是否创建桌面图标。该选项默认不勾选；开始菜单快捷方式始终创建。
5. 点击安装。完成后，结束页默认勾选 “Launch MathCoach”，取消勾选则不会自动启动。
6. 卸载入口位于 Windows 设置的“应用”列表中的 MathCoach。

安装器会请求关闭正在运行的 MathCoach；安装完成后不会自动重启旧进程。使用静默安装时不会自动启动应用。

若启动后没有出现窗口，请尝试安装 Microsoft Edge WebView2 Runtime 后重新启动；v0.6.1 Release 说明记录了该排查项。

## Windows 便携版

1. 下载 `MathCoach-windows.zip`。
2. 解压到任意目录。
3. 运行解压目录中的 `MathCoach.exe`。

便携版不写入开始菜单，不注册卸载项；学习数据仍保存在用户数据目录，而不是解压目录。

## macOS 安装镜像

1. 下载 `MathCoach-0.6.1.dmg`。
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

仓库不提供独立的 `SHA256SUMS` 文件。下表哈希来自 GitHub Release 资产 digest（v0.6.1，2026-11-21 通过 GitHub API 核对），与 v0.6.1 Release Notes 中的值一致。

| 文件 | 大小（字节） | SHA256 |
|---|---|---|
| `MathCoachSetup-0.6.1.exe` | 86,618,261 | `9adddd6dc496b88b20884cf4d999447c59bfcc2a2cbe6f13676cd1c08df93b12` |
| `MathCoach-windows.zip` | 115,286,166 | `4e6629c70d039859e17e69ccfd30f69c969962d0fab13d958c07f017efd1a484` |
| `MathCoach-0.6.1.dmg` | 138,588,689 | `2e76b5ada0bdd5adcdb6335c04c72098017a2a9fafc520ed3ec995638c03c39a` |
| `MathCoach-macos.zip` | 111,157,703 | `a5725534c217c5e9816c9e4ab6f9facb4acf4195cc8c1248c8cf2d03e3d7bcc9` |

macOS / Linux：

```bash
shasum -a 256 ~/Downloads/MathCoach-0.6.1.dmg
# 或
sha256sum ~/Downloads/MathCoach-0.6.1.dmg
```

Windows PowerShell：

```powershell
Get-FileHash "$env:USERPROFILE\Downloads\MathCoachSetup-0.6.1.exe" -Algorithm SHA256
```

预期输出包含 64 位十六进制哈希；PowerShell 还会显示算法名与文件路径。将输出中的哈希与上表逐字符比较；一致即表示文件完整。`shasum` 的常见格式为：

```text
2e76b5ada0bdd5adcdb6335c04c72098017a2a9fafc520ed3ec995638c03c39a  MathCoach-0.6.1.dmg
```

校验值随版本变化。升级后请以对应 Release 的资产 digest 或 Release Notes 为准。

## 首次启动

默认配置下，首次启动会自动创建本地 SQLite 数据库和所需表结构，无需手动执行迁移。

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

当前版本：**v0.6.1**（2026-11-21）。仓库没有常驻更新进程，**不支持后台静默更新或自动安装**。

应用“设置”Tab 中的“关于与更新”提供“检查更新”按钮。点击后会查询 GitHub 最新 Release：

- 有新版本时显示版本号、Release Notes 摘要与下载链接。
- 没有新版本时显示“已是最新版本”。
- 离线或网络不可用时提示无法检查更新。
- 下载链接只会打开浏览器，不会下载或安装。

### 确认当前版本

“关于与更新”会显示当前版本号；Release 资产文件名也包含版本号，例如 `MathCoachSetup-0.6.1.exe`。

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

仓库没有独立 `CHANGELOG` 文件；每个版本的变更说明见 GitHub Releases。

## 卸载与数据保留

- Windows：在 Windows 设置的“应用”列表中卸载 MathCoach。卸载程序移除安装目录、开始菜单快捷方式和卸载项。
- macOS：退出应用，将 `MathCoach.app` 移到废纸篓。
- 便携版：直接删除解压目录。

卸载不会自动删除学习数据库和 AI 密钥。如需彻底清除，请手动删除上表中的数据库文件、`~/.mathcoach/secrets.local`，以及数据库同目录下的 WAL/SHM 文件。删除后不可恢复。

## Linux：从源码运行

Linux 当前没有桌面安装包。按 README 的“从源码安装”章节操作：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

更多背景见 [README](../README.md) 与 [桌面打包方案](packaging/desktop-packaging-plan.md)。
