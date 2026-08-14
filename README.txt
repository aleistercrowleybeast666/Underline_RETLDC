Underline RETLDC 使用说明
=========================

英文全称：Underline Rocket Engine Test Log Decode and Compute
用途：试车结束后，对已经记录好的火箭发动机试车记录进行解析、校准、处理、计算和导出。

当前版本提供项目、推力分析、燃烧室压力、温度和数据浏览器工作区。程序是离线软件，
不负责点火、实时采集或发动机控制。


一、第一次使用
--------------

1. 安装 Python 3.11 或更高版本。
   Windows 用户安装 Python 时建议勾选“Add Python to PATH”。

2. 打开 Underline_RETLDC 工程文件夹。

3. 在文件夹空白处打开 PowerShell / Windows Terminal，第一次只需要执行：

   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -e .

   如果电脑没有 py 命令，可把第一行改为：

   python -m venv .venv

4. 安装完成后启动程序：

   python .\main.py

   main.py 会自动使用本工程的 .venv。

以后通常只需要执行最后一条启动命令，不需要重复安装环境。

如果提示找不到 .venv，请重新执行第 3 步。


二、最简单的使用流程
------------------

1. 启动程序。
2. 选择“打开原始数据”，可以一次添加一个或多个试车记录文件。
3. 多文件需要对齐时，填写各文件的“工程时间偏移”。
4. 选择解析器（Parser）。不确定时可使用自动识别；若几个解析器同样符合，按数据的
   真实物理意义选择一个推荐项。
5. 普通 CSV、TSV 或 XLSX 使用“快速导入”，只需把各列设为时间、推力、燃烧室压力、
   温度或其他，再点击“快速导入”。复杂格式才展开“高级映射”。
6. 导入后在“主通道”区域确认主要推力、主要燃烧室压力和所需温度通道。软件会给出
   建议，但最终选择以这里为准。
7. 每个新通道默认显示“已经校准”。这只表示软件不额外变换数字，不代表软件证明了
   传感器标定准确。
8. 如果数据仍是 ADC/raw/count，为该通道选择正确校准器并填写参数，或加载校准 JSON。
9. 点击“进入分析”进入推力分析；燃烧室压力和温度也可在各自工作区查看。
10. 软件使用已确认的主通道检测试车区间：存在主要燃烧室压力时优先使用室压，否则使用
    主要推力。自动结果只是建议，用户保留最终决定权。
    自动识别后，可在推力或燃烧室压力页面拖动、输入同一套试车前/试车/试车后区间；
    两个页面和工程状态会立即同步。
11. 根据试车方式选择是否启用发动机自重变化补偿，并检查假设基线提示。
12. 检查修正后的曲线和计算结果；需要时导出 TXT、PNG、CSV、JSON 或 OpenRocket ENG。

单位只需要这样理解：

数据单位：文件里的数字本来是什么单位。修改它是在纠正数据解释，不改变原数字。
显示单位：软件画图时想显示成什么单位。软件会换算显示值，不改变原数字。

例如 Data Unit 为 Pa、Display Unit 为 MPa 时，文件中的 1,000,000 Pa 会显示为 1 MPa。
温度 K 与 °C 也会正确处理 273.15 的偏移，不是简单修改文字。

“设置”中的单位显示模式有两种：
- 工程单位（默认）：使用 N、MPa、°C、mm 等便于阅读的工程单位；
- SI + 科学计数法：使用 N、Pa、K、m 等规范 SI 单位，并以科学计数法显示数值。

这两种模式只改变图、坐标轴和统计表的显示，不修改原始数值、数据单位、校准状态或
正式导出数据的单位定义。

如果推力通道仍是 raw/count/ADC，可以查看、绘图和分段，也能看到相对峰值；但软件不会
伪造以 N、N·s、s 为单位的峰值推力、总冲和比冲，也不会生成 OpenRocket ENG。


三、工程文件要不要保存
--------------------

可以不保存工程。

如果只是临时分析一次：
打开原始数据 → 分析 → 直接导出 → 关闭程序即可。

如果希望下次继续：
选择“保存工程”。工程文件会记录：
- 原始文件引用和校验信息
- 多个 Source、Stream 和工程时间偏移
- 解析器及其参数
- 每个通道的物理量、数据单位、单位来源、显示单位覆盖、校准模型及参数
- 处理/补偿配置
- 选择的工作区间
- 分析和导出设置

下次直接选择“打开工程”即可恢复并重新计算。

