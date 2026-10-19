# Underline RETLDC

面向火箭发动机台架试车记录的离线桌面工具，支持推力、燃烧室压力与温度数据的导入、校准、分析和导出。可用于固体火箭发动机静态试车数据处理与推力曲线分析。
An offline desktop tool for importing, calibrating, analyzing and exporting rocket-engine static fire test data, including thrust, chamber pressure and temperature. Suitable for solid rocket motor test records and thrust curve analysis.

**[下载 Windows 便携版](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/download/v0.1.0/Underline_RETLDC_0_1_0_Windows_Portable.zip)** · [体验](docs/Recorded_Data_Showcase.md) · [使用手册](README.txt) · [发布文章](https://www.kechuang.org/t/91966) · [English](#english-quick-start)

**对照实验记录与模拟参考。** 橙线为一台固态燃料火箭发动机的实验记录，绿虚线为由该记录生成的平滑模拟参考，并非独立理论预测。

![推力曲线叠图：左侧滑动条与偏移输入框用于时间平移，右侧切换指标来源](docs/assets/record-overlay-estimate.png)

拖动滑动条或输入偏移秒数，就能平移参考曲线；也可以按两份数据的试车起点自动对齐，再手动微调。[查看平移前后对比](docs/Recorded_Data_Showcase.md#移动时间轴与对齐曲线)。

## 主要功能

- **导入与校准**：支持 TR_F / TR_P / TR_T 双列记录、CSV / TSV / 自定义分隔文本和 XLSX；保存列映射预设、配置校准与显示单位，保留原始样本。
- **实验与理论曲线对照**：导入已有理论或模拟数据，在推力、燃烧室压力和温度时间图中叠加显示。平移、自动对齐试车起点、手动微调，并分别计算可用指标；显示平移不改变科学时间或计算区间。
- **试车区间**：自动识别候选，也可拖动边界确认起止时刻；切换全段或只看选定工作区间。
- **频谱分析**：对选定区间查看 FFT，可去均值，X/Y 轴支持线性或对数坐标，观察频率成分和局部峰值。
- **保存与导出**：保存工程、配置和视图；导出实验 CSV、正式曲线 PNG、TXT / JSON 报告，以及满足输入条件的 ENG。统一导出使用实验数据；图表右键 Export 可导出当前参考曲线叠图。
- **界面**：简体中文 / English、浅色 / 深色主题；报告可独立选择中文或英文。

FFT 对非等间隔时钟使用线性插值，长时间间隙会限制频谱解释；频谱峰值不能单独证明共振。[示例说明](docs/Recorded_Data_Showcase.md)记录了换算、参考生成方法和计算边界。

![实验工作区间 FFT，X/Y 双对数坐标；横轴频率 Hz，纵轴 FFT 模值 N](docs/assets/record-fft-loglog.png)

*中文界面截图（Qt 离屏渲染）。[查看操作指南与示例数据说明](docs/Recorded_Data_Showcase.md)。*

## 体验

当前稳定版 **v0.1.0 · 2026-10-15**。下载便携 ZIP，对照 [Release 正文](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/tag/v0.1.0) 的 SHA-256 校验，完整解压后运行 `Underline_RETLDC.exe`，无需安装 Python。

按[示例指引](docs/Recorded_Data_Showcase.md)将 TXT、参考 CSV 和工程 JSON 保存到任意可写目录，即可打开工程体验平移曲线、独立计算、FFT 和导出。[下载示例文件](examples/record_showcase)。

分析已有记录时，可直接从任意本地目录导入，原始文件无需放进程序目录或仓库。

Release 另附[对应源码包](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/download/v0.1.0/Underline_RETLDC_0_1_0_Corresponding_Sources.zip)，包含第三方原始归档；校验值见 Release 正文。

## English quick start

Use Underline RETLDC to inspect rocket motor static fire records, compare experimental and imported theoretical curves, and analyze thrust curves alongside chamber pressure and temperature.

- **Import and calibration:** TR_F / TR_P / TR_T two-column logs, CSV / TSV / custom-delimited text and XLSX. Save column-mapping presets, configure calibration and display units, and retain original samples.
- **Experimental and theoretical curves:** overlay imported theory or simulation data on thrust, chamber-pressure and temperature plots. Shift curves with the slider or offset field, align test starts automatically, then fine-tune. Calculate available metrics separately; display shifts leave scientific timestamps and calculation intervals unchanged.
- **Test intervals:** detect candidates or drag boundaries to confirm start and end times. View the full record or focus on the selected active interval.
- **Spectrum analysis:** inspect interval FFT, optionally subtract the mean, and use linear or logarithmic X/Y axes to examine frequency components and local peaks.
- **Projects and exports:** save projects, settings and plot views. Export experimental CSV, formal curve PNG, TXT / JSON reports and ENG when required inputs are available. Unified exports use experimental data; the plot's context-menu Export can include reference overlays.
- **Interface:** Simplified Chinese / English, light / dark themes, and a separate Chinese / English report-language choice.

FFT uses linear interpolation for nonuniform clocks; long gaps limit spectral interpretation, and a peak alone does not establish resonance. The orange curve above is a solid rocket motor record; the dashed green curve is a smoothed synthetic reference derived from it, rather than an independent theoretical prediction. Screenshots are actual Qt offscreen renders. [View the alignment and FFT walkthrough](docs/Recorded_Data_Showcase.md#english-walkthrough) for sample processing details and calculation limits.

The current stable release is **v0.1.0 · 2026-10-15**. Download the [Windows portable ZIP](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/download/v0.1.0/Underline_RETLDC_0_1_0_Windows_Portable.zip), verify its SHA-256 against the [Release body](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/tag/v0.1.0), extract the whole folder and run `Underline_RETLDC.exe`; Python is not required.

Follow the [sample walkthrough](docs/Recorded_Data_Showcase.md#english-walkthrough) to save the TXT, reference CSV and project JSON in any writable folder, then open the prepared project and try alignment, separate calculations, FFT and export. [Sample files](examples/record_showcase) are available in the repository. Existing records can be imported directly from any local folder, without placing them in the application or repository directory.

The Release also provides the [corresponding sources ZIP](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/download/v0.1.0/Underline_RETLDC_0_1_0_Corresponding_Sources.zip), including original third-party archives. Checksums are in the Release body. The [release article](https://www.kechuang.org/t/91966) is in Chinese.

## 文档与开发 / Documentation and development

| 入口 / Link | 内容 / Contents |
|---|---|
| [使用手册 / User manual](README.txt) | 完整中文操作说明 / Full instructions in Chinese |
| [记录与叠图示例 / Recorded-data walkthrough](docs/Recorded_Data_Showcase.md) | 时间平移、FFT、独立计算、实验导出与数据说明 / Alignment, FFT, separate calculations, experimental exports and data notes |
| [极简合成例 / Minimal synthetic example](docs/Synthetic_Overlay_Example.md) | 两条短曲线与复现公式 / Two short curves and reproducible formulas |
| [来源与理论曲线 / Sources and theory curves](docs/Theoretical_Curves.md) | 来源、显示对齐和计算规则 / Source origins, display alignment and calculation rules |
| [数据格式 / Data formats](docs/Data_Formats.md) · [Plugin API v1](docs/Plugin_API.md) | 表格映射、工程格式与插件扩展 / Table mappings, project format and plugin extensions |
| [v0.1.0 更新说明 / Release notes](docs/Release_Notes_0_1_0.md) · [发布文章 / Release article (Chinese)](https://www.kechuang.org/t/91966) | 版本功能介绍 / Version overview |
| [GitHub Issues](https://github.com/aleistercrowleybeast666/Underline_RETLDC/issues) | 问题反馈，请附版本与复现步骤 / Report issues with the version and steps to reproduce |

源码运行需要 Python ≥ 3.11；已有 `.venv` 时直接复用，首次运行：
Running from source requires Python ≥ 3.11. Reuse an existing `.venv`; for a first setup:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe main.py
```

开发前阅读 [AGENTS.md](AGENTS.md) 与 [TARGETS.md](TARGETS.md)。原创代码采用 [Apache-2.0](LICENSE)，第三方许可见 [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)。
Before contributing, read AGENTS.md and TARGETS.md. Original code is licensed under Apache-2.0; third-party licenses are listed in THIRD_PARTY_NOTICES.txt.
