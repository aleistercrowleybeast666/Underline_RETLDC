# Underline 工作流收敛 · 2026-11-10

沿用 `codex/release-candidate-20261103`，基线 `a6e5d3b1eab66032c109cedbcd0743c05395c2c9`。
本轮功能实现为 [094777c](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/094777c70b61a1742f89ad05ee06e7c0c732da1c)。
相对统计兼容补齐为 [437c7bc](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/437c7bce196fdc6fef8af308fdfb393c5bc1a344)。
随后补充双主按钮数字输入覆盖：[3584cc4](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/3584cc4488baefc1eae19480420dc1d8a59b3914)。
原生审阅后补清晰的已提交区间状态：[72390b9](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/72390b900427b1f57c12b8688390351a762dc1ff)，也是首个完整便携产物的源码身份。
实际 150% 桌面审阅发现首次窗口越屏后，补启动时尺寸/位置限制：
[04ac660](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/04ac660eb30d685a723b586e3e03c906b9f82bea)。
仓库新增产物治理为 [4aa2e7a](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/4aa2e7aa0885ab34a0b201b6d7763875ac38e7cd)。
保留原五工作区、科学插件、Project schema、motor-test-package /1、源数据只读与既有原子导出。
原未跟踪的 `docs/Repository_Showcase_Review_20261016.md` 未改动或纳入提交。

## 用户路径

导入并核对单位/校准，在推力页选定区间后，顶部主按钮第一次即可完成处理与分析。
有处理草稿时，按钮显示“应用并重新计算”；两阶段全部成功才一起发布已应用结果。
处理失败、分析失败、取消或输入已被新草稿取代时保留原有效结果。压力、温度和独立来源
仍走各自既有消费者。展开左侧“高级处理与基线详情”可单独应用处理，随后需重新分析。
非物理单位仍可走已有相对统计；按钮明确显示“计算相对统计”，SI 指标和物理导出继续不可用。

试车区间修改会直接提交到唯一 Project 区间 owner，按既有规则使依赖结果失效；它不是
processing_draft。当前输入/区间尚无结果时，结果区和导出窗明确要求重算并提供返回入口。
不会把旧结果与新边界的 provenance 混在一起，也不会把该状态误说成仍可导出旧处理草稿。

导出窗显示结果来源、区间和总冲；有草稿时明确说明新修改尚未包含，可以选择
“导出已应用结果”或返回同一推力编辑入口。类别收为报告、数据、图像、模型交换，
同时显示选中、可用和缺条件数量；类别只是呈现信息，科学输入 owner 未改变。

左栏改为 280–360 Qt 逻辑像素，基线详情默认折叠；右侧物理指标优先、重复通用统计按需展开。
语言、主题和正常插件刷新保留正在输入的处理参数。合法数字无需 Enter 即可提交；
非法中间输入保留并定位字段，同时阻止保存旧值冒充新草稿。
[完整操作说明](../../../README.txt) · [科学状态和计算路径](../../Analysis.md)

## 本轮验证

环境：Windows 11 build 26200，Python 3.14.0，PySide6 6.11.1，NumPy 2.5.2，
SciPy 1.18.0，pyqtgraph 0.14.0，pytest 9.1.1，Ruff 0.16.2，PyInstaller 6.22.0。

