# MathCoach 桌面客户端打包方案

本文档给出 Windows / macOS 桌面客户端的可重复构建方案。所有构建命令都需要在目标操作系统上、由用户本机执行；仓库不包含任何打包产物。

## 1. 路线对比与推荐

| 维度 | A. streamlit-desktop-app | B. 手动 PyInstaller + 启动器（推荐） |
|---|---|---|
| 构建方式 | 一条命令，内部调用 PyInstaller + pywebview | 显式调用 PyInstaller，入口为 `scripts/launch_desktop.py` |
| 资源携带 | 需要通过 `--pyinstaller-options` 透传 `--add-data` | 构建脚本直接生成 `--add-data`，路径一目了然 |
| 可控性 | 中，依赖封装层的参数透传 | 高，可单独调整端口、窗口、日志与收集项 |
| Python 兼容 | **0.3.4 明确排除 Python 3.13，3.14 未声明**；分类器仅 3.9—3.12 | 由 PyInstaller 版本决定；本仓库建议 3.11/3.12 |
| 依赖版本 | 固定 `pyinstaller>=6.11.1,<7`、`pywebview>=5.3.2,<6` | 可与项目其他依赖独立管理 |
| 结论 | 仅在 Python 3.9—3.12 构建环境可尝试 | **本项目推荐** |

【待确认】路线 A 的 `streamlit-desktop-app 0.3.4` 在 PyPI 元数据中声明 `requires_python` 排除 `3.13.*`，分类器最高到 Python 3.12。当前沙箱解释器为 Python 3.14.8，不在其声明范围内，不能视为已验证；若构建机使用 Python 3.13，pip 也会直接拒绝安装。因此不推荐 A。

路线 B 的额外成本是维护一个启动器，但换来：明确的 `--add-data`、可控的 `--collect-all streamlit --copy-metadata streamlit`、可选的 `--console` 排错，以及不依赖第三方封装层的版本策略。

## 2. 资源路径处理

当前源码入口：

```python
CONTENT_ROOT = Path(__file__).parent / "content"
```

PyInstaller 运行后：

- `onefile` 模式把所有文件解压到临时目录，`sys._MEIPASS` 指向该目录；
- `onedir` 模式（PyInstaller 6.x）通常把资源放在 `_internal`，`sys._MEIPASS` 同样指向资源根目录；
- 因此不能再假设 `__file__` 的父目录就是仓库根目录。

本仓库已把逻辑收敛到 `mathcoach/config.py` 的 `resolve_content_root()`：

```python
def resolve_content_root(app_file: Path) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "content"
    return Path(app_file).resolve().parent / "content"
```

`app.py` 仅做最小改动：

```python
CONTENT_ROOT = resolve_content_root(Path(__file__))
```

构建时必须同时携带：

- `content/` 目录（知识卡片、curriculum、prerequisites）；
- `app.py`（Streamlit 以脚本方式执行它，而不是 import）。

Windows 使用 `--add-data "content;content"`，macOS/Linux 使用 `--add-data "content:content"`；`scripts/build_desktop.py` 会按平台自动选择分隔符。

## 3. 前置条件

### Windows

- Windows 10/11，64 位 Python 3.11 或 3.12（推荐）。
- .NET Framework > 4.0（PyWebview 的 pythonnet 依赖）。
- Microsoft Edge WebView2 Runtime（PyWebview 默认使用 EdgeChromium 渲染）。
- 能正常创建虚拟环境并安装依赖。
- 需在本机验证：WebView2 是否已安装、双击启动是否出现原生窗口。

### macOS

- macOS 11+，64 位 Python 3.11 或 3.12（推荐）。
- PyWebview 使用 Cocoa/WebKit，不需要 .NET 或 WebView2。
- 未签名、未公证的 `.app` 首次启动会被 Gatekeeper 拦截，需要右键“打开”。
- 需在本机验证：`.app` 双击启动、窗口关闭后子进程是否退出。

### 通用

- PyInstaller **不是交叉编译器**：Windows 客户端必须在 Windows 上构建，macOS 客户端必须在 macOS 上构建。
- 构建机需要预留至少 2 GB 磁盘空间（Streamlit + SymPy + PyWebview 体积较大）。
- 建议在独立虚拟环境中构建，避免把开发依赖带入产物。

## 4. 构建步骤（由用户本机执行）

```bash
python -m venv .venv-build
# Windows: .venv-build\Scripts\activate
# macOS: source .venv-build/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-packaging.txt
```

先检查命令（不执行构建）：

```bash
python scripts/build_desktop.py --dry-run
```

正式构建（默认 onedir，启动更快）：

```bash
python scripts/build_desktop.py
```

单文件构建（体积略小但每次启动都要解压，明显更慢）：

```bash
python scripts/build_desktop.py --onefile
```

需要排错时保留控制台：

```bash
python scripts/build_desktop.py --console
```

预期输出路径：

- Windows onedir：`dist/MathCoach/MathCoach.exe`
- Windows onefile：`dist/MathCoach.exe`
- macOS：`dist/MathCoach.app`（PyInstaller 在 `--windowed` 下生成 app bundle）
- 中间文件：`build/`、`*.spec`，均已被 `.gitignore` 忽略

启动器行为：

1. 向系统申请空闲端口；
2. 以子进程启动本地 Streamlit，绑定 `127.0.0.1`；
3. 轮询 `/_stcore/health`，就绪后打开 PyWebview 原生窗口；
4. 关闭窗口时终止 Streamlit 子进程。

### 安装器

