Underline RETLDC 0.1.0
======================
火箭发动机试车记录的离线解析、校准、分析与导出工具。
Rocket Engine Test Log Decode and Compute.

Windows 便携包无需安装 Python：完整解压后运行 Underline_RETLDC.exe，保留整个文件夹。
v0.1.0 已于 2026-10-15 发布，Windows 便携包与对应源码包可在 GitHub Release 下载。
快速导航与入门示例见 README.md；以下为完整操作手册。

版本与下载：https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases
代码与文档：https://github.com/aleistercrowleybeast666/Underline_RETLDC
问题反馈：https://github.com/aleistercrowleybeast666/Underline_RETLDC/issues

正式发布：https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/tag/v0.1.0
该版本有两个附件，正式文件名：
  Underline_RETLDC_0_1_0_Windows_Portable.zip
  Underline_RETLDC_0_1_0_Corresponding_Sources.zip
SHA-256 列在 Release 正文中；该版本没有独立的 SHA256SUMS.txt 下载附件。


一、快速开始（Windows 便携包）
----------------------------
1. 下载对应版本的 Windows Portable ZIP，对照 Release 正文核对 SHA-256。
   PowerShell 示例：
   Get-FileHash .\Underline_RETLDC_0_1_0_Windows_Portable.zip -Algorithm SHA256
2. 完整解压 ZIP，在 Underline_RETLDC 文件夹中双击 Underline_RETLDC.exe。
   建议使用有写入权限的位置，例如 D:\Tools\Underline_RETLDC；无需管理员权限。
3. 在“工程”页导入数据，确认来源类型为“实验数据”或“理论数据”。原文件始终只读。
4. 核对解析结果、时间来源、物理量和单位，确认实验主通道；需要时设置校准。
5. 在推力或燃烧室压力页自动识别试车区间，也可拖动边界或输入起止时刻调整。
   温度与数据浏览器使用同一工程区间。
6. 填写必要发动机参数，点击顶部“计算分析结果”，核对结果后导出。
   工程可在任意阶段保存；临时分析也可直接导出，无须先保存工程。

软件用于已经记录的数据，不负责点火、实时采集或发动机控制。


二、导入、单位和计算
------------------
实验与理论使用同一套已有 Parser 和 Mapping Preset，不限制数据来自哪种仿真软件。
普通 CSV、TSV、分隔文本及 XLSX 使用通用表格解析器和明确的列映射。自动识别在本地
确定性运行；未知数值列默认保留为“其他”。识别失败或需要修改时展开高级映射。
每个来源保存自己的有效映射，重开工程不会重新识别或追随外部预设变化。

两列原始 TXT 若同时兼容 TR_F、TR_P、TR_T，需要明确选择推力、室压或温度含义。
时间必须来自真实时间列、明确采样率或采样周期，不默认猜测 1 Hz。
多来源可分别保留采样间隔和科学工程时间偏移，不为共用试车区间而重采样。

数据单位定义原数字的物理含义；显示单位只换算图和表中的值。例如 1,000,000 Pa 可
显示为 1 MPa，K/°C 会处理零点偏移。工程单位和 SI 科学计数显示均不改变原始数组、
校准状态或正式导出单位。单位换算不能代替传感器校准。

新通道默认 Identity（已经校准/不额外变换），不代表软件证明了传感器标定准确。
raw/count/ADC 需要合适的校准及物理单位，才能用于 SI 总冲、比冲或 ENG。
新工程推力修正默认“不启用”；推力极性独立生效。自重/基线补偿可按安装方式和
分析需要选择。校准、极性与补偿属于不同阶段。

实验推力与室压编辑同一套工程 PRE/ACTIVE_TEST/POST 区间，温度读取该区间。
自动识别的区间可手动调整。总冲使用实际时间戳作梯形积分；比冲只用
推进剂质量，质量缺失或无效时比冲不可用，其他有足够输入的指标仍可计算。
发动机总质量不能替代推进剂质量，基线推导的等效质量变化不等于精确推进剂消耗。


三、理论曲线与独立结果
--------------------
来源明确标记“实验/理论”，旧工程默认实验；它与 raw/calibrated/processed 通道阶段
分开保存。同一个物理文件可分别作为两种来源导入，独立 Source ID 防止同名通道混用。