| 执行 | 结果和范围 |
| --- | --- |
| 修复前真实入口回归 | 4 failed：首次顶部按钮不可用、顶部未应用草稿、分析失败丢失旧有效对、导出无就地状态提示；[原日志](pre-fix.log) |
| 新事务/输入/旧结果导出和既有导出布局回归 | 13 passed in 79.95s；[日志](targeted.log) |
| 既有候选与小窗口回归 | 首轮 1 failed / 5 passed，英文室压控件最小宽度超过视口；修复换行/输入框宽度后原几何断言通过；[失败](regression.log) · [复验](geometry.log) |
| 首次完整 403 项 | 402 passed / 1 failed in 584.83s；旧断言仍要求基线详情固定在第 5 项，现由 Advanced 按钮占第 5、详情第 6；[完整日志](full-suite.log) |
| 布局顺序及真实 batch 故障/隔离路径 | 8 passed in 10.52s；保留顺序检查并增加默认折叠/展开，异常退出和无新产物均拒绝，非法构建标签在输出前拒绝；[日志](pack-path.log) |
| ADC 相对分析与物理首次计算 | 2 passed in 19.56s；相对积分 220、SI 指标不可用、ENG/TreeDiagram 禁用；[日志](relative.log) |
| 左侧主按钮数字输入 | 2 passed in 21.85s；合法 2.75 和非法中间文本，均通过真实键盘及按钮事件，无需额外焦点修补；[日志](panel-input.log) |
| Ruff | All checks passed；[日志](ruff-final.log) |
| 最终源码无 Qt 的默认 CLI 实际导出 | exit 0；导出的包与本轮 GUI 首次计算后的包逐字节一致；[日志](integration/cli-final.log) |
| 第一次正常打包预检 | **409 passed in 702.20s**；随后 Ruff 发现并行新增治理脚本的 3 处 import/行宽问题，batch exit 1，PyInstaller 未开始；[完整日志](package-preflight1.log) |
| 原生发现的区间状态缺口 | 真实键盘将 end 从 4 改为 3.95，直接 Export；原先缺就地说明，回归 1 failed；补提示后与旧草稿路径共 2 passed in 19.59s。新区间计算为 219.25 N·s，旧 220 N·s 不与新区间混用；[修复前](interval-before.log) · [修复后](interval-after.log) |
| 首个完成的正常 `打包.bat` | **410 passed in 829.74s** → Ruff **All checks passed** → 实际 PyInstaller → 便携 EXE 浅/深两次 smoke，完整八步骤 **exit 0**；[完整日志](package-final.log) |
| 首个完成的便携 EXE 默认 CLI | 新工程实际重放并使用正式副本重新定位来源，exit 0，新 motor 包仍为相同 `eed976…017e3`；[回执](portable-cli.json) |
| 首次窗口尺寸回归 | 3 passed in 43.84s；真实 Qt 窗体在 1536×816、1280×680 逻辑可用区完整约束，合法位置保持，语言/主题切换不重新定位；[日志](startup-geometry.log)。offscreen 几何用例不冒充原生缩放验收 |
| 清理后实际 CLI | 当前源码与首个完整便携包均 exit 0；重新定位同一保存工程后 motor 字节仍一致，输入来源/工程哈希不变；[回执](cleanup/cli.json) |
| 启动修复后的正常 `打包.bat` | **413 passed in 1189.76s** → Ruff **All checks passed** → 实际 PyInstaller → 浅/深便携 EXE smoke，完整八步骤 **exit 0**；[完整日志](package-fit.log) |
| 新 fit 便携 EXE 默认 CLI | exit 0，重新定位正式副本后实际默认导出，仍得到相同 `eed976…017e3`，来源/保存工程未变；[回执](portable-fit-cli.json) |

首次完整结果未被定向通过拼接为全套通过；409、410 和 413 均为各自独立的完整执行。
第一次正常 `打包.bat` 在 Ruff 失败处停止，第二次通过完整测试和 Ruff 后才进入 PyInstaller。
两个候选各自完成正常八步骤；预检与便携 smoke 使用 offscreen，不以它们替代桌面验收。

