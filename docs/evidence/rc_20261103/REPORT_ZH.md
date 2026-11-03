# Underline Windows 发布候选 · 2026-11-03

分支 `codex/release-candidate-20261103` 从已推送的 main `351ab0b0167eb37bd6312c2bde79181d6225e97f` 切出。下列便携包使用实现提交 `df6fefd392c1577b9b1301dc488e1d175774badb`。工程／推力／燃烧室压力／温度／数据浏览器仍是五个主工作区。[实现提交](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/df6fefd392c1577b9b1301dc488e1d175774badb) · [操作手册](../../../README.txt)

解压整个便携包，运行 `Underline_RETLDC/Underline_RETLDC.exe`。本机可直接从 `D:\python_software\Underline_RETLDC\dist\rc_20261103\Underline_RETLDC` 启动。ZIP 位于 `D:\python_software\Underline_RETLDC\dist\rc_20261103\Underline_RETLDC_RC_20261103_Windows_Portable.zip`，大小 101,439,751 字节。

| 产物 | SHA-256 |
| --- | --- |
| Windows 便携 ZIP | `14fa32f129353026e7644e60cd34cd5317c90d3ac12241c868b35de01ced277a` |
| Underline_RETLDC.exe | `8259a929a0d07c90783bc5e9a5dbd8d139d353d8083d8d1d7f94fe8b4cb3a5cc` |
| 默认 CLI 导出的正样例包，逐字节等同既有 golden | `66c6232d0ccec6ceaabdec9186e9059a2f16dc9eeeedea0c94221f06a8ceaed96` |

全部 891 个 ZIP 成员打开后逐个核对 SHA-256。最终实现、插件、契约、测试和打包输入共 229 个文件，最终构建起止字节一致。本次 PyInstaller 收集目录中的随机标记与构建开始记录精确一致。[产物清单](portable-manifest.json) · [最终输入](source-release-end.json)

## 工作流和科学状态

- 添加普通物理单位 CSV 后核对主通道。raw/ADC 身份标定保留原值。若需要物理标定，工程页顶部有直接可见的操作，打开单层通道与校准属性窗。取消时会撤销仍在计算的本次 Apply 回调。
- 物理参数归工程统一编辑。数字不需按 Enter；非法值使窗口保留整份草稿并定位字段。导出窗上方显示已应用质量和尺寸，修改入口复用同一编辑器。未知质量允许留空。
- 处理器与表单修改为独立草稿。主结果旁标明正在显示上次结果，可以恢复已应用值，或应用并重算。Project schema /2 的可选 `processing_draft` 保存草稿；科学重放仍由已应用引用和完成阶段驱动。
- 新建、打开或关闭遇到未保存修改时作一次保存／放弃／取消选择。保存失败或取消选路径会留在原工程。工程菜单能恢复最近一次区间、主通道或已解析来源删除前的科学配置，重放会核对源文件 SHA。
- 正式导出冻结输入、配置、物理参数、指标和实际插件实例。多选格式先在目标卷暂存，全部完成才发布；取消或后续发布失败会保留/恢复已有文件。手动刷新插件在当前任务结束后执行，已加载实现的文件发生变化时明确要求重启。
- 底层科学算法、motor-test-package /1 契约及 golden 文件沿用基线内容。插件继续是用户明确安装的同进程可信 Python。

## 在最终实现和产物上实际执行

