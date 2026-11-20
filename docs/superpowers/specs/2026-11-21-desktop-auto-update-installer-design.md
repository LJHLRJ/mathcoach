# 桌面客户端自动更新与安装器设计

日期：2026-11-21
状态：已确认方案 A，待实施
版本目标：v0.3.0

## 1. 背景与目标

当前 `v0.2.3` 已通过 GitHub Actions 构建 Windows/macOS 便携 zip，但用户仍需手动下载压缩包，且应用内没有版本/更新入口。

本设计新增两件事：

1. **更新检查**：应用内检查 GitHub Releases，提示新版本并提供官方下载入口。
2. **安装器**：Windows 提供 Inno Setup 安装器，macOS 提供 DMG；同时保留便携 zip。

### 非目标

- 不做后台静默下载与静默安装。
- 不做代码签名、公证或自建更新服务器。
- 不做差分更新、灰度通道或强制更新。
- 不做 Linux 客户端安装器。

## 2. 方案选择

选择 **方案 A：更新检查 + 引导下载 + 安装器**。

不选择方案 B（全自动下载 + 静默安装）的原因：

- 当前 Windows/macOS 产物未签名、未公证。
- macOS 的 `.app` 自替换受 Gatekeeper 与文件权限限制，无法在 CI 中真实验证。
- 后台下载并执行安装包会扩大安全边界；应用本身是本地优先、离线可用的。
- 方案 A 已能满足“自动检查更新 + 可安装”的用户价值。

## 3. 架构与组件

### 3.1 更新检查模块

新增 `mathcoach/update_check.py`，不引入新依赖。

公开接口：

```python
@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    page_url: str
    notes: str

class UpdateCheckError(RuntimeError):
    ...

def parse_version(value: str) -> tuple[int, ...]: ...
def is_newer(latest: str, current: str) -> bool: ...
def fetch_latest_release(timeout_s: float = 3.0) -> ReleaseInfo: ...
def check_for_update(
    current_version: str,
    fetcher: Callable[[str, float], dict] | None = None,
) -> ReleaseInfo | None: ...
```

行为：

- 请求 `https://api.github.com/repos/LJHLRJ/mathcoach/releases/latest`。
- HTTPS、3 秒超时、无 Token、带 `User-Agent: MathCoach`。
- `tag_name` 去掉前缀 `v` 后与当前版本做数字元组比较。
- `parse_version` 无法解析时返回空元组；`is_newer` 对任一空元组返回 `False`；`check_for_update` 在远端版本为空元组时抛出 `UpdateCheckError`，不误报更新。
- 仅当远端版本更高时返回 `ReleaseInfo`；同版本/更低返回 `None`。
- 网络错误、非 200、JSON 缺少字段、版本无法解析时抛出 `UpdateCheckError`。
- `fetcher` 可注入，测试不访问真实网络。
- 不在应用启动时自动请求；只有用户点击“检查更新”才请求。

### 3.2 UI 接入

在 `app.py` 侧边栏末尾增加“关于与更新”折叠区：

- 显示当前版本 `mathcoach.__version__`。
- “检查更新”按钮：
  - 发现新版本：显示版本号、简述与“打开下载页”链接。
  - 已是最新：显示“已是最新版本”。
  - 检查失败：显示“无法检查更新（离线或网络不可用）”。
- 检查结果存入 `st.session_state`，避免 Streamlit rerun 重复请求。
- 使用 `st.link_button` 打开 Release 页面；不自动下载文件。

### 3.3 Windows 安装器

新增 `scripts/installer/MathCoach.iss`，使用 Inno Setup 6。

关键配置：

- 稳定 `AppId`，支持覆盖升级。
- 按用户安装：`DefaultDirName={localappdata}\Programs\MathCoach`。
- `PrivilegesRequired=lowest`，不要求管理员权限。
- 安装 `dist\MathCoach\*` 全部文件。
- 创建开始菜单快捷方式与卸载项。
- 安装完成后可选启动应用。
- 产物：`dist/installer/MathCoachSetup-<version>.exe`。

版本号由 CI 通过 `/DMyAppVersion=<version>` 注入，避免手写重复。

### 3.4 macOS DMG

新增 `scripts/build_macos_dmg.sh`，只使用 macOS 自带 `hdiutil`。

流程：

1. 读取 `mathcoach.__version__`。
2. 创建临时 staging 目录，复制 `dist/MathCoach.app`。
3. 加入指向 `/Applications` 的软链接，便于拖拽安装。
4. `hdiutil create -volname MathCoach -srcfolder <staging> -ov -format UDZO`。
5. 产物：`dist/installer/MathCoach-<version>.dmg`。

