# Third-Party Notices

本文件列出 MathCoach 使用的第三方资源、许可证与使用方式。

- 核实日期：2026-11-21
- 核实人：待人工复核
- 原则：来源不明或许可证不清的资源一律不使用；外部链接不等于打包或再分发。

## 资源清单

| 资源 | 来源 | 许可证 | 是否需署名 | 本项目使用方式 | 状态 |
|---|---|---|---|---|---|
| Pattern Craft | https://github.com/megh-bari/pattern-craft | MIT | 是，保留版权与许可声明 | 改编 3 个低对比度 CSS 背景图案 | 已使用 |
| Radiant | https://github.com/pbakaus/radiant | MIT | 是，保留版权与许可声明 | 2 个 shader HTML 内联到动态背景 | 已使用 |
| canvas-confetti | https://github.com/catdad/canvas-confetti | ISC | 是，保留版权与许可声明 | 全屏庆祝静态 overlay | 已使用 |
| uisfx | https://github.com/romainsimon/uisfx | 代码 MIT；音频 CC0 1.0 | 音频无需署名；代码未复制 | 4 个反馈音 cue，以 base64 常量嵌入 | 已使用 |
| Noisekun | https://github.com/mateusfg7/Noisekun | 代码 MIT；音源逐项许可 | 代码 MIT；音频按逐项许可 | 仅外部链接，不打包音频 | 已使用（仅链接） |
| Moodist | https://github.com/remvze/moodist | 代码 MIT；音源 Pixabay/CC0 等 | 代码 MIT；音频按各自许可 | 仅外部链接，不打包音频 | 已使用（仅链接） |
| Open Lo-Fi | https://github.com/btahir/open-lofi | CC0 1.0 | 否 | 仅外部链接，不打包音频 | 已使用（仅链接） |
| CozyPixels | https://github.com/SleepyCatHey/CozyPixels | 仓库 MIT；壁纸来源未逐一追踪 | 不适用 | **仅参考配色，未使用任何图片** | 仅参考 |
| math-pattern-gen | https://github.com/martin-ushiyama/math-pattern-gen | MIT | 是 | 未使用 | 未使用 |
| tiks | https://github.com/rexa-developer/tiks | MIT | 是 | 未使用 | 未使用 |
| css-doodle | https://github.com/css-doodle/css-doodle | MIT | 是 | 仅备选，未集成 | 未使用 |
| streamlit-animate | 未找到可核实原项目：`saajunaid/junai` 现为 caddis-plugin；PyPI `streamlit-animate` 404 | 待人工核实 | 待确认 | 未提取 CSS/代码；微交互为自写 | 未集成，待人工核实 |
| weft-ui | https://github.com/ankittripathi1/weft-ui | MIT | 是 | 未集成；需新依赖且要求 Streamlit >=1.66 | 未使用 |
| matanim | 未找到明确对应仓库；候选 `matino06/MatAnim` 为 NOASSERTION | 待人工核实 | 待确认 | 未集成 | 未集成，待人工核实 |
| handanim | https://github.com/subroy13/handanim | MIT | 是 | 仅文档说明（离线视频生成，非实时） | 未集成 |
| bgvault | https://github.com/WabweniBrian/bgvault | 未检测到许可证（NOASSERTION） | 待确认 | 未使用 | 未使用，待人工核实 |
| Quiz and Game Show Sound Effects | 未找到可核实的 CC0 仓库或打包来源 | 预期 CC0，未证实 | 待确认 | 未使用 | 未使用，待人工核实 |

## 具体使用说明

### Pattern Craft

- 仅使用 CSS 背景图案，不复制图片资源。
- 适配为浅色/深色常量 CSS；未拼接用户输入。
- 版权与许可声明保留在本文件及代码注释中。

### Radiant

- 使用 commit `59e9f48c0ad9a3db2fbeb8898b4390d5a1eabb40` 的 `static/flow-field.html`（10,086 字节）与 `static/topographic.html`（16,179 字节）。
- 两个 shader 以内联常量放入 `mathcoach/ui/motion.py`，仅用于仪表盘/空状态装饰面板。
- 已核实两个文件无外部 `http`/`src` 请求。
- MIT 版权：Copyright (c) 2025 Paul Bakaus；完整许可见下方 MIT 文本。

### canvas-confetti

- 版本 1.9.4，ISC License，Copyright (c) 2020 Kiril Vatev。
- 文件：
  - `static/overlay/confetti.html`
  - `static/overlay/confetti.browser.js`
  - `static/overlay/canvas-confetti.LICENSE.txt`
- 通过固定定位 iframe 覆盖视口；`pointer-events:none`；`prefers-reduced-motion` 时跳过。
- 版权头保留在 `confetti.browser.js`，完整 ISC 文本见同目录许可证文件与下方文本。

### css-doodle

- MIT 已核实；npm 0.70.1 压缩版约 233,883 字节。
- 仅作为备选记录，未集成。

### streamlit-animate

- 提示中的 `saajunaid/junai` 当前指向 `saajunaid/caddis-plugin`（MIT，但不是 streamlit-animate）；PyPI `streamlit-animate` 返回 404。
- 原计划仅提取 CSS 模式、未引入工具链；实际因许可证无法核实，**未提取任何 CSS 或代码**。
- 当前微交互为自写常量 CSS，不依赖该资源。

### weft-ui

- MIT；PyPI 0.1.0 要求 Python >=3.12、Streamlit >=1.66。
- 当前项目 Streamlit 1.57.0，且未授权新增依赖；未集成。

### matanim

- 未找到许可证明确且与提示相符的仓库；候选 `matino06/MatAnim` 为 NOASSERTION。
- 未集成，待人工核实。

### handanim

- MIT；离线 Python 视频生成工具，非实时动画库。
- 仅作文档说明，不在应用内集成。

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

## MIT License（Radiant）

```text
MIT License

Copyright (c) 2025 Paul Bakaus

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

## ISC License（canvas-confetti）

```text
ISC License

Copyright (c) 2020, Kiril Vatev

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

## 免责声明

本项目集成的背景图案、音效与环境音来自第三方开源项目，其许可证以各项目仓库声明为准。我们已尽力核实许可证信息，但**不对第三方资源的版权状态作任何法律保证**，也不构成法律建议。

- CC0 / 公有领域资源：无需署名，但我们仍在 THIRD_PARTY_NOTICES.md 中列出来源以示尊重。
- MIT 资源：保留原版权声明与许可声明。
- 来源不明或许可证不清的资源：一律不使用。

若你是权利人并认为本项目使用不当，请通过仓库 Issue 联系，我们将在核实后移除相关内容。

用户自行选择的外部曲库与外部链接，其许可证与使用条款由对应项目负责，本项目仅提供入口，不承担相关责任。

### 动效与微交互

本项目的动态背景、庆祝动效与微交互参考了第三方开源资源，其许可证以各项目仓库声明为准。我们已尽力核实许可证信息，但**不对第三方资源的版权状态作任何法律保证**，也不构成法律建议。

- MIT / ISC / CC0 / 公有领域资源：按对应许可证使用；需要保留版权声明的，已在 THIRD_PARTY_NOTICES.md 中保留。
- 仅参考设计模式、未引入代码的资源：已注明“仅参考”。
- 来源不明或许可证不清的资源：一律不集成。

若你是权利人并认为本项目使用不当，请通过仓库 Issue 联系，我们将在核实后移除相关内容。

用户自行启用的动效与背景，其性能表现可能因设备而异，本项目不对特定设备上的帧率或耗电作保证。