| 验证 | 结果 |
| --- | --- |
| 正常 `打包.bat` 全套 pytest → Ruff → PyInstaller → EXE 浅、深两种启动 smoke | **392 passed in 571.14s**，Ruff 通过，完整批处理 exit 0 |
| Windows 原生便携 GUI，中文浅色、实际 125% | 18 项通过，exit 0 |
| Windows 原生便携 GUI，English dark、实际 150% | 18 项通过，exit 0 |
| 纯数据 CLI，独立 Python 3.14.0 环境只安装 NumPy 2.5.2 | Qt、pyqtgraph、SciPy 均未安装，默认真实导出 exit 0、golden 字节匹配 |
| 正式 EXE 普通启动，Windows UI Automation 核对键盘焦点 | 7 个物理参数字段顺序正确，Esc 返回工程。全部键盘消息发往事先校验 PID 的本程序窗口 |
| 便携 EXE 的 `export` 子命令 | Windows 进程 exit 0、同一 golden 字节匹配 |
| 实际基线与当前 GUI TXT 导出，200 N·s、工程质量从 0.15 kg 改至 0.30 kg | 原报告 0.30 kg / 135.96216173 s，当前报告 0.30 kg / 67.9810808652 s |
| 实际 Qt 确认按钮驱动，关闭取消、打开取消、关闭保存写入失败、关闭放弃 | 四条路径通过。取消/写入失败均保留原工程和文件 |

完整 GUI 工作流使用正常工作区控件、解析器、校准、分析、导出插件及保存重开。合成物理量 CSV 和 raw 文件在每次运行中独立生成。功能校验包含聚焦字段、非法输入、恢复草稿、物理参数即刻可见、共享区间、默认无补偿、图表视图、TXT 与 TreeDiagram 实际导出。实例由 `--release-smoke` 指定独立设置和插件测试目录；窗口抓图使用 Windows Qt 客户区。[完整构建](pack6.log) · [中文 GUI 回执](gui/zh-light-125/receipt.json) · [English GUI receipt](gui/en-dark-150/receipt.json) · [无 Qt CLI](headless-delivery.log) · [便携 CLI](packaged-cli-final.log) · [质量回归](mass-validated.log) · [离开保护](leave-final.log) · [正式 EXE 的 Tab/Esc](tab-receipt.json)

主要页面与属性窗：
[工程](gui/zh-light-125/project.png) · [推力和草稿](gui/zh-light-125/thrust-draft.png) · [压力](gui/en-dark-150/chamber_pressure.png) · [温度](gui/en-dark-150/temperature.png) · [数据浏览器](gui/en-dark-150/data_explorer.png) · [raw 阻塞入口](gui/zh-light-125/raw-action.png) · [校准属性](gui/zh-light-125/raw-calibration.png) · [物理参数](gui/zh-light-125/motor-properties.png) · [导出摘要](gui/en-dark-150/export.png)。

## 命令与未关闭的边界

在仓库根目录用 `underline-retldc-cli export tests/fixtures/motor_test_package/v1/synthetic_positive.retldc.json motor.tdmotor.json` 复验；独立纯数据环境可先安装 NumPy，在 PowerShell 设置 `$env:PYTHONPATH=(Resolve-Path src).Path`，再运行 `python -m underline_retldc.cli export ...`。便携 EXE 使用 Windows 图形子系统，自动化可用 `Start-Process -Wait -PassThru` 检查退出码和输出文件。指定的必需插件缺失会以 exit 2 结束并给出插件 ID，未创建输出。[失败记录](headless-required-failure.log)

本轮构建设置 `CI=1`、`UNDERLINE_RC_20261103=1`、`PYTHONUTF8=1`。pytest 通过 `PYTEST_ADDOPTS=-p no:cacheprovider --basetemp=.work/rc-20261103/pack6 -o faulthandler_timeout=90` 使用独立目录。预检使用 Qt offscreen；正式 GUI 使用 `QT_QPA_PLATFORM=windows`，通过 `Underline_RETLDC.exe --release-smoke <新目录> --candidate-flow --locale zh_CN --theme light` 或 `en_US / dark` 执行。本机 Windows 基础缩放 125%，额外倍率分别为 1 和 1.2，回执记录实际 devicePixelRatio 1.25/1.5。自动化使用 Qt 事件定向操作本应用，并在回执中保留实际输出与截图 hash。

