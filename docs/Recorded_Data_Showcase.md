# 曲线对齐、FFT 与导出 / Recorded-data walkthrough

[返回首页](../README.md) · [使用手册](../README.txt) · [发布文章](https://www.kechuang.org/t/91966)

用一份用户提供的实验记录，走一遍导入、时间平移、分别计算、FFT 和导出。橙线为实验记录，绿虚线为用于演示的平滑模拟参考。

## 三步体验

1. 下载并完整解压 [v0.1.0 Windows 便携版](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/tag/v0.1.0)。
2. 将下表三份必需文件保存在同一目录。在 GitHub 文件页点击 **Download raw file**，保留文件名。
3. **从该目录启动应用**，再打开 `record_showcase.retldc.json`，进入“推力”。

| 文件 | 内容 |
|---|---|
| [TEST_SD(1).TXT](../examples/record_showcase/TEST_SD%281%29.TXT) | 必需；原始记录，18180 点 |
| [synthetic_smooth_reference.csv](../examples/record_showcase/synthetic_smooth_reference.csv) | 必需；平滑模拟参考 |
| [record_showcase.retldc.json](../examples/record_showcase/record_showcase.retldc.json) | 必需；已配置的工程 |
| [线性换算配置](../examples/record_showcase/peak_estimate.calibration.json) · [参考生成脚本](../examples/record_showcase/generate_reference.py) | 可选；复现本例的数据处理 |

例如在 PowerShell 中启动，替换为自己的目录：

```powershell
Set-Location 'D:\MyExamples\record_showcase'
& 'D:\Tools\Underline_RETLDC\Underline_RETLDC.exe'
```

v0.1.0 按启动工作目录查找非主来源的相对路径，因此需要上面的启动方式。源码用户可在示例目录用仓库已有 venv 执行仓库 `main.py`。

## 移动时间轴与对齐曲线

**平移前：** 显示时间偏移为 `0 s`，两条曲线在横轴上错开。

![平移前，偏移输入框为0秒，滑动条和自动对齐按钮均可见](assets/record-before-alignment.png)

有三种调整方式：

- **拖动滑动条**：移动参考曲线，快速比较峰值位置和曲线形状。
- **输入偏移秒数**：精确设置平移量，负值向左、正值向右。
- **对齐试车起点**：按当前实验起点和参考数据检测到的起点自动对齐，随后仍可微调。

本例自动对齐得到 `-1.631973 s`（[自动对齐截图](assets/record-auto-alignment.png)）。再拖动滑动条或在输入框填入 `-2 s`，得到下图。点击“恢复原时序”可清除显示平移。

![自动对齐后再手动微调为-2秒，曲线移动后与实验记录叠加](assets/record-overlay-estimate.png)

平移只改变图上的位置，原始时间和计算区间不变。重复点击自动对齐不会累加偏移。

## 选择试车区间，分别计算结果

试车区间可自动识别，也可拖动两侧边界或输入起止时刻调整。本工程选用 `[152.50,154.80] s`；切换“仅分析工作区间”即可集中查看这一段。

在结果区选择“实验”或“理论”，点击同一个顶部“计算分析结果”按钮。发动机物理参数在工程中填写一次，两类来源分别计算。[查看参考来源的结果表](assets/record-reference-metrics.png)。

| 指标 | 实验记录 | 模拟参考 |
|---|---:|---:|
| 区间时长 / s | 2.30 | 2.30 |
| 峰值 / N | 919.73 | 894.915307 |
| 总冲 / N·s | 1545.896136 | 1493.648280 |
| 比冲 | 不可用 | 不可用 |

本例未提供推进剂质量，所以不显示比冲。数据换算与参考生成方法见末尾说明。

## FFT：查看频率成分和局部峰值

在图表菜单打开 FFT，查看选定区间中的频率成分。X、Y 轴都可以切换对数坐标，让宽频段中强弱不同的成分和局部峰值更容易看清。

下图使用实验记录的工作区间，开启“去均值”和 X/Y 双对数：横轴为频率 **Hz**，纵轴为 FFT 模值，当前推力通道的单位为 **N**。对数视图只显示正频率和正模值，不包含 0。

![实验工作区间的FFT双对数图，横轴频率Hz、纵轴FFT模值N](assets/record-fft-loglog.png)

也可切回[线性坐标视图](assets/record-interval-fft.png)，或关闭 FFT 回到时域曲线。

## 导出实验结果

顶部“导出”可输出实验 CSV、正式曲线 PNG 和报告。统一导出使用实验主流程；保存包含参考曲线的当前叠图，可用图表右键 Export。

![实验CSV和正式PNG导出选项](assets/record-export-options.png)

本例实际导出的 CSV 含 213 个区间内样本，时间以 `152.50 s` 为零点；首个样本在约 `0.009841 s`。即使结果区选中参考来源，正式导出也仍对应实验记录。

## 数据说明

记录由用户提供，第一列为秒，第二列为原始值。工程使用线性配置 **`K=0.49 N/raw`、`B=0`、极性 `+1`**；比例来自用户提供的约 `919.7 N` 峰值与原始峰值 `1877` 的对应关系，不是设备标定记录。[查看换算配置界面](assets/record-calibration-estimate.png)。

未扣除静止偏置，也未启用自重变化修正。PRE `[145,151] s` 的中位数为 `34 raw`，POST `[160,170] s` 为 `19 raw`，这些偏置仍留在曲线和积分中。原始文件、实验抖动和完整时间记录均保留。

模拟参考对一个新数组做 **31 点中值滤波 → 高斯平滑（sigma=20 点，truncate=4，nearest 边界）→ 乘上述比例**，并将时间列加 `2 s`，输出六位小数。它由记录趋势生成，用于演示叠图，不是独立物理模型的理论预测。生成脚本可用仓库已有 NumPy/SciPy 环境重建，文件行尾固定以保持哈希一致。

实验计算区间为 `[152.50,154.80] s`，参考的独立科学区间为 `[154.50,156.80] s`；显示平移不改这两个区间。新建参考来源默认使用完整记录，手动重建时应留意计算区间。

| 文件 | SHA-256 |
|---|---|
| 原始 TXT | `7325935683d8380681a804c338b8fe8ebbe1539d5dc3211cc55743303c038e8f` |
| 模拟参考 CSV | `f51da844814ad9562415522a3fce113d3098af742220ee4afcf8ed7e73140a27` |

FFT 显示 `abs(rFFT(y)/N)` 模值，非 PSD；非等间隔时钟出图沿用线性插值。频谱峰值提供观察线索，其物理原因需结合工况判断。截图为 v0.1.0 真实 Qt 中文界面离屏渲染，目前没有视频；ENG → OpenRocket 导入演示尚未验证。

## English walkthrough

Save the TXT, reference CSV and project JSON together. Launch v0.1.0 with that folder as the working directory, open the project, then use the slider or offset field to shift the reference curve. Align Test Starts finds the two starts automatically; you can fine-tune afterwards.

Detect the test interval or drag its boundaries, switch metric sources and Calculate, inspect FFT with linear or logarithmic axes, then export experimental results. The green curve is a smooth synthetic reference for this demonstration. Processing settings and source hashes are recorded above; screenshots are actual Qt offscreen renders.