理论曲线直接叠加在已有推力、室压、温度及适用的数据浏览器时间曲线上，以理论图例、
颜色和虚线区分。可选择曲线和可见性；叠加前校验物理量及物理单位，原采样点和 NaN
缺口保持原样。理论来源不会自动成为实验主通道。

正负“显示时间平移”及滑条在各时间曲线页共享。“对齐试车起点”使用当前实验起点
（包含人工修改）和理论独立检测的起点，重复点击不累计偏移，之后仍可微调。
“恢复原时序”恢复原显示时间。显示平移不修改 Stream 科学时钟、积分区间或文件。
来源类型、选择/可见性、平移、图轴范围及自动范围状态随工程保存、重开恢复。

各页原有结果区以一个“指标来源”选择器查看实验或理论，顶部统一计算动作复用已有
计算器。两种来源分别保存通道引用、科学时间区间、处理配置和完成状态；新理论来源
计算默认使用完整记录，草稿不会在重开时自动推进为已完成。

理论使用工程中的实验发动机物理参数，包括推进剂质量、总质量、直径及长度；不再
维护一套重复的理论物理输入。缺失参数保持不可用，不填零。新理论计算采用工程量
通道、+1 方向、不启用修正，不继承实验分段或自重补偿；旧独立配置保留读取兼容。
实验和理论的计算区间均采用科学时间，不采用显示对齐坐标。

理论导入、删除、校准、隐藏或对齐不改变已完成的实验主流程结果及正式导出就绪状态。
本版不提供残差、MAE/RMSE、自动拟合、大模型分析或发动机优化。
细节：docs/Theoretical_Curves.md。


四、工作区间、FFT 和图表导出
---------------------------
图表右键“变换”中的“仅分析工作区间”在所有时间曲线页同步。开启后，时域只显示
该试车区间，FFT、去均值及既有派生变换也先选取区间内原点；关闭即可恢复全段。
实验使用工程 ACTIVE_TEST，理论使用自身独立检测区间；该显示选区不重写科学计算
配置。FFT 时隐藏时间区间标记，退出后恢复。选择和 FFT/对数状态随工程保存。

FFT 沿用 pyqtgraph 0.14 原有行为：非等间隔时间先按首末实测时长线性插值为同样 N
个等间隔点，再显示 abs(rFFT(y)/N)。横轴为 Hz，纵轴保留输入显示单位，标为
“FFT 模值 |rFFT|/N”；不是 PSD/功率，也没有补乘 2 的单边振幅归一化。
去均值选中时，沿用先减原选中点均值、再插值和 FFT 的顺序，DC 可能有插值残差。

非有限数值、重复/倒序时钟和不足两点仍拒绝。有限但间隔较大的空档允许沿用原插值
出图，并在图下方一行提示频谱局限：空档内的直线不是实测数据，插值可能衰减或改变
高频内容。优先检查连续工作区间。提示可悬停或展开，不遮挡曲线，也不修改原始数组。

顶部统一 CSV、TXT/JSON 报告和正式 PNG 继续使用实验主流程，不随理论指标选择改变。
室压正式 PNG 的样本及 X 范围均只覆盖 ACTIVE_TEST；正式推力图保留 0 N 参考。
图表右键 Export 是独立的当前图路径：PNG/SVG 可显示理论、平移和当前 FFT；绘图 CSV
保留完整图项输入的显示单位/平移，不包含 FFT、去均值、对数、降采样或本显示区间裁剪。
绘图 CSV 不等同于原始文件或顶部正式 CSV。导出不要求事先保存工程。

导出窗口每次新打开选中全部当前可用格式；窗口保持打开时，手动取消不会因刷新或
换语言而恢复。不可用项禁用且不勾选。输出语言默认跟随界面，正式文件使用 _ZH/_EN
固定名称（ENG 无语言后缀）；重复导出覆盖同名结果。
细节：docs/Plot_Analysis_0_1_0.md、docs/FFT_Restored_Acceptance_0_1_0.md。


五、工程、界面与插件
------------------
工程记录来源引用及 SHA-256、解析/校准/处理配置、主通道、区间、结果状态和视图。
重开时核验原文件；移动文件需重新定位并通过同一哈希检查，不接受不同内容混入。
已完成来源结果按已保存有效配置恢复，未完成阶段保持草稿。显示设置不改变科学数组。

界面支持简体中文/English、浅色/深色、工程单位/SI 科学计数。顶部与设置中的主题、
语言保持同步。导出输出语言可独立固定为中文或英文。

