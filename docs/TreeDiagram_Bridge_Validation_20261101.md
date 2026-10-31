# Underline → TreeDiagram 桥接验证记录（2026-11-01）

本记录只说明 Underline 的实现及实际运行范围。TreeDiagram 物理求解、参数包与 SCG
生成的跨仓库完整链路由各消费者仓库记录，不把本记录的 Host 检查说成硬件或飞行验证。

## 输入、提交与原有工作

- 开始基线：`main` / `f913c376daf9cb7ebedfd584069866fe510aa30c`；当时
  `GitHub_Underline_RETLDC/main` 同 SHA。
- 主实现：`153fbd6038cb52e7474a42f7c944002fa643c255`。
- 最终受测代码：`e4001bf730692f58071a1df4d1efad756bd84379`。本记录随后单独提交；
  完整冻结回归期间没有修改运行代码。
- 原先未跟踪的 `docs/Repository_Showcase_Review_20261016.md` 保留，未纳入这些提交。
- 本子任务没有推送 Underline，也没有打包/覆盖原有 0.1.0 EXE 或发布 Release。

## 实际入口与实现

| 用户入口/要求 | 实现与消费者 | 结果 |
|---|---|---|
| 既有导出对话框 | `builtin.exporter.treediagram_motor`，由标准插件发现与能力元数据加载 | 保留现有 GUI 导航、布局和主题；缺能力禁用；后台任务导出 |
| 正确来源与冻结 | `app/export_snapshot.py`、`app/source_input.py` | 按 Primary 完整引用和实际处理输出解析；导入时绑定源 SHA；活动来源选择不替换身份 |
| GUI/CLI 共用重开 | `app/project_pipeline.py`、`cli.py` | 迁出原有真实编排，未另写简化计算；相对路径依工程目录；显式重定位校验原 SHA |
| 原生数据包 | `plugins/exporters/treediagram_motor/` | 实际 SI 转换、完整带符号证据、独立 ACTIVE_TEST 派生曲线、受界定插值、实际时间积分 |
| 质量/资格 | 原有 motor metadata、标定文档 provenance | 未知保持 null/unknown，原文说明保留；估算 profile 明确 estimated；改参数不继承旧资格 |
| 契约 owner | `contracts/motor-test-package/v1/` 与 `contract.py` | 严格类型、界限、数值、摘要及错误码；TreeDiagram 使用固定副本 |
| 原子写入 | exporter 的同目录临时文件、验证、fsync、os.replace | 中途取消保留原目的文件，临时文件只删除本次创建项 |

普通用户在已有流程中完成导入、标定、极性/补偿与分析，然后在“导出”中选择 TreeDiagram
格式，得到 `motor.tdmotor.json`。无需先保存工程。CLI 使用已保存且完成所需工作流的工程：

```powershell
# 在仓库目录；沿用已有环境，干净环境先 python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe main.py
.venv\Scripts\python.exe -m underline_retldc.cli export `
  tests/fixtures/motor_test_package/v1/synthetic_positive.retldc.json motor.tdmotor.json
# 任意 cwd 使用工程、输出和 python 的绝对路径；无需切到数据目录
# 显式搬迁原始文件：追加 --relocate bench=D:\path\synthetic.csv
```

完整规范、错误码、摘要算法与兼容边界见 [交换规范](TreeDiagram_Export_Contract.md)。

## 实际验证与证据

环境：Windows 11 10.0.26200，Python 3.14.0 AMD64，NumPy 2.5.2、SciPy 1.18.0、
PySide6 6.11.1、pytest 9.1.1、Ruff 0.16.2。GUI 检查是 Qt `offscreen`，不声称桌面鼠标验收。

| 命令/检查 | 实际结果 |
|---|---|
| `.venv/Scripts/python.exe -u -m pytest -q -p no:cacheprovider --basetemp=.work/0.1.0-motor-bridge-20261101/frozen-final` | 379 passed in 850.77s (0:14:10)，退出 0 |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/integration/test_motor_bridge.py --basetemp=.work/0.1.0-motor-bridge-20261101/targeted-final` | 31 passed in 20.67s |
| `.venv/Scripts/python.exe -m ruff check .` | All checks passed |
| `git diff --check`，契约 manifest 所列全部 SHA-256（工作文件与 Git 提交原始字节分别核对） | 通过 |
| 实际 CLI 分别导出两个 synthetic 工程，与已提交 golden 的原始字节比较 | 两份完全一致 |
| 仅 import `underline_retldc.cli` 后检查 `sys.modules` | 未载入 PySide6、pyqtgraph 或 GUI 包 |
| `main.py --smoke-test --locale zh_CN --theme dark` | 退出 0；Qt offscreen，125% 缩放 |
| `main.py --smoke-test --locale en_US --theme light` | 退出 0；Qt offscreen，100% 缩放 |

两个 smoke 均通过 `UNDERLINE_NATIVE_DIAGNOSTICS_DIR` 使用本任务独立设置与阶段日志，未改用户设置。
它们真实创建 MainWindow、发现插件、显示窗口、切换中英文并执行既有 plot CSV/PNG/SVG 出口。
桥接测试另真实创建原有 ExportDialog，选择格式、启动 TaskManager、切换活动来源字段并等待落盘；
产物仍对应原主推力。算法断言直接检查数组、时间、来源、数值与文件，不依赖截图判断。