- Windows：`scripts/installer/MathCoach.iss`，Inno Setup 按用户安装到 `%LOCALAPPDATA%\Programs\MathCoach`，生成 `dist/installer/MathCoachSetup-<version>.exe`。
- macOS：`scripts/build_macos_dmg.sh`，用系统 `hdiutil` 生成 `dist/installer/MathCoach-<version>.dmg`，附带 `/Applications` 软链接。
- 安装器只包含程序文件，不包含学习数据或数据库。

## 5. 已知限制

- **体积**：Streamlit + SymPy + PyWebview 的 onedir 产物通常在数百 MB 量级；具体大小需在本机构建后确认。
- **启动速度**：onedir 一般数秒；onefile 需要先解压到临时目录，启动明显更慢。
- **Windows 运行时**：缺少 .NET Framework > 4.0 或 WebView2 Runtime 时，原生窗口无法创建；这不是 PyInstaller 能完全内嵌的。
- **macOS 签名**：本方案不包含代码签名与公证，首次启动会触发 Gatekeeper 提示。
- **Python 3.13/3.14**：3.13 被 streamlit-desktop-app 明确排除；3.14 未在其分类器中声明。路线 B 也需在本机验证 PyInstaller/PyWebview 兼容性，推荐使用 3.11/3.12。
- **PyInstaller 收集项**：`--collect-all streamlit --copy-metadata streamlit` 是必须项；若升级 Streamlit 后出现静态资源 404，需要重新验证收集项。
- **数据位置**：SQLite 默认仍在用户数据目录（`platformdirs`），不会打进客户端，也不会随客户端复制；卸载客户端不会自动删除学习数据。
- **安全边界**：本地服务只绑定 `127.0.0.1`，不对外网开放；仍建议在受信任的本机环境运行。
- **更新检查**：只读 GitHub Releases API，需联网；不会自动下载或执行安装器。
- 以上“构建后大小、启动时间、双击行为”均标记为**需在本机验证**，本仓库未实际执行打包。

## 6. 验证清单（需在本机执行）

1. `dist/` 下存在预期产物。
2. 双击产物，出现“数学陪练”原生窗口，不弹出浏览器。
3. 首屏能加载知识卡片；严格模式可用 `MATHCOACH_CONTENT_STRICT=1` 构建/运行验证。
4. 完成一次小测，确认离线模板模式可闭环。
5. 关闭窗口后，任务管理器/活动监视器中无残留 Streamlit 子进程。
6. 删除构建目录后重新执行构建脚本，产物可重复生成。
7. 确认 `git status` 中只有源码与本文档变更，没有 `dist/`、`build/`、`*.spec`。
8. Windows 安装器可按用户完成安装、创建开始菜单快捷方式并卸载。
9. macOS DMG 可挂载并拖拽安装。

## 7. GitHub Actions 发布

`.github/workflows/release-desktop.yml` 在 GitHub Release 发布后运行：

- 在 `windows-latest` 与 `macos-latest` 上安装依赖并执行全量 `pytest`；
- 使用 `scripts/build_desktop.py` 构建；
- Windows 生成 `MathCoach-windows.zip` 与 `MathCoachSetup-<version>.exe`；
- macOS 生成 `MathCoach-macos.zip` 与 `MathCoach-<version>.dmg`；
- 通过 `gh release upload` 附加到当前 Release。

产物不进入 git 仓库，只作为 Release 资产分发。构建机架构以 GitHub Runner 为准；未做代码签名，Windows SmartScreen 与 macOS Gatekeeper 可能提示。

## 7.1 手动/标签构建（仅 artifact，不创建 Release）

`.github/workflows/build-desktop.yml` 用于构建桌面产物并上传 artifact：

- 触发方式：Actions 页面的 `workflow_dispatch` 手动触发，或推送 `v*` tag。
- 矩阵：`windows-latest` 与 `macos-latest`，Python 3.12。
- 步骤：checkout → setup-python → 安装 `requirements.txt` 与 `requirements-packaging.txt` → `python scripts/build_desktop.py --output-dir dist` → `actions/upload-artifact@v4`。
- 不执行 `git push`，不创建 Release，不对 macOS 签名；产物只作为 workflow artifact 保存。
- 下载：打开对应 Actions run，在页面底部 Artifacts 下载 `MathCoach-windows-latest` 或 `MathCoach-macos-latest`；解压后 Windows 运行 `MathCoach/MathCoach.exe`，macOS 打开 `MathCoach.app`。
- macOS 产物未签名：首次打开需右键“打开”，或在“系统设置 → 隐私与安全性”中仅对该应用选择“仍要打开”；不要全局关闭 Gatekeeper。
- `--output-dir` 会映射到 PyInstaller 的 `--distpath`，默认 `dist/`；该路径行为需在本机验证一次。
- 需在仓库中验证一次 workflow：手动触发或推送 `v*` tag，确认两个 job 成功且 artifact 可下载。本仓库沙箱未执行真实 runner 构建。

## 8. 更新检查

- `mathcoach/update_check.py` 只读 GitHub Releases latest API，3 秒超时，无 Token。
- 侧边栏“关于与更新”由用户点击触发；不自动联网、不自动下载、不执行安装器。
- 网络失败或限流只显示提示，不影响判题与本地记忆。

## 9. 参考

- streamlit-desktop-app PyPI：<https://pypi.org/project/streamlit-desktop-app/>（0.3.4，`requires_python` 排除 3.13）
- PyInstaller 使用文档：<https://pyinstaller.org/en/stable/usage.html>（`--add-data`、`--collect-all`、`--copy-metadata`）
- PyWebview 安装说明：<https://pywebview.flowrl.com/guide/installation>（Windows 需要 .NET > 4.0 与 WebView2）
- Streamlit 社区 PyInstaller 讨论：<https://discuss.streamlit.io/t/using-pyinstaller-or-similar-to-create-an-executable/902>