测试命令：

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest -v --tb=short --durations=10 --basetemp=.work/gui-convergence-20261110/full-tests -o cache_dir=.work/gui-convergence-20261110/cache
.venv\Scripts\python.exe -m ruff check .
```

原 15 秒入口启动上限保持不变；首次完整测试中两个入口都通过。
新回归通过真实导入与顶部按钮验证首次计算、220→200 N·s 草稿应用、注入分析失败、取消、
较新草稿、未失焦键盘输入、非法文本、语言/主题/刷新、保存拒绝和明确导出旧结果。
既有质量归属、保存失败、导出原子回滚和纯数据 CLI 回归仍在完整套件中。

## 本轮新数据闭环

[reproduce.py](reproduce.py) 新建明确标注 synthetic 的 CSV，经普通解析器导入、首次顶部计算、
既有保存和默认 CLI 导出。CSV 不是旧 golden 复制，也不代表实物测量或传感器标定。
CLI 的独立进程通过 import guard 拒绝 PySide6/pyqtgraph，确实执行默认 motor 导出。
源字节未变；独立重放仍得到相同文件哈希。

| 输入/产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| [synthetic_20261110.csv](integration/synthetic_20261110.csv) | 4310 | `fe46ccce39dc92765e6848021df540558b40d3d4bb95b7f00ba0c1b181e6a615` |
| [保存工程](integration/Synthetic_20261110.retldc.json) | 11750 | `1f2c4168fcda6d18d13332febfdf6e693eec4d941d027b789917b203b1354516` |
| [motor.tdmotor.json](integration/motor.tdmotor.json) | 10507 | `eed976bb0d95d90f680a6b72988e42b2a93b5342d5756a1d4a0a437930f017e3` |

包内容摘要 `fc07e75df6171d5da31e54adb0417ff8babc93f38be254a2d9667dbb2dcedd66`。
实际总冲 225 N·s、推进剂 0.18 kg、总质量 0.42 kg、直径 0.054 m、长度 0.24 m；
121 个证据点、41 个有效区间点，0.05 s 采样、区间 2–4 s。[原回执](integration/receipt.json)

工程保留当时绝对来源路径；迁移后使用已有 `--relocate source_1=<上述 CSV 路径>`，仍须哈希相同。
从仓库根目录可复现：

```powershell
.venv\Scripts\python.exe -X utf8 docs/evidence/gui_convergence_20261110/reproduce.py .work/gui-convergence-20261110/reproduced
.venv\Scripts\python.exe -X utf8 -m underline_retldc.cli export docs/evidence/gui_convergence_20261110/integration/Synthetic_20261110.retldc.json .work/gui-convergence-20261110/replayed.tdmotor.json --relocate source_1=docs/evidence/gui_convergence_20261110/integration/synthetic_20261110.csv
```

TreeDiagram 使用这份新包实际导入并完成 run `4008f769-9d31-4182-bee5-7477845b5870`，
相应仿真与 SilverStar 消费者证据由各仓权威报告记录；Underline 不将其代报为自己的硬件通过。

## 运行与交付边界

源码：`.venv\Scripts\python.exe main.py --locale zh_CN --theme light`。
便携版完整解压后运行 `Underline_RETLDC/Underline_RETLDC.exe`，无参即正常 GUI，
可附加 `--locale en_US --theme dark`。整个文件夹是运行单元，不能只复制 EXE。

当前候选含首次窗口限制，其源码身份为
[6933851](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/69338514e9017f2801a779fd9811b78e848591f5)。
本机目录为 `D:\python_software\Underline_RETLDC\dist\gui-convergence-20261110-fit\Underline_RETLDC`。
同级 ZIP 为 `Underline_RETLDC_GUI_20261110_Fit_Windows_Portable.zip`，98,654,508 字节。

| 产物 | SHA-256 |
| --- | --- |
| 当前 fit 便携 ZIP | `7d518a16f927a0fd643e158ca7bec0b95d24823896a350af710bb94d8da7c58a` |
| 当前 fit Underline_RETLDC.exe | `87e4d65154db99cad5f07587a8c7bd6af35351d2cb83637ff99dae46474b3840` |

ZIP 的 891 个文件均重新读取并与原目录逐项核对大小和 SHA-256。472 个实际打包输入的
起止清单逐字节一致，清单 SHA-256 为
`aa501c9f7e942e7cfbb4a8f5c5d6067933a07b2ec0cc001383491b84fe6b70b4`。
本次随机构建标记 `da7c572138624450af48e949a47f408b` 与收集目录一致。
[当前产物及验证清单](portable-fit-manifest.json) · [当前输入清单](source-fit-inputs.json)

首个完整候选的原 `dist/gui-convergence-20261110/` 副本已在 2026-11-11 恢复核验后退役；
ZIP 持久保留于 `D:/SilverStar_Archive/20261110/task/underline/Underline_RETLDC_GUI_20261110_PreFit_Windows_Portable.zip`。
其源码 72390b9，ZIP 98,650,426 字节、
SHA-256 `aa47c148ed9eaf81948f9f1b0b316cd41d19761d4194401ea927025027a367d6`，
EXE SHA-256 `c524f271a643dd29e4f561881a1b3fc58fec1c7678848fde5d9c4be713ffc9c8`。
其首次窗口越屏已由新候选修复；保留旧身份用于追溯，不把它当作新修复的产物。
[首个产物清单](portable-manifest.json) · [首个输入清单](source-inputs.json)

当前候选正常打包使用以下环境；测试和回执仍在本轮同一任务目录，打包中间产物由
新标签隔离在 `.work/gui-convergence-20261110-fit/package/`：

```powershell
$env:CI='1'
$env:PYTHONUTF8='1'
$env:UNDERLINE_BUILD_TAG='gui-convergence-20261110-fit'
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTEST_ADDOPTS='-v --tb=short --durations=10 --basetemp=.work/gui-convergence-20261110/package-fit-tests -o cache_dir=.work/gui-convergence-20261110/cache'
.\打包.bat
```

既有正式发布与 `dist/rc_20261103/` 不被覆盖；标签不跳过任何门禁。

## 原生窗口与剩余边界

主负责人已在生产 MainWindow、私有 settings 的 Windows 原生窗口观察 English/dark，
实际 DPR 1.5（OS 125% × `QT_SCALE_FACTOR=1.2`）。打开本轮 Synthetic 工程后看到 225 N·s
曲线/主要指标和固定顶部 Update results，导出底部操作可达。该次真实操作发现区间更新的
提示缺口，随后由 72390b9 修复；旧截图不被当作修复后验收。关闭时丢弃本次测试修改，原工程未变。
原截图统一保留于 SilverStar 的
`docs/evidence/gui_convergence_20261110/gui_native/underline-en-dark-150.png`，不重复复制。

主负责人随后用首个完成的便携 EXE，真实执行 None → Linear Weight-Change Compensation
草稿：主按钮变为 Apply and recalculate；Export 明确显示 previous applied result、2–4 s / 225 N·s、
Return 与 Export applied results。Return 后用顶部主按钮一次重算成功，仍为 225 N·s，
Result up to date 且仅剩 Unsaved changes。关闭显示 Save/Discard/Cancel，测试修改已 Discard，
原工程未变。截图统一保留于 SilverStar 的
`docs/evidence/gui_convergence_20261110/gui_native/underline-portable-draft-export-150.png`。

这次原生操作还确认默认 1280×820 窗口超出实际 1280×680 逻辑工作区，手动最大化不算修复。
04ac660 在正常应用启动时按目标 QScreen 的 availableGeometry 约束包含原生边框的尺寸和位置，
已合法的几何不变；只在首次 show 与边框确定后的单次回调执行，不挂接语言、主题或普通刷新。
真实 Windows QScreen 查询为 DPR 1.5、availableGeometry 1280×680，与故障一致。
修复后已以独立标签 `gui-convergence-20261110-fit` 完成正常 413 项和全部打包步骤。
主负责人随后运行该新 EXE（上表 `87e4d651…3840`），参数 `--locale en_US --theme dark`，
OS 125% × `QT_SCALE_FACTOR=1.2` 为实际 150%。没有手动最大化、移动或缩放，首次窗口
完整可见，含工具栏和状态栏。真实 Open Project → 本轮 Synthetic 工程 → Thrust，
Update results 保持可见，225 N·s 结果、主图和 Saved 状态准确。Alt+F4 正常退出，无工程修改；
Computer Use 随后已退出。原生截图由 SilverStar 统一保留：
[150% 首次窗口](https://github.com/aleistercrowleybeast666/SilverStar/blob/b5f9d645313db7dbf39e0737012fe31db11353d5/docs/evidence/gui_convergence_20261110/gui_native/underline-fit-first-show-150.png) ·
[150% 实际结果](https://github.com/aleistercrowleybeast666/SilverStar/blob/b5f9d645313db7dbf39e0737012fe31db11353d5/docs/evidence/gui_convergence_20261110/gui_native/underline-fit-result-150.png)。
此前 410 项与旧截图不被当作新窗口验证。

同一 fit EXE 随后以 `--locale zh_CN --theme light` 在 OS 125% × factor 1 的原生环境首次启动。
未手动移动、缩放或最大化，主导航、顶部动作和底栏完整可见，正常关闭且 stderr 为空，
Computer Use 再次退出。[125% 首次窗口](https://github.com/aleistercrowleybeast666/SilverStar/blob/b5f9d645313db7dbf39e0737012fe31db11353d5/docs/evidence/gui_convergence_20261110/gui_native/underline-fit-first-show-125.png)。
自动逻辑几何回归与这两次实际原生缩放观察分别记录，没有用 offscreen 替代桌面验收。

## 可确认的本地清理与防回流

治理脚本只检查 Git 新增/修改 blob，2 MiB 上限、工作区/构建目录限制和原测试输入例外均保留。
实际 staged 5 项和基线之后 55 项通过；精确 2 MiB 边界、超限、工作区、build 与二进制分类核对通过。
忽略规则补 `.qa/`、`.test-tmp/`、`.codex-remote-attachments/`；CI 对 push/pull request 调用同一检查。

清理复用 SilverStar 已提交的 `apps/FLP/tools/clean_workspace.py` Python API，
来源提交 `737126081adec290721c783310ed0b36537f8a8c`，文件 SHA-256
`35ebd3b83c3b89b98f6a1f2cec27e601caa9c1afec988d27e88926694ef5a321`。
显式 root 为本 Underline 仓，scope 为 src、plugins、tests、scripts、tools、根 __pycache__
及本任务 `.work/gui-convergence-20261110`。未运行默认指向 FLP 的 CLI，没有复制第二套删除框架。
先调用 Plan/PlanSave，逐项审阅后 PlanLoad/Apply；保留检查、文件哈希/身份、索引检查与空目录
rmdir 均由同一 API 实施。实际删除仅 253 个 `.pyc` 与 105 个空缓存目录，共 **4,498,105 字节**。
[预览及 API 身份](cleanup/preview.json) · [删除回执](cleanup/applied.json) ·
[保护清单](cleanup/protected-before.json)。7 个 plan 文件保留了删除前每个路径的身份与 SHA-256。

磁盘可用空间在 Apply 前后从 30,248,079,360 到 30,252,523,520 字节，区间增量 4,444,160 字节。
同时其他仓有工作，区间变化不能完全归因于本次删除；逻辑删除量以上述逐文件记录为准。
845 个跟踪或明确保护文件哈希完全一致，包括原 Showcase、新 CSV/工程/motor 和旧 ZIP/EXE。
以上缓存清理当时的 dist、build、.venv、docs、fixtures、其他任务 work 与小型根缓存均保留；未分类试验文件、
当前/历史产物和唯一输入不因目录名称被视为可丢弃。清理后实际运行两条 CLI，结果见上表。
正常后续运行可以重新生成缓存；不通过反复删除追求空目录，也不把本次清理当作改写 Git 历史。

需要逐字节校验的 JSON 保留原始 Windows CRLF。Git 的通用 whitespace 检查因此把 CR
报告为行尾空白；逐行核对没有尾随空格/Tab，14 份 staged JSON 均可解析且与原文件字节一致，
7 个清理 plan、保护清单和新包输入清单的哈希均匹配回执。普通文本的 whitespace 检查通过，
未修改门禁或证据字节。[字节校验记录](evidence-byte-check.log)

PyInstaller 保留可选 `pyqtgraph.opengl/OpenGL` 和 `scipy.special._cdflib` 发现 warning；
本轮验收为已有二维离线工作流，未声明第三方 OpenGL 功能可用。未执行真实采集、
实物控制或传感器标定准确性验证。候选包在本机生成，未创建正式 Release；上游对应源码、
库替换等正式分发事项沿用原发布说明与许可材料，不能由 smoke 通过代替。
跨仓交付与远端身份由主负责人统一汇总。

### 2026-11-11：退役已被 fit 替代的便携副本

中断后先核对 HEAD 与原预览 SHA，再执行原明确范围：旧 `dist/gui-convergence-20261110/Underline_RETLDC`
的 891 文件、旧 `.work/gui-convergence-20261110/package` 的 13 文件，以及旧 ZIP。
最终 fit 目录/ZIP、472 个打包输入、唯一 CSV/工程/motor、原 Showcase 和其余任务不在删除范围。

旧 ZIP 原字节复制到上述稳定外部目录；13 个打包文件另存
`Underline_RETLDC_GUI_20261110_PreFit_Build.zip`，46,482,985 B，SHA-256
`600d39bb1084580d6e23baf642987611d510f419f3b661cc0754e22d7ac48f3f`。
两份归档均**实际解压到磁盘**，逐路径、大小与 SHA-256 核对全部 904 文件后，再逐叶清除恢复副本。
只读比较现有归档与原位置的访问主体/权限，范围相同；续行没有改 ACL。

随后以单一 PowerShell 流程再次校验绝对根、每层祖先无 reparse、原始 size/mtime、
Windows volume/file-ID 与 SHA-256，逐文件删除并只移除空目录；没有递归删除、跨 shell
拼装删除命令、修改共享清理工具规则或使用 `git clean`。
实际移除 **905 文件 / 387,115,321 逻辑字节、405 空目录，0 失败**。
完整预览、恢复与删除清单及脚本保留于外部归档目录，精简索引见
[退役回执](cleanup/prefit-retirement.json)。两份冷档共 **145,133,411 B**。

Apply 前后 D: 可用空间从 **33,973,370,880** 到 **34,381,037,568 B**，
区间增量 **407,666,688 B**。同时其他清理/构建在进行，不能将该增量独占归因于本次动作。
逻辑删除量、冷档大小与磁盘区间变化分别记录。

原两个目录及原 ZIP 已不存在；当前源代码和最终 fit EXE 随后分别实际运行默认 CLI，
两次均 exit 0，仍导出同一 `eed976…017e3` motor 包，来源与保存工程字节不变。
见[清理后入口复验](cleanup/post-retirement-cli.json)。本阶段没有产品源码改动，
413 项完整测试和真实打包仍对应前述相同源码输入，不重复跑无关科学计算套件。
