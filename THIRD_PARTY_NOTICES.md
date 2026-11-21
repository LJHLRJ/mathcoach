# Third-Party Notices

本文件列出 MathCoach 使用的第三方资源、许可证与使用方式。

- 核实日期：2026-11-21
- 核实人：待人工复核
- 原则：来源不明或许可证不清的资源一律不使用；外部链接不等于打包或再分发。

## 资源清单

| 资源 | 来源 | 许可证 | 是否需署名 | 本项目使用方式 | 状态 |
|---|---|---|---|---|---|
| Pattern Craft | https://github.com/megh-bari/pattern-craft | MIT | 是，保留版权与许可声明 | 改编 3 个低对比度 CSS 背景图案 | 已使用 |
| uisfx | https://github.com/romainsimon/uisfx | 代码 MIT；音频 CC0 1.0 | 音频无需署名；代码未复制 | 4 个反馈音 cue，以 base64 常量嵌入 | 已使用 |
| Noisekun | https://github.com/mateusfg7/Noisekun | 代码 MIT；音源逐项许可 | 代码 MIT；音频按逐项许可 | 仅外部链接，不打包音频 | 已使用（仅链接） |
| Moodist | https://github.com/remvze/moodist | 代码 MIT；音源 Pixabay/CC0 等 | 代码 MIT；音频按各自许可 | 仅外部链接，不打包音频 | 已使用（仅链接） |
| Open Lo-Fi | https://github.com/btahir/open-lofi | CC0 1.0 | 否 | 仅外部链接，不打包音频 | 已使用（仅链接） |
| CozyPixels | https://github.com/SleepyCatHey/CozyPixels | 仓库 MIT；壁纸来源未逐一追踪 | 不适用 | **仅参考配色，未使用任何图片** | 仅参考 |
| math-pattern-gen | https://github.com/martin-ushiyama/math-pattern-gen | MIT | 是 | 未使用 | 未使用 |
| tiks | https://github.com/rexa-developer/tiks | MIT | 是 | 未使用 | 未使用 |
| bgvault | https://github.com/WabweniBrian/bgvault | 未检测到许可证（NOASSERTION） | 待确认 | 未使用 | 未使用，待人工核实 |
| Quiz and Game Show Sound Effects | 未找到可核实的 CC0 仓库或打包来源 | 预期 CC0，未证实 | 待确认 | 未使用 | 未使用，待人工核实 |

## 具体使用说明

### Pattern Craft

- 仅使用 CSS 背景图案，不复制图片资源。
- 适配为浅色/深色常量 CSS；未拼接用户输入。
- 版权与许可声明保留在本文件及代码注释中。

### uisfx

- 使用 commit `9950fe66f993a6660dab9c2651dcbcd899ffd83b` 的 `packages/uisfx/sounds/organic/` 下 4 个音频：
  - `success.mp3`（7,984 字节）
  - `error.mp3`（6,939 字节）
  - `complete.mp3`（8,611 字节）
  - `select.mp3`（4,013 字节）
- 音频以 base64 常量嵌入 `mathcoach/ui/sound.py`，不新增二进制资源文件。
- `LICENSE-AUDIO`：https://github.com/romainsimon/uisfx/blob/9950fe66f993a6660dab9c2651dcbcd899ffd83b/LICENSE-AUDIO
- uisfx 代码为 MIT（Copyright (c) 2026 Yuki Capital），但本项目未复制其代码。

### Noisekun

- 仅提供 https://noisekun.com 外部链接，不打包或再分发任何音频。
- README 中逐项音源许可证：CC0 音源可用；Train（CC Sampling+）、Washing Machine（QuickSounds Standard License）、Waterfall（CC BY）、White noise / Pink Noise（CC BY-SA）、Rain on Tent（CC BY 4.0）等未使用。
- 外部站点的播放与使用条款由 Noisekun 及其音源作者负责。

### Moodist

- 仅提供 https://moodist.mvze.net 外部链接，不打包或再分发任何音频。
- 代码 MIT（Copyright (c) 2023 MAZE）；音源包含 Pixabay Content License 与 CC0，具体以项目 README 为准。
- 外部站点的播放与使用条款由 Moodist 及其音源作者负责。

### Open Lo-Fi

- 仅提供 https://github.com/btahir/open-lofi 外部链接，不打包或再分发音频。
- 曲目声明为 CC0 1.0（public domain），无需署名；本项目仍列出以示尊重。

### CozyPixels

- 仅参考配色方案，未下载、复制或打包任何壁纸/图片。
- 该仓库 README 明示壁纸来自多个社交平台且来源未逐一追踪，因此本项目不使用其图片。

### 未使用资源

- **math-pattern-gen**：MIT 已核实，但按当前方案只使用 Pattern Craft CSS 图案。
- **tiks**：MIT 已核实，仓库无音频文件；当前使用 uisfx 音频，不采用其合成代码。
- **bgvault**：未检测到许可证，不使用。
- **Quiz and Game Show Sound Effects**：未找到可核实的 CC0 来源，不使用。

## MIT License（Pattern Craft）

```text
MIT License

Copyright (c) 2025 Megh Bari

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 免责声明

本项目集成的背景图案、音效与环境音来自第三方开源项目，其许可证以各项目仓库声明为准。我们已尽力核实许可证信息，但**不对第三方资源的版权状态作任何法律保证**，也不构成法律建议。

- CC0 / 公有领域资源：无需署名，但我们仍在 THIRD_PARTY_NOTICES.md 中列出来源以示尊重。
- MIT 资源：保留原版权声明与许可声明。
- 来源不明或许可证不清的资源：一律不使用。

若你是权利人并认为本项目使用不当，请通过仓库 Issue 联系，我们将在核实后移除相关内容。

用户自行选择的外部曲库与外部链接，其许可证与使用条款由对应项目负责，本项目仅提供入口，不承担相关责任。