不生成 `.pkg`，不做静默安装。

### 3.5 CI 与发布

扩展 `.github/workflows/release-desktop.yml`：

- Windows：
  - 安装 Inno Setup（Chocolatey）。
  - 运行 `ISCC.exe /DMyAppVersion=<version> scripts\installer\MathCoach.iss`。
  - 上传 `MathCoachSetup-<version>.exe`。
- macOS：
  - 运行 `scripts/build_macos_dmg.sh`。
  - 上传 `MathCoach-<version>.dmg`。
- 两个平台继续上传便携 zip。
- 一个 Release 共 4 个资产：
  - `MathCoach-windows.zip`
  - `MathCoachSetup-<version>.exe`
  - `MathCoach-macos.zip`
  - `MathCoach-<version>.dmg`
- Release 说明增加安装器步骤、SmartScreen/Gatekeeper 提示与 SHA256。

### 3.6 版本与发布

- `pyproject.toml` 与 `mathcoach/__init__.py` 同步升级到 `0.3.0`。
- 打 annotated tag `v0.3.0`，创建 Release。
- Release 触发 Actions 构建并附加 4 个资产。

## 4. 数据流

```text
用户点击“检查更新”
  → check_for_update(mathcoach.__version__)
  → GitHub Releases latest API
  → 版本比较
  → UI 显示“新版本 + 打开下载页” / “已是最新” / “离线或网络错误”

用户下载安装器
  → Windows: MathCoachSetup-<version>.exe → 按用户安装 → 开始菜单/卸载项
  → macOS: MathCoach-<version>.dmg → 拖入 Applications → 右键打开
```

更新检查不写入数据库、不发送学习数据，只发送 GitHub API 必需的 HTTP 请求头。

## 5. 错误处理

- 网络不可用、超时、GitHub 限流、JSON 异常：统一提示“无法检查更新”，不崩溃。
- 远端 tag 或当前版本无法解析：抛出 `UpdateCheckError`，UI 显示“无法检查更新”，不误报有新版本。
- 安装器：
  - Windows 安装失败由 Inno Setup 显示错误；不自动重试。
  - macOS DMG 挂载/拖拽失败由系统提示；不做自动修复。
- 应用启动、离线模式、判题与记忆层不受更新检查影响。

## 6. 测试策略

新增 `tests/test_update_check.py`：

- `is_newer`：高版本、同版本、低版本、`v` 前缀、畸形版本。
- `check_for_update`：假 fetcher 返回新版本 → `ReleaseInfo`；同版本 → `None`；缺少字段/异常 → `UpdateCheckError`。
- 不访问真实网络。

新增 `tests/test_installer_config.py`：

- `.iss` 包含按用户安装、无需管理员、开始菜单、卸载项、安装器输出名。
- DMG 脚本包含 `hdiutil create` 与 `/Applications` 软链接。
- CI workflow 包含 Inno Setup、DMG 构建与 4 个资产上传。

回归：

- 原有 217 项测试保持通过。
- 版本一致性测试继续校验 `pyproject.toml` 与 `mathcoach.__version__`。
- 严格模式内容校验不受影响。

## 7. 安全与合规

- 更新检查只读 GitHub API，不下载、不执行任何文件。
- 用户必须主动点击“检查更新”；不在启动时联网。
- 安装器与 DMG 不含学习数据、数据库、音频、模型或 Token。
- 产物不入 git 仓库，只作为 Release 资产分发。
- 未签名产物继续提示 SmartScreen/Gatekeeper；不引导关闭系统安全设置。
- 不自动安装；安装动作由用户在本机完成。

## 8. 验收标准

1. `v0.3.0` Release 包含 4 个资产，Windows/macOS 构建任务成功。
2. 应用侧边栏显示版本号；点击“检查更新”能显示新版本/已最新/离线提示。
3. 更新检查失败不影响应用其他功能。
4. Windows 安装器可按用户安装、创建快捷方式并可卸载。
5. macOS DMG 可挂载并拖拽安装。
6. 全部测试通过，仓库不包含安装器产物。

## 9. 已知限制

- 不提供静默自动更新；用户仍需点击下载并运行安装器/拖拽 DMG。
- 无代码签名与公证，SmartScreen/Gatekeeper 提示属预期。
- GitHub API 匿名请求有限流，频繁检查可能收到 403。
- macOS 构建架构取决于 GitHub Runner；Intel 兼容性需本机验证。
- 不做增量更新；每次更新下载完整安装包。