如果原始数据文件被移动，程序会要求重新定位，并校验文件是否还是原来的数据。

同一已保存工程重复导出时，默认覆盖该工程导出目录中的同名结果，不自动生成 (1)、final 等副本。


四、语言和外观
------------

程序支持：
- 简体中文
- English

可在窗口顶部切换。

程序支持浅色模式和深色模式；选择会保存，下次启动继续使用。


五、怎样新增一个“解析器”
----------------------

解析器负责回答：
“这个原始记录文件怎样读成 Underline_RETLDC 的统一数据？”

解析器不负责校准、滤波、总冲、比冲或导出。

官方参考插件位于：

   plugins/parsers/tr_f/

你自己的 Parser 放在：

   plugins/parsers/<插件文件夹>/

官方插件和用户插件使用完全相同的 plugin.json、plugin.py、Plugin API、Loader、
SchemaForm 和中英文资源；TR_F 只是软件默认附带的 Parser，不是 Core 特例。

使用 AI 扩展最方便：
1. 打开根目录“新增解析器_PROMPT.txt”。
2. 把全文复制给 AI。
3. 在末尾“【本次具体要求】”写入文件样本、字段意义、时间单位、分隔方式、
   自动识别依据和坏数据处理要求。
4. AI 有 Agent 或仓库编辑能力时，让它直接在当前工程中创建插件并运行测试。
5. AI 无法访问工程时，要求它生成一个可直接安装的插件 ZIP。
6. 把 ZIP 解压到 plugins/parsers/。解压后应直接得到：

   plugins/parsers/<插件文件夹>/plugin.json
   plugins/parsers/<插件文件夹>/plugin.py
   plugins/parsers/<插件文件夹>/i18n/zh_CN.json
   plugins/parsers/<插件文件夹>/i18n/en_US.json

   ZIP 内不要再套一层 Underline_RETLDC/plugins，也不要把文件散落在 parsers/ 中。
7. 重启软件，或打开“工具 → 插件”后刷新。新 Parser 应自动出现在解析器下拉框。

了解 Python 的用户也可直接以 plugins/parsers/tr_f/ 为模板编写。普通新 Parser
原则上不需要修改 Core 或主 GUI；如果需求无法由公开 Plugin API 表达，应使用能读取
完整仓库的 Coding Agent 先扩展平台，而不是让 ZIP 覆盖 Core。


六、怎样新增一个“校准模型”
------------------------

校准模型负责：
“把 Parser 得到的传感器数值转换成工程量。”

官方参考插件位于：

   plugins/calibrations/linear/
   plugins/calibrations/identity/

你自己的 Calibration 放在：

   plugins/calibrations/<插件文件夹>/

使用 AI 的步骤与 Parser 相同：
1. 把“新增校准配置_PROMPT.txt”全文复制给 AI。
2. 在“【本次具体要求】”写明校准公式、参数、范围、输入意义、输出物理量和单位。
3. 有 Agent 时让 AI 直接修改当前仓库并测试。
4. 无 Agent 时让 AI 生成插件 ZIP，再解压到 plugins/calibrations/。
5. 最终应形成 plugins/calibrations/<插件文件夹>/plugin.json 和 plugin.py；重启或刷新后，
   新模型应自动出现在校准下拉框。

校准模型只负责数值映射，不承担解析、baseline、自重变化补偿、滤波、分析或导出。


七、插件放在哪里
--------------

源码版和便携版随软件提供的插件统一位于：

   plugins/
   ├─ parsers/
   ├─ calibrations/
   ├─ processors/
   ├─ analyzers/
   └─ exporters/

插件类型以 plugin.json 的 plugin_type 为准，分类文件夹主要帮助人阅读。

软件还会读取当前 Windows 用户目录下的：

   %APPDATA%\Underline_RETLDC\plugins\

“插件管理”安装文件夹时优先使用这个可写目录，因此安装版通常不需要管理员权限。
源码/便携用户也可手工把可信插件文件夹放入工程根目录 plugins/ 的对应类别。
无论来源显示为 Bundled 还是 User，它们都进入同一个 Registry，使用同一套 API。


八、插件安全
----------

plugins/ 中的 Python 插件属于“可执行代码”，不是沙箱。

只安装或运行你信任来源的插件。

坏插件通常会被程序隔离并显示加载错误，但恶意 Python 插件本身仍可能拥有当前用户权限。


