Underline RETLDC 使用说明
=========================

全称：Underline Rocket Engine Test Log Decode and Compute
用途：试车结束后，对已经记录好的火箭发动机试车日志进行解析、校准、处理、计算和导出。

当前版本主要处理推力数据。程序是离线软件，不负责点火、实时采集或发动机控制。


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
2. 选择“打开原始数据”。
3. 选择试车记录文件。
4. 选择解析器（Parser）。
   - 不确定时可使用自动识别。
   - 软件随附 TR_F；以后安装的其他 Parser 也会出现在同一列表中。
5. 点击解析，检查样本数、时间、数据警告等信息。
6. 选择校准方式（Calibration）。
   - 如果数据已经是工程量，选择“已经校准”。
   - 如果需要校准，选择相应校准模型并填写参数，或加载校准 JSON。
7. 进入推力分析。
8. 检查/选择燃烧区间。
9. 根据试车方式选择是否启用发动机自重变化补偿。
10. 检查修正后的推力曲线和计算结果。
11. 需要时导出 TXT、PNG、CSV、JSON 或 OpenRocket ENG。


三、工程文件要不要保存
--------------------

可以不保存工程。

如果只是临时分析一次：
打开原始数据 → 分析 → 直接导出 → 关闭程序即可。

如果希望下次继续：
选择“保存工程”。工程文件会记录：
- 原始文件引用和校验信息
- 解析器及其参数
- 校准模型及其参数
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

原始文件
  → Parser
  → Dataset / Raw Channels
  → Calibration Model
  → Calibrated Channels
  → Processor
  → Processed Channels
  → Analyzer
  → Analysis Result
  → Exporter

五类主要 Plugin API：
1. Parser：读取新日志格式
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
五种导出器，都位于根目录 plugins/，由同一个递归 Loader 发现。稳定 plugin_id 中的
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
- 稳定 ID 与显示文字分离。
- GUI 不复制科学算法。
- 普通扩展优先写插件，不修改 Core。
- 插件参数尽量通过 schema 自动生成 GUI。


十、高级：加入压强、温度、流量等新数据
----------------------------------

这类任务通常不再只是“增加一个两列 Parser”这么简单。

如果只是某种文件里多了一个已经能用现有 Dataset 表示的 Channel，可能只需要新增/修改 Parser，并给 Dataset 增加对应 quantity/unit Channel。

如果希望完整支持压强分析，例如：
- 静态燃烧室压力
- 动态燃烧压力
- 压强专用分析页面
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
