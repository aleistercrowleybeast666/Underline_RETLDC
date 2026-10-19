# Underline RETLDC

火箭发动机试车数据的离线解析、校准、分析与导出工具。
Offline rocket-engine test log decoding, calibration, analysis and export.

**稳定版 v0.1.0 · 2026-10-15** — [Windows 下载](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/tag/v0.1.0) · [记录与叠图示例](docs/Recorded_Data_Showcase.md) · [完整中文手册](README.txt) · [English quick start](#english-quick-start)

**橙线来自公开原始记录，按近似峰值估算为 `0.49 × raw` N；未扣静止偏置，不是设备标定后的净推力。绿虚线是其趋势派生的平滑合成参考，不是真实理论预测，不用于性能证明或工程推断。**

![Underline RETLDC v0.1.0 中文推力页：原始记录的估算换算与明示合成参考，缺质量时比冲不可用](docs/assets/record-overlay-estimate.png)

*与 v0.1.0 标签一致的真实 Qt 界面离屏渲染，不是桌面录屏。Peak-based scale estimate; synthetic reference, not a physical prediction. [换算来源、零点和复现步骤](docs/Recorded_Data_Showcase.md)。*

## 下载与开始

1. 下载 [Windows 便携包](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/download/v0.1.0/Underline_RETLDC_0_1_0_Windows_Portable.zip)，按 [Release 正文](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/tag/v0.1.0) 的 SHA-256 核对文件。
2. 完整解压到可写目录，运行 `Underline_RETLDC.exe`；无需安装 Python，保留整个目录。
3. 在“工程”导入记录，核对时间、通道与物理单位，按需校准；进入推力、室压或温度页确认试车区间，再计算和导出。

**无硬件体验（三步）：** 按[记录示例指引](docs/Recorded_Data_Showcase.md)保存原始 TXT、合成参考 CSV 与工程 JSON → 从示例目录启动应用并打开工程 → 在推力页对齐、切换指标来源计算，或查看工作区间 FFT、导出实验结果。文件位于 [examples/record_showcase](examples/record_showcase)；发布包内不含这些后补样例。另保留[两条均为合成数据的极简教学例](docs/Synthetic_Overlay_Example.md)。

[对齐前](docs/assets/record-before-alignment.png) · [合成参考独立结果](docs/assets/record-reference-metrics.png) · [工作区间 FFT](docs/assets/record-interval-fft.png) · [实验导出](docs/assets/record-export-options.png)。目前提供截图，没有视频。

v0.1.0 有两个发布附件：便携包与[对应源码包](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/download/v0.1.0/Underline_RETLDC_0_1_0_Corresponding_Sources.zip)。校验值在 Release 正文，**没有独立的 `SHA256SUMS.txt` 附件**。对应源码包包含第三方原始归档；GitHub 自动生成的 Source code ZIP 不能替代它。

## 可以做什么

- 导入 TR_F / TR_P / TR_T、CSV / TSV / XLSX；通用表格使用明确列映射，可保存 JSON 预设。
- 在现有时间曲线上叠加实验与理论来源，调整显示对齐，分别计算指标；原始文件只读。
- 查看选定工作区间的曲线与 FFT；导出 CSV、PNG、TXT / JSON 报告及满足物理输入条件的 OpenRocket ENG。
- 保存工程与视图，切换简体中文 / English、浅色 / 深色主题。

软件用于离线记录，不承担点火、实时采集或控制。自动试车区间需要人工确认；比冲需要有效推进剂质量。正式统一导出使用实验主流程，包含理论叠图的图片请使用图表右键 Export。FFT 不是 PSD，也不能单独证明共振、发动机稳定性或振动原因。ENG → OpenRocket 实际导入兼容演示仍待验证。

## English quick start

Download the [v0.1.0 Windows portable ZIP](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/tag/v0.1.0), compare its SHA-256 with the release body, extract the complete folder and run `Underline_RETLDC.exe`. Python is bundled. Switch the UI to English in Settings.

Import a recorded file in Project, confirm timestamps, quantities and units, apply calibration if needed, select the test interval, then calculate and export. Try the [recorded-data walkthrough](docs/Recorded_Data_Showcase.md#english-walkthrough): the original raw record is preserved; `0.49 N/raw` is a user peak-based estimate with zero offset and no baseline subtraction, not a verified sensor calibration. Its smoother synthetic reference is derived from the record, not an independent physical prediction or performance validation. Missing propellant mass leaves Isp unavailable.

Save the TXT, reference CSV and project JSON together, launch the app with that folder as its working directory, then open the project and switch metric sources in Thrust. The screenshots are real Qt offscreen renders; no desktop video is provided. FFT alone does not establish resonance or engine stability. An actual ENG import demonstration in OpenRocket remains unverified.

## 文档与开发 / Documentation

| 入口 | 内容 |
|---|---|
| [README.txt](README.txt) | 完整操作手册 / Full Chinese manual |
| [记录示例 / Recorded-data showcase](docs/Recorded_Data_Showcase.md) | 原始 TXT、估算比例、平滑合成参考、中文截图与现成工程 |
| [极简合成例 / Synthetic example](docs/Synthetic_Overlay_Example.md) | 两条均为合成数据的短记录与复现公式 |
| [来源与理论曲线 / Source curves](docs/Theoretical_Curves.md) | 对齐、独立计算与导出边界 |
| [数据格式 / Data formats](docs/Data_Formats.md) | 表格映射、单位与工程格式 |
| [Plugin API v1](docs/Plugin_API.md) | 解析、校准、处理、分析和导出插件 |
| [v0.1.0 更新说明](docs/Release_Notes_0_1_0.md) | 该版本功能与验证记录 |

源码运行：Python ≥ 3.11；在仓库根目录安装依赖后启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe main.py
```

已有环境请直接复用 `.venv`。源码修改应先读 [AGENTS.md](AGENTS.md) 与 [TARGETS.md](TARGETS.md)。

原创代码采用 [Apache-2.0](LICENSE)；第三方组件适用各自许可，见 [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)。反馈请附版本、复现步骤及可公开的最小输入：[GitHub Issues](https://github.com/aleistercrowleybeast666/Underline_RETLDC/issues)。
