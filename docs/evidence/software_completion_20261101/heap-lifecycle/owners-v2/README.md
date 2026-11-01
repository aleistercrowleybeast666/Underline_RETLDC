# Qt 原生所有权与普通整组验收

本批次继续处理上一批普通 pytest 的 `0xc0000374`，没有把临时 ImageExporter
参数树修复误记为堆崩溃已解决。旧失败及第一次修复记录保留在上级目录。

源基线为 `c1f8ac76f9bbcde1076ef9e48624c920ad161960`。本批次生产改动只有
`app/release_smoke.py`（上批临时导出资源）、`gui/plot_ui_i18n.py` 和
`gui/source_analysis_widget.py`。`owners-final-source.json` 冻结 215 个
src/plugins/tests 文件的实际字节；`owners-final-source.diff` 给出相对基线差异。
新测试包含在该字节清单中。文档改动不属于运行时源码。

## 已复现的错误边界

真实 TaskManager 的失败任务会通过 exception traceback 保留窗口。Qt 原生窗口
删除以后，pyqtgraph 两个菜单根仅由 Python 引用保留，并没有所属 PlotWidget
这个原生父对象。随后在工作线程收集该引用环时，24 个菜单相关 QWidget
在工作线程析构：4 个 ViewBoxMenu、12 个 QMenu、8 个 QFrame。
窗口 Qt 删除后当时还有 48 个原生顶层控件存活。

另一个独立问题是 SourceAnalysisWidget 的隐藏 `parameter_scroll` 没有进入
可见布局，也没有 Qt 父对象。即使保留 Python wrapper，所属控件 Qt 删除后，
它也应同步失效；修复前该断言失败。

- `window-orphan-failure.jsonl` 是失败任务、Qt 删除、worker GC 的原始线程记录。
- `owners-before-v3.log` 中两个正式回归均在原生资源仍然存活的断言失败：
  **2 failed / 18.41 s**。
- 更早 `owners-before-v2.log` 的第二项还包含诊断测试误写 3 个 editor 的计数，
  已明确保留；实际有 4 个。最终测试遍历所有 editor，并在真正的原生失效
  断言处复现失败。没有改变应用对失效、线程或科学结果的期待。

## 修复与验证

菜单根在拥有它的 PlotWidget 上建立 Qt parent，并保留原有 windowFlags；
菜单仍是弹出菜单。隐藏参数面板改为 `QScrollArea(self)`，继续隐藏且不加入
可见布局。临时 ImageExporter 资源沿用上批 GUI 线程创建与 `deleteLater`
退休。没有禁用全局 GC，没有 monkeypatch 供应商模块，没有修改科学计算、
解析或导出数据，也没有跳过旧测试。

| 验证 | 实际结果 | 原始记录 |
|---|---|---|
| 相同失败任务与 worker GC，使用修复后的真实生产源码 | Qt 删除后残留 0，worker GUI 析构 0 | `window-orphan-after.jsonl`, `owners-thread-summary.json` |
| 新生命周期回归、多语言菜单、真实 CSV/PNG/SVG、原 portable source workflow | 10 passed / 77.17 s | `owners-after-v1.log` |
| 受影响源码与测试 Ruff | exit 0 | `owners-ruff.log` |
| 归档载体修正后全仓 Ruff | exit 0 | `owners-full-ruff-after.log` |
| Git diff whitespace 检查 | exit 0 | `owners-diff-check.log` |
| 普通未插桩整组 pytest | **383 passed / 754.36 s，exit 0** | `full-owner-after-v1.log` |
| 原失败时的同一 381 条集合，独立普通复跑 | **381 passed / 445.47 s，exit 0** | `original381-after.log` |