“工具 → 插件 → 安装插件”接受文件夹或 ZIP。安装器按 plugin.json 类型递归识别，
优先使用可写程序 plugins/，权限不足时逐插件回退到用户插件目录；同 ID 替换仍在
原位置完成。只有 Registry 实际加载成功才报告成功。外部 Python 插件会执行代码，
请只安装可信来源；来源标签不代表安全背书，插件不在沙箱内。
Plugin API v1：docs/Plugin_API.md；扩展指引：新增解析器_PROMPT.txt、新增校准配置_PROMPT.txt。


六、许可与对应源码
----------------
项目原创代码采用标准 Apache License 2.0，完整条款见 LICENSE。第三方组件及保留
上游许可的代码仍按各自条款提供；例如 pyqtgraph/SVG 适配保留 MIT，Qt/PySide/Shiboken
仍适用其相应许可。第三方原文与说明见 THIRD_PARTY_NOTICES.txt 和 docs/third_party/。

与便携包同时提供 Corresponding_Sources ZIP：匹配标签的应用源码、构建/重组工具、
精确依赖版本及五份 Qt/PySide 6.11.1 原始归档，另含 Mesa 11.2.2 固定提交源码和软件
OpenGL/LLVM 许可材料。六份上游原始压缩归档合计 85,322,364 字节，不展开 SDK。
内部清单逐成员记录哈希，Release 正文提供两个交付 ZIP 的 SHA-256。GitHub 自动生成的应用
Source code ZIP 不包含这些第三方归档，不能代替该对应源码包。

Qt/PySide 的 Python 绑定重组途径已实际运行验证；原生 C++ 库未重新编译。源码提供
方式、库替换步骤和证据见 docs/Qt_Corresponding_Source_0_1_0.md、
docs/Qt_Library_Replacement_0_1_0.md、docs/License_Delivery_Closeout_0_1_0.md。


七、从源码运行与验证（开发者）
----------------------------
需要 Python >=3.11。已有 .venv 时直接复用；首次没有环境时执行：
  py -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -e ".[dev,packaging]"
启动：
  .\.venv\Scripts\python.exe main.py
验证：
  .\.venv\Scripts\python.exe -m pytest
  .\.venv\Scripts\python.exe -m ruff check .

v0.1.0 发布构建使用 Python 3.14.0、Qt/PySide6 6.11.1、pyqtgraph 0.14.0、NumPy 2.5.2、
SciPy 1.18.0、PyInstaller 6.22.0。来源包 BUILD_DEPENDENCIES.json 保存实际版本。
打包.bat 在 pytest 或 Ruff 失败时停止，不继续 PyInstaller。

发布前验证记录：348 项 pytest、57 项针对性检查、源码/冻结 GUI 各 244 项、中英文启动及
仓库外解压启动通过；真实 TEST_SD 与其合成参考的全段/工作区间 FFT 已逐点比对。
这些验证对应已记录的数据与软件路径，不构成传感器、发动机或现场硬件认证。
Windows IME 人工专项验收未运行。完整边界见 docs/FFT_Restored_Acceptance_0_1_0.md。

发布后展示复核的全量 pytest 遇到 Windows 原生堆异常 0xc0000374，
没有完整汇总；相关理论工作流单项隔离重跑 1 passed，根因未定。单项通过不能作为
该次全量通过，也不替代上述发布前记录。


English quick start
-------------------
Underline RETLDC is an offline rocket-engine test-log decoder and calculator.
For Windows, download the published v0.1.0 Portable ZIP from Releases, verify its
SHA-256 against the release body, extract the complete folder and run
Underline_RETLDC.exe. Python is not required for the portable application.
There is no separate SHA256SUMS.txt attachment for this release.

Experimental and theoretical sources share the existing parsers and mappings.
Theory overlays and its results live in the existing workspaces. Display alignment
never changes scientific timestamps; engine physical parameters come from the
Project model. Formal unified exports continue to use experimental primary inputs.
FFT retains linear interpolation for nonuniform clocks and displays |rFFT|/N,
not PSD or doubled one-sided amplitude. Inspect gap warnings and prefer a continuous
active-test interval. Source files and raw arrays remain unchanged.

Application code is Apache-2.0; third-party licenses remain in effect. Distribute the
matching Corresponding_Sources ZIP and checksums with the portable archive.
The repository/tag push does not by itself create a GitHub Release or upload assets.