九、高级：给了解编程的用户
----------------------

Underline_RETLDC 的核心数据链：

Source（只读原始文件）
  → Parser
  → Stream（本地时间 + 工程时间偏移）
  → Channel（Quantity + Data Unit + Raw Values）
  → Calibration Model
  → Calibrated Channels
  → 可选的 Display Unit 换算
  → Processor
  → Processed Channels
  → Analyzer
  → Analysis Result
  → Exporter

五类主要 Plugin API：
1. Parser：读取新的记录格式
2. Calibration Model：新增校准数学模型
3. Processor：补偿、滤波、重采样等数据处理
4. Analyzer：计算新的物理/统计结果
5. Exporter：输出新的文件格式

平台边界可以概括为：

Platform Core
  → Plugin API
  → plugins/
     ├─ parsers
     ├─ calibrations
     ├─ processors
     ├─ analyzers
     └─ exporters

所有具体格式和算法，包括随软件提供的 TR_F、Identity、Linear、自重补偿、推力分析和
各类导出器，都位于根目录 plugins/，由同一个递归 Loader 发现。稳定 plugin_id 中的
“builtin”只表示官方随附，不表示源码仍在 src/underline_retldc/builtin/。

详细接口见：
- docs/Architecture.md
- docs/Plugin_API.md
- docs/Data_Formats.md
- docs/Calibration.md
- docs/Analysis.md
- docs/I18N.md

原则：
- 原始数据不可破坏。
- Unit 和 Calibration 完全独立；所有新通道默认 Identity。
- Parser 明确知道单位时必须保留；已知物理量缺单位时平台使用规范 SI。
- 数据单位解释与显示单位换算必须分开。
- 稳定 ID 与显示文字分离。
- GUI 不复制科学算法。
- 普通扩展优先写插件，不修改 Core。
- 插件参数尽量通过 schema 自动生成 GUI。


十、高级：加入压强、温度、流量等新数据
----------------------------------

这类任务通常不再只是“增加一个两列 Parser”这么简单。

如果只是某种文件里多了一个已经能用现有 Dataset 表示的 Channel，可能只需要新增/修改 Parser，并给 Dataset 增加对应 quantity/unit Channel。

当前已提供燃烧室压力、温度和通用数据浏览工作区；如果希望继续加入完整专用分析，例如：
- 静态燃烧室压力
- 动态燃烧压力
- 更多压强统计/频域分析
- 多通道同步
- 压强与推力联合分析
- 新图表和新报告

通常需要同时检查：
- Dataset/Channel 语义
- Parser
- Calibration
- Processor
- Analyzer
- Exporter
- GUI workspace
- Project 持久化
- i18n
- 测试和 docs

这种修改建议使用 Codex 等较强的代码代理，并要求它先完整阅读 AGENTS.md、TARGETS.md 和 docs/，不要让能力较弱的 AI 直接在 MainWindow 中堆 if/else。

若扩展需求超出当前 Plugin API，应该先扩展通用架构和文档，再实现具体功能，而不是给某一个插件做隐藏特例。


十一、开发者常用命令
----------------

启动：
python .\main.py

测试：
.\.venv\Scripts\python.exe -m pytest

代码检查：
.\.venv\Scripts\python.exe -m ruff check .

重新安装当前工程依赖/可编辑包：
.\.venv\Scripts\python.exe -m pip install -e .


十二、遇到问题先看哪里
--------------------

程序使用问题：README.txt
项目目标：TARGETS.md
开发约束：AGENTS.md
总体架构：docs/Architecture.md
插件接口：docs/Plugin_API.md
数据格式：docs/Data_Formats.md
校准：docs/Calibration.md
分析公式：docs/Analysis.md
语言：docs/I18N.md

不要修改 .venv 中的源码来“修程序”；真正源码位于 src/underline_retldc/。


十三、生成可分发的 Windows 文件夹版
--------------------------------

需要制作无需安装 Python 的 Windows 版本时，双击根目录：

   打包_文件夹版.bat

脚本只使用当前工程的 .venv；如果其中没有 PyInstaller，会先自动安装。随后使用文件夹
模式构建并自动执行浅色、深色两次启动检查，同时确认所有随包插件均可载入。成功后的
发布位置是：

   dist\Underline_RETLDC_0_1_0\

主程序是：

   dist\Underline_RETLDC_0_1_0\Underline_RETLDC_0_1_0.exe