普通整组命令为仓库原 venv 下的：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.venv\Scripts\python.exe -m pytest --basetemp=.work/0.1.0-software-completion-20261101/full-owner-after-v1 -o cache_dir=.work/0.1.0-software-completion-20261101/full-owner-after-v1-cache -q
```

它没有调试器、pytest 插件插桩或对象全量扫描。定向测试和普通整组均是
offscreen 软件验证，不能称为物理桌面、设备或硬件验证。

为核对时序敏感性，另一轮仅不收集新增的 `test_plot_owner_lifecycle.py` 两项，
保留原先 `full-after` 失败时的所有 381 条测试及原顺序。
`original381-collection-equivalence.json` 对比两份 collection 日志，确认 nodeid
与顺序完全相同。该轮独立记账，不能当作新的 383 项完整运行。

```powershell
.venv\Scripts\python.exe -m pytest --ignore=tests/integration/test_plot_owner_lifecycle.py --basetemp=.work/0.1.0-software-completion-20261101/original381-after -o cache_dir=.work/0.1.0-software-completion-20261101/original381-after-cache -q
```

## 保留的诊断过程

拆分前置组分别为 59 passed / 477.47 s、85 passed / 327.16 s、15 passed /
50.24 s；全仓收集后单独选择原故障用例为 1 passed、380 deselected / 69.52 s。
这些结果不能拼成一次完整测试，也没有据此声称故障已修复。
参数树与图例探测没有发现相应新生命周期缺陷，没有据猜测改动这些组件。

为尝试获取原生调用栈，从 Microsoft 官方 NuGet 下载 DbgEng
`20260319.1511.0`，仅放在本轮 `.work/debug-tools` 中，DLL Authenticode
验证为 Microsoft Corporation 有效签名。包 SHA-256 为
`875678516f9ceed4a1c8b9b106d165106fcaa38723ad7c584c47b95b231600de`。
使用已有 MinGW 编译任务专用 launcher，没有安装系统调试器、改注册表或
系统调试设置，没有附加到用户的其他进程。

- 最初默认 debug-heap 运行过慢，精确停止自有进程并保留停止记录。
- no-debug-heap 的诊断脚本启动完整组得到 **381 passed / 600.32 s**；该脚本
  及 `-v` 输出改变了启动与回收时序，只作为诊断结果。
- 后续按普通 `-m pytest -q` 启动并附加到指定子进程的尝试，在协调者要求
  实施已证明的修复后停止。PID/命令/原因在 `native-attach-stopped.json`；
  它是部分运行，不是完整通过。debugger 正常结束的 exit 0 也不是 pytest 通过。
- 可选 Python PDB 包下载完成，但 7-Zip 参数错误导致提取未完成，未用于任何
  原生分析结论。该工具设置问题与应用测试结果分开记录。

本批次没有捕获到原始堆异常的原生破坏指令或 crash dump，因此不能把
`ntdll` 检测地址解释为具体源码根因。已证明的是上述 Qt 生命周期违例及
修复边界。修复后两轮普通运行均完成并且没有复现历史堆异常，其中第二轮与
先前失败的测试集合、顺序一致。没有把诊断运行或若干定向通过拼成整组通过。
本修复所需的软件回归已经完成；原生破坏指令未定位这一证据限制仍保留。

Qt 官方要求跨线程对象销毁使用其所属线程的事件循环，原生父子对象树
决定 QObject 生命周期：[Threads and QObjects](https://doc.qt.io/qt-6/threads-qobject.html)。
诊断工具来源为 [Microsoft DbgEng package](https://www.nuget.org/packages/Microsoft.Debugging.Platform.DbgEng/20260319.1511.0)。

## 原始执行快照与重放

`.py.txt` 是实际执行过的临时诊断脚本的逐字节快照，不是维护中的生产或正式
重放入口。`raw-snapshot-carriers.json` 保存原执行路径、载体路径、字节数和
SHA-256；只改变归档载体的扩展名，没有改写原执行字节。上级目录原清单保存在
`evidence-manifest-before-carriers.json`。未扩大 Ruff 排除项；正式源、测试和
维护中的工具继续接受整仓 Ruff。

正式可重复的边界验证使用仓库测试，仍属于 Ruff/pytest 范围：

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_plot_owner_lifecycle.py tests/integration/test_release_plot_lifecycle.py tests/integration/test_plot_ui_i18n.py -q
```

审阅历史原始探测时，应在源版本与环境核对后的独立 checkout 中，使用从未
存在的新临时目录。例如当前仓库的独立版本目录可按下列方式运行原失败任务
生命周期探测；同一脚本对修复前和修复后源码的结果不同，应同时记录当前 HEAD
及脏树源码哈希，不能沿用旧结果身份：

```powershell
if (Test-Path .work/0.1.0-heap-replay-20261101) { throw 'Use a new owned replay directory' }
New-Item -ItemType Directory .work/0.1.0-heap-replay-20261101 | Out-Null
Copy-Item docs/evidence/software_completion_20261101/heap-lifecycle/owners-v2/window_orphan_failure_probe.py.txt .work/0.1.0-heap-replay-20261101/window_orphan_failure_probe.py
.venv\Scripts\python.exe .work/0.1.0-heap-replay-20261101/window_orphan_failure_probe.py
```

脚本使用两级目录深度定位仓库，因此这里保持 `.work/<版本目录>/<脚本>`。
它只在该新目录写设置、探测记录和生成材料，默认 offscreen，不操作硬件。
其余原始诊断脚本含各自的固定输出名和特定基线说明，应先审阅快照，逐份在
独立目录重放；它们不替代上面的正式回归与普通完整套件。
