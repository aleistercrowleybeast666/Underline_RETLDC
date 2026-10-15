# UNDERLINE 0.1.0 许可与仓库核查

核查日期：2026-10-15。本轮仅修改许可、说明和打包时许可文件的收集，不改变应用功能。
最新 PlotSVG 仍为待用户验收候选；没有用户已验收该候选的结论。

## GitHub 与本地

- GitHub `main`：`3c4e436cc0072c0a3f33c068d3a9bb6df1a43fa7`，与本地 `main` 一致。
- 核查开始时，本地 `feature/v0.1.0-theory-overlays` 为 `0d9d07b`，领先 main 23 个提交，
  涉及 70 个文件；这批本地功能和验收记录尚未出现在 GitHub main。
- 最新公开 Release 是 [v0.0.4](https://github.com/aleistercrowleybeast666/Underline_RETLDC/releases/tag/v0.0.4)，
  发布于 2026-09-11。没有公开 v0.1.0 Release。
- 本地/远端根目录都没有 LICENSE/COPYING/NOTICE，pyproject 没有项目 license 字段。
  所有可见本地分支历史未发现项目自身许可证；唯一既有许可文本是 pyqtgraph 的 MIT。
- `.agents` 和已知本机 `memory_summary.md` 路径不存在；个人上下文服务不可用。
  因此没有可据以沿用的、已确认的 UNDERLINE 项目授权选择。

以上为只读核查；未更改远端 main、tag、Release 或下载资产。

## 确定问题与本轮修复

README 原来指向旧 CompactResults ZIP。本轮改为区分公开 v0.0.4 下载和本地待验收
PlotSVG 候选，提供现有 Releases 入口；没有捏造 v0.1.0 下载链接。

PlotSVG ZIP 的 558 个文件中有 NumPy 许可树、pyqtgraph MIT 和 CET 色图许可；未见
Python LICENSE、SciPy 许可、PySide6/Shiboken 主许可文本或根第三方声明。
这与“目录中的 Qt 许可未变”不是同一结论：不能据目录未改推断许可已经完整。

新增 `THIRD_PARTY_NOTICES.txt`，明确只描述第三方，不为项目新增授权。
新增打包许可收集步骤：从正在打包的环境逐字节复制 Python、NumPy、SciPy、pyqtgraph、
PySide6/Essentials/Addons、Shiboken 和 PyInstaller 原有许可文件，保存版本/路径/SHA-256
清单；同时复制将来由权利人正式选定的根许可证。现有 pyqtgraph MIT 不改写。
GNU LGPLv3、GPLv3 和 OpenSSL 3.0.18 Apache-2.0 文本保存在 `docs/third_party/upstream`，
出处及哈希见 `sources.json`。GPLv3 原文取自本机 NumPy 2.5.2 许可文件的完整末段；
保留正文和附录，未把 NumPy/GCC 的许可扩展为项目许可。

## 不能由本轮代选的事项

1. **项目自身许可证及署名。** 需权利人明确许可证名称/版本、适用范围和署名主体；
   不能因源码公开或存在第三方 MIT 就替项目选 MIT/GPL，也不生成占位 LICENSE。
2. **Qt 分发路线和 Virtual Keyboard。** 当前候选实际包含 `Qt6VirtualKeyboard.dll` 和
   `plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll`。
   [Qt 6.11 官方说明](https://doc.qt.io/qt-6.11/qtvirtualkeyboard-index.html)将其列为
   GPLv3 或商业许可，不能用 PySide 的 LGPL 概述覆盖。需明确商业授权依据，或决定采用
   适合的 GPL 路线。随后已确认业务不依赖该模块，在独立新目录实施最小打包排除和
   验证；旧 PlotSVG 保留。该排除不替项目自身选择许可证，也不免除其余 Qt 的义务。
3. **所选 Qt 路线的实际材料。** LGPL 路线涉及对应库源码、安装/替换信息等，单有文本
   和上游网址不足以宣称完成。Qt PDF、图像插件、字体等嵌套归属需按实带二进制版本
   核对；当前清单不是完整 Qt SBOM 或许可合规证明。
4. 当前包另含 OpenSSL 3.0.18 与 3.6.4 两组二进制，以及 Windows/VC 运行库。已补的
   OpenSSL 文本属于已核实的 3.0.18 来源；第二组及其它嵌套 notices、运行库再分发材料
   仍待核实。不存在的 NOTICE 下载路径未被当作许可文件或成功证据。

Qt 主许可及其嵌套组件各有条件，见[官方许可说明](https://doc.qt.io/qt-6/licensing.html)、
[第三方列表](https://doc.qt.io/qt-6.11/licenses-used-in-qt.html)和
[LGPL 义务](https://www.qt.io/development/open-source-lgpl-obligations)。
PyInstaller 的 bootloader 例外允许应用采用适合的许可，
[不会自动把应用变成 GPL](https://pyinstaller.org/en/stable/license.html)。本轮也未选择项目许可。

## 包影响与验证

现有 PlotSVG 目录、ZIP、校验和与旧候选全部保留，没有被本轮许可材料原地覆盖。
其 189 项功能检查是上一轮的自动验证，不能表述为本轮用户验收或许可放行。

仅补许可/说明时，可以保留相同 EXE 字节，重新封装 ZIP 并更新 BUILD_INFO/校验和，
不需要重新运行 PyInstaller。若决定排除 Qt 组件，则必须验证新运行目录的启动、输入法、
导出等依赖行为后再封包。旧公开 v0.0.4 也需单独审核其实际依赖/许可，不以本轮本地
0.1.0 检查替代，更不自动替换既有 Release 资产。

本轮许可收集实测 33 份文件，版本清单与逐项哈希核验通过，材料合计 308937 字节；
另验证了 3 个源目录覆盖目标会在写入前拒绝。Ruff 和 `git diff --check` 通过。
该轮完整 pytest 已回收到终态：317 项通过，退出码 0，用时 346.23 秒，无遗留测试。
PlotSVG EXE 与 ZIP 哈希仍与上一轮一致。没有运行新 PyInstaller 构建或发布。
过程继续使用 `D:\Temp\Underline_RETLDC_v010_validation\plot-chinese-work` 下的小目录。

## 后续最小排除验证

后续授权允许在业务完全不用时修复多收集的打包组件。只读 PYZ、全部 DLL/PYD 导入表、
业务源码和 PyInstaller 钩子后，确认实际绑定是 PySide6 6.11.1，无 PyQt 模块。
`Qt6VirtualKeyboard.dll` 唯一 PE 引用者是 `qtvirtualkeyboardplugin.dll`；业务无相应引用、
冻结包无对应 Python 包装模块，QtGui 钩子会把整个 platforminputcontexts 类别收集进来。
因此只在新打包输出排除上述两个文件，不修改供应商安装或源码。

剩余 Qt 模块与实际冻结 Python 依赖的核对、可选许可路线及实物证据见
[Qt 运行依赖核查](Qt_Runtime_Licensing_0_1_0.md)。这是限定模块范围的审计，仍不宣称
完整嵌套 SBOM、对应源码材料或项目自身许可已经解决。现有 PlotSVG 保持原字节。