31 项桥接参数化用例覆盖：实际 K/B→极性→基线补偿、200 N·s 总冲，多 Source 同名 Channel
与不同采样率、任意 cwd、未保存会话、原文件后改/解析中改、重定位匹配及不匹配、自定义最终
通道名、缺质量、错误/布尔质量、mm→m、kN→N/raw 拒绝、负样本保留、重复/倒序/非有限时钟
或样本、长缺口、边界插值/越界覆盖、超量样本、坏长度/摘要/版本、重复 JSON 键与嵌套限制、
取消保留旧输出、GUI/CLI 一致、估算标定与原始 notes 保留、第三方默认导出组兼容。

明确的数值样例：61 个证据点、0.05 s 采样、ACTIVE_TEST 0.5–2.5 s，峰值 200 N、
实际梯形总冲 200 N·s；质量 0.15/0.4 kg，直径/长度从 50/200 mm 转为 0.05/0.2 m。
完整补偿路径保留约 -1.07e-14 N 的数值负值并诊断，未自动截零。另一个实际仿射标定、无补偿
样例得到非负三角曲线，供消费者默认运行。它们都是本仓库合成数据，非真实试车或设备校准证明。

固定身份：

| 对象 | SHA-256 |
|---|---|
| schema 文件 | `23b484e42ed2245c2547562969ade6327222c46eaf83954dcffdd6750f3ce3d2` |
| portable validator 文件 | `ea4eaaf4e38587e44678a3bd05fef476fda2329c49596ce7201cbbbba0479988` |
| valid_synthetic 文件 | `6b8ea90658017c9419c4344022ed41d7d8ab90f6dfeb52fa608893ccf976467a` |
| valid_positive 文件 | `66c6232d0ccec6ceaabdec9186e9059a2f16dc9eeedea0c94221f06a8ceaed96` |

原始字节 fixtures 使用 Git `-text` 和 `cr-at-eol`，保留 Windows 实际导出字节及源 CSV 哈希；
schema/portable validator 固定 LF，避免不同 Git autocrlf 配置改变消费端固定摘要。
最终 Git 对象核对曾检出 schema 工作副本仍为 CRLF，旧 manifest 的 `402f…fb440`
与已提交 LF schema 不符。本次交付将工作副本正规化为 LF，并把 manifest 改为上表的
`23b4…ce3d2`，随后逐项核对通过。schema 的字段和语义没有变化；这次交付元数据修正
独立于受测运行代码，不能把修正前的 hash 检查声称为通过。

## 修复前复现与中间失败（未抹掉）

读取基线 Git 对象中的实际旧方法，以 AST 取出并调用原 `_export_execute` 编排，使用真实
CSV exporter 与合成输入。旧方法导出曲线对应源 SHA `aad867fbbb51ce9c9c0e5e2ee1c9bc36004d353a437adc6ff34d6e5ff0377c32`，
却把当前另选来源 `ffff…ffff` 和分隔符 `;`、时间单位 `ms` 写入 provenance。修复后相同
导出写入实际 SHA、`time_unit=s` 与 `invalid_row_policy=error`。这是 Host 调用实际基线
编排的复现，不冒称旧 GUI 端到端点击录像。

同样调用基线 `_project_streams_recompute` 从仓库 cwd 打开
`examples/synthetic_overlay/synthetic_overlay.retldc.json`：旧逻辑查找仓库根的
`synthetic_reference.csv` 并报缺失；修复后两个来源均解析到工程自己的目录。

开发中的完整初次运行为 **10 failed / 338 passed / 2 cache warnings (502.22s)**：
7 项暴露迁移编排时 secondary Source 的局部变量错误，3 项为新第 10 个 exporter 的
旧数量/能力预期。局部变量已修正；旧测试按新插件能力真实更新，没有放宽数值或来源断言。
单独 GUI 重测中间状态为 **3 failed / 50 passed (149.04s)**，均为那 3 项旧预期。
随后完整中间状态 **376 passed (770.58s)**。这些运行覆盖了开发中快照，不能归因于最终冻结
提交；最终提交的独立完整结果列在上表，不能把各次局部通过拼接为全套通过。

失败名称完整列于配套 [证据摘要](evidence/TreeDiagram_Bridge_20261101.json)。原始开发日志与
pytest 临时夹具位于 `.work/0.1.0-motor-bridge-20261101/`，owner 为本桥接任务；
该目录只保存本次生成夹具/日志/输出，没有复制仓库、SDK 或用户数据，没有清理旧 `.work`。
可长期复现的 source fixtures、测试、契约与最终结果摘要均已提交，不依赖这个临时目录存在。

## 精确边界与未完成项

- v1 原生包完整支持推力与现有 motor metadata；未实现压力/温度辅助流打包。既有相关导出
  仍使用各自完整 Primary 引用，未把主推力源哈希套给其他来源。
- 历史工程若从未保存标定原文，无法自动恢复其 notes/资格；不会凭单位或增益推断校准证书。
  showcase 的现行 profile 明确 estimated，原历史报告、数值和数据未改写为校准性能证据。
- 未提供真实硬件、设备校准、飞行精度、压力高度修正、整机惯量/安装姿态或真实质量流率证明。
  输入前后 SHA 检查只防止观察到的文件身份变化，不是可信采集或标定真实性认证。
- 本次只交付源码和可运行入口，未制作新安装包、二进制发行版；没有因权限失败跳过本仓库软件修改。
- 跨仓库完整仿真与 SCG 参数消费结果以 TreeDiagram/SilverStar 本轮报告为准，本记录不借其结果
  宣称 Underline 已验证整机动力学或固件实物行为。