PyInstaller 记录可选 `pyqtgraph.opengl/OpenGL` 和 `scipy.special._cdflib` 的发现警告。此次验收覆盖上述离线二维工作流，未执行第三方 OpenGL 插件、其他操作系统、真实传感器标定精度和完整现场试车。候选 ZIP 存放在本机，本轮交付止于工作分支和候选构建，正式合并、发布与适用的对应源码分发手续另行进行。

## 保留的失败和中间结果

- 首次默认 pytest 临时目录遭遇 Windows 访问拒绝。使用本轮独立 `--basetemp` 后得到真正的两项修复前失败：选中的纯数据导出被无关 Qt 插件拦截，导出质量行可写。[环境错误](before.log) · [修复前回归](pre-v2.log)
- 200 N·s 的旧结果用原提交的 MainWindow、ExportDialog 与 ExportSnapshot 源码，配合原科学插件真实导出 TXT。[原始报告](mass-before/analysis_summary_EN.txt) · [最终报告](mass-validated/analysis_summary_EN.txt)
- 首轮完整预检 380 passed / 7 failed。1 项旧测试把未应用表单当作已应用处理器，其余 6 项暴露 dirty 检查捕获视口，覆盖正在恢复的范围/FFT。已将 dirty 判定改为纯读取并保持原视图断言。[第一次全套](pack1.log) · [范围/FFT 原断言](viewport2.log)
- 另一轮 37 项通过而 Qt fixture 清理发生错误，原因是测试在关闭 executor 后仍模拟用户点击保存。清理明确关闭测试拥有的窗口，真实保存失败行为单独检查。[原始日志](target2.log)
- 旧版本的 389 项完整预检通过后，原生窗口审阅发现窄屏下 raw 操作和旧结果提示可滚出视口，主动停止了已过时的 PyInstaller 阶段。下一实现 `9e09567` 的 390 项完整预检与实际打包成功。再对只选 TXT 的真实窗口复现 ENG 分组隐藏统一参数入口，修复后摘要位于格式选择上方。[中间构建](pack3.log) · [可见性修复前](export-visibility-before.log) · [修复后](export-visibility-after.log)
- 在 `397193c` 上完整 390 项检查通过，主动停止过时的 PyInstaller 后，老脚本错误跨过负退出码并以原 EXE 启动，返回 0。该次编译没有得到认可，保留原 EXE 的未变 hash、退出与原日志。新的所有原生命令门禁拒绝负退出；本次构建写入的随机标记必须与 PyInstaller 新收集目录中的标记完全一致。隔离故障注入覆盖原生 0xffffffff，以及错误返回 0 却无新产物两种情况，均须在复制阶段前拒绝。另补非表格解析详情的空诊断折叠和内部解析器身份 tooltip。[异常退出修复前](builder-exit-before.log) · [修复后两例](builder-exit-after.log) · [真实中间日志](pack4.log) · [旧 EXE 比对](pack4-stale-evidence.json) · [空诊断修复前](import-visibility-before.log) · [修复后](import-visibility-after.log)
- 最终源首次整组的两个 15 秒入口用例超时。12 逻辑核负载采样为 100%，同命令诊断完成时间分别为 16.356 s 与 16.793 s，均 exit 0，原 15 秒条件仍不满足。短暂资源窗口，未经修改的两项用例合计 23.70 s 通过。最终构建重新执行完整门禁，未把定向结果拼入首轮。[首次整组](pack5.log) · [负载采样](contended-host.json) · [诊断时长](timed-entry-contended.json) · [原门槛定向复验](entry-window1.log)
- Windows 的 Qt offscreen 渲染缺少字形。已验看原生 windows 平台实际截图，最终展示图均来自此次构建的 EXE。

外部 Tab 探针的前两次尝试分别受前台窗口定位和异步按钮激活影响，未计作产品通过。最终基于本进程窗口句柄和实际 Invoke，逐个比较真正的 UI Automation 焦点对象后通过。主程序源码和产物在三次尝试间保持同一身份。[首次定位](tab-check.log) · [第二次定位](tab-check-v2.log) · [最终回执](tab-receipt.json)
