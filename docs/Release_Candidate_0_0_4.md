# Underline RETLDC 0.0.4 发布候选核对

## 变更与兼容性

- 新 Session / 新工程 / 缺省 processor 字段：推力修正默认 None；极性独立有效。
- 显式保存的 vertical_linear_baseline 继续恢复；插件 ID、API v1、工程 schema 不变。
- 新 Generic CSV/TSV/XLSX 导入会真正复制并应用通过校验的高匹配预设。
- 解析器 ID/版本、工作表、表头/数据起始行、完整列索引、单位和真实时间必须兼容。
  每个表头规范化名称的相似度至少 0.95，以最弱表头为分数，领先第二名至少 0.08；
  低于阈值的第二候选仍参与分差检查。固定结束行预设不自动应用，避免裁掉新记录。
- 配置在有界预览中通过通用映射引擎校验，时间必须有限且严格递增。失败或近似并列
  时回退普通自动映射。手动编辑优先；保存工程持有独立 effective mapping，重开不检测。
- 自动应用名称和最终映射支持中英文切换；重开时重复自动预览不再弹出任务冲突信息框。
- PRODUCT_NAME 为 Underline RETLDC，窗口标题为 Underline RETLDC — 0.0.4。
  内部包名、仓库、EXE 名称、设置和插件路径不改；版本仍是 0.0.4。

## 工作区布局

| 页面 | 左栏顺序 |
| --- | --- |
| 推力 | 主要通道 → 显示设置 → 试车区间 → 推力极性 → 推力修正 → 基线状态 |
| 室压 | 主要通道 → 显示设置 → 试车区间 → 参考压力 |
| 温度 | 主要通道 → 显示设置（含温度曲线开关）→ 只读试车区间 |

保留上轮已完成的统一结果/诊断面板及边距、2:1 伸展比例、计算按钮文案和显示区按钮顺序。
温度曲线开关保留在 Display 内，不再添加重复专用组。三栏禁止折叠到零，受限左栏滚动。
室压不再重复显示单位行；温度单通道结果优先显示指标名，多通道才附加通道身份。
三页指标和值都提供完整悬停提示。表格保持共同的行高策略。

## 数值语义

- Peak Thrust / Pressure 仍取最大值，没有为显示零线插入或修改源样本。
- Thrust Total Impulse 继续按真实时间戳梯形积分，Average Thrust 原本已为积分/试车区间时长。
- Pressure Average 从算术平均改为真实时间积分/选定区间时长。全记录平均以首末有限样本
  时差为分母；不足两个严格有序有限样本时平均值不可用。
- 分析不插入边界样本。边界在采样点之间时，积分只覆盖保留样本，分母仍为选定区间时长，
  与现有推力定义一致；正式导出端点插值单独披露。
- 参考压力默认 101325 Pa，可编辑、转换显示单位并随工程恢复，仅作用于显示/PNG。

## 回归证据

最终发布构建的前置检查：187 passed（91.71 s），Ruff All checks passed。
原生 Windows 源码烟测的 42 个检查通过，并生成 24 张主界面截图；包括两种逻辑尺寸、
Light/Dark、zh_CN/en_US、自动 XLSX 导入、真实导出、显式 Processor 保存/重开、
参考压力恢复及真实插件 ZIP 安装/Registry 刷新。

最终 Portable 从 ZIP 解压至独立新目录 `D:\Temp\Underline_RETLDC_0_0_4_release_test_16e450f6`，
实际 EXE 首次运行 50 项检查全部通过；24 张三工作区截图和 8 张参考压力滚动
截图覆盖 980×640、1280×820、Light/Dark、zh_CN/en_US，逻辑窗口尺寸与请求一致。
完整进程退出后再次启动同一 EXE，49 项检查通过，`plugin_loaded_at_start=true`，
确认安装的插件跨进程保留。测试设置、生成数据和测试插件均隔离在该目录的 validation 中，
没有写入用户原有设置或插件目录。

证据：独立目录 `validation/report-first.json`、`validation/report.json` 和 PNG 截图；
构建日志 `build/release-build-final.log`。最终 ZIP 仅补入本报告，EXE 与通过检查的文件
按 SHA-256 比对一致。发布候选位于
`dist/Underline_RETLDC_0_0_4_Windows_Portable.zip`。

| 回归项目 | 已完成证据 |
| --- | --- |
| 预设 | 高匹配实际应用、近似并列、低于阈值的临界第二候选、单位冲突、错误版本、结构冲突、无匹配回退、手改优先、重开不检测 |
| 默认修正 | 新工程 None、极性可用、显式补偿保存/重开恢复 |
| TR_F / TR_P / TR_T | 专用 Parser、歧义选择、校准/极性、补偿与 None 链、分析/导出测试通过 |
| 插件安装 | GUI 7 项、Installer 11 项、Loader 20 项；目录/嵌套/ZIP/多插件、Application 优先、权限回退及 Loaded 校验 |
| 删除 Source | 解析和未解析来源分别处理、最后来源清空、绑定/结果/绘图/导出失效 |
| 零线/参考压力 | GUI 和 PNG 回归通过；参考压力显示转换和 Project 恢复不改源数组 |
| 语言/主题/布局 | 实际窗口尺寸 980×640、1280×820；中英文及 Light/Dark 截图审阅，三栏可用 |
| README | 导航流程、None 默认、预设 effective mapping 和当前标题已同步 |
| 打包 | pytest/Ruff fail-fast 门禁测试通过；两种主题和随包插件启动 smoke 保留 |


原生 Windows GUI 烟测使用公开格式的生成数据：4001 点、0–10 s、400 Hz，
时间/室压/推力/e/Ab/Kn/TC1。额外三个工程列保留为 Other。独立全记录积分与自动区间分析
分别验证：生成样本峰值推力 2000 N、峰值室压 9 MPa、全记录原始推力积分 6000 N·s；
自动区间为 [2.2375, 7.7625] s，Analyzer 总冲约 5962.395833 N·s。
这不是 prompt 中那份原始 XLSX，不能据此声称验证了 1959.0061 N、9.6042528 MPa、
3542.0969 N·s。仓库没有该文件，未读取或提交用户私有试验文件。

README 已移除旧按钮流程，改为左侧工作区导航，并同步 None 默认及预设独立副本说明。
发布脚本在 PyInstaller 前执行完整 pytest / Ruff，失败立即退出，保留 Light/Dark 及插件
加载检查，额外校验产品名、版本和默认 None。

## GitHub 与发布边界

当前环境未发现可用 gh CLI（PATH 及常见安装位置均未找到），因此未修改 Repository About。
安装并登录 gh 后可执行：

~~~powershell
gh repo edit aleistercrowleybeast666/Underline_RETLDC --description "Offline rocket engine test log decoder and analysis platform." --add-topic rocket-engine --add-topic rocket --add-topic rocket-motor --add-topic data-analysis --add-topic pyside6 --add-topic test-data
~~~

也可在 GitHub 仓库首页 About 旁的设置按钮编辑同样的 Description / Topics。
仓库可见性未变；没有创建 v0.0.4 tag 或 GitHub Release，也未修改 v0.0.2/v0.0.3。
改动保留在当前工作区，未自动提交或推送。

## 限制

- 指定真实 XLSX 的精确参考数值待持有该文件的用户核对，生成样本结果已单独列明。
- 小宽度中长指标可截断显示，通过悬停读取完整标签；左栏的下方参考压力控件需要滚动。
- 最初默认 pytest 临时目录存在权限错误。后续完整回归使用项目 build 下独立临时/缓存目录，
  不修改或清理其他任务的临时目录。