发布时必须复制或压缩整个 Underline_RETLDC_0_1_0 文件夹，不能只拿走 EXE。
`_internal` 中是运行依赖，`plugins` 中是随软件发布的标准插件，二者都不能删除。
发布文件夹还包含 README、插件生成 Prompt、技术文档和示例数据。

重新打包会替换同名发布目录中的旧构建产物；不会改动源码、原始试车文件或用户的
AppData 插件目录。打包脚本和生成的 EXE 仅面向 Windows。

十四、普通 CSV / TSV / XLSX：优先使用通用表格解析
---------------------------------------------

大多数普通二维表格不需要开发新的 Parser Plugin。只要数据能够表示为“每行一个采样、每列一个字段”，
应优先使用：

   Generic CSV / TSV（内部 ID：builtin.parser.generic_delimited）
   Generic XLSX（内部 ID：builtin.parser.generic_xlsx）

普通用户操作步骤：

1. 在“工程”工作区添加 CSV、TSV 或 XLSX 文件。
2. 选择 Generic CSV / TSV 或 Generic XLSX；也可以先让软件自动推荐解析器。
3. XLSX 选择工作表；分隔文本可以使用自动分隔符/编码，也可以手工指定。
4. 设置表头行、数据开始行和可选的数据结束行。
5. 明确指定时间来源：文件中的列、固定采样率或固定采样周期。
6. 在快速映射中把每一列设为 Time、Thrust、Chamber Pressure、Temperature 或 Other。
7. 检查数据单位，点击“快速导入”，然后确认主通道绑定。
8. 相同格式以后还会使用时，点击“保存预设”；也可以导入/导出纯 JSON 预设。

Other 与 Ignore 不同：Other 会作为辅助通道导入并随工程保存，但默认不进入专用工作区、
试车区间检测或科学分析；Ignore 只在高级映射中提供，表示完全不导入该列。稳定 Channel ID、
Quantity、Semantic Role 和 Metadata 等专业选项也都在默认折叠的“高级映射”中。

软件绝不会在未指定时间来源时默默使用 1 Hz。存在真实时间列时会保留真实时间戳，不会把它重采样成
均匀时间。某列中间缺少单元格时，默认用 NaN 保持所有通道的行和时间对齐。

简单 CSV 示例：

   Time,P,F
   0,0.1,10
   0.1,0.2,20

可以配置为：

   A → Time / s
   B → Chamber Pressure / MPa
   C → Thrust / N

列标题叫什么并不决定数据含义。即使标题改成 T0、CH_A、CH_B，只要映射仍指定 A 为时间、B 为
燃烧室压力、C 为推力，就可以正确解析。自动映射只负责预填建议，用户可以修改；真正执行的是保存的
Column Mapping。

TR_F、TR_P 和 TR_T 都是“时间 + 一个原始数值”的两列文本，单凭数字形状无法可靠判断
第二列是推力、压力还是温度。因此自动识别会把分数接近的候选项列出来，由用户确认：

   TR_F → 时间 / 原始推力
   TR_P → 时间 / 原始燃烧室压力
   TR_T → 时间 / 原始温度

确认的含义只决定通道的物理类别；原始数值仍使用 raw 单位，必要时还要应用真实校准。

预设与工程文件的区别：

- Preset 是可复用的格式模板，Windows 用户预设保存在
  %APPDATA%\Underline_RETLDC\presets\tabular\，主要通过软件的“导入预设/导出预设”操作。
- Project 保存当前这个 Source 最终实际使用的完整 Mapping。以后修改同名 Preset，不会改变旧工程。
- Preset 是纯 JSON 配置，不执行 Python，适合普通表格格式。
- Plugin 是可执行 Python 代码，只能安装可信来源。

以下变化通常只需要 Generic Tabular + Preset：

- CSV/XLSX 列位置变化；
- 表头文字变化；
- 数据单位变化；
- 文件前面增加说明行；
- 某些列需要忽略。

只有下列格式无法表示为普通二维表格时，才考虑使用“新增解析器_PROMPT.txt”开发 Parser Plugin：

- 二进制或压缩格式；
- 专有通信协议；
- 带特殊校验/解码；
- 多个复杂数据块；
- 多个工作表之间存在必须联合解析的专有关系。

没有 Agent 的 AI 如果面对普通 CSV/TSV/XLSX，应优先生成：

   <format_name>_tabular_preset.json

然后由用户在表格映射区域点击“导入预设”，而不是生成可执行插件 ZIP。
