# 最新范围：九文件排除

下文保留之前仅排除 Virtual Keyboard 的阶段证据（14 个 Qt DLL、528 个运行文件）。
新候选追加排除未使用的 qpdf/Pdf 及孤立 QML/Quick 七文件；保留 8 个 Qt DLL，其他
521 个运行文件仍与原 PlotSVG ZIP 一致。新规则的九文件精确清单、正常/延迟 PE 引用
关系见 `third_party/qt-6.11.1/optional-runtime-exclusions.json`。业务无 PDF/QML API、
对应 Python 包装或 QML 资源；原有图像写出格式完全不变，读图仅少 PDF。

这次七文件精简后，中/英文冻结启动均退出 0，完整 GUI 189 项通过。官方对应源码从
旧八归档 661.4 MiB 降为五归档 71.21 MiB；实际下载/校验状态和剩余供应商归属边界见
[对应源码](Qt_Corresponding_Source_0_1_0.md)。原包及安装库未改。后续 FFT/范围改动
需要新冻结验证，不冒用此前相同 EXE 的结果，详见 `FFT_Apache_Acceptance_0_1_0.md`。

## 前一阶段原始记录

# Qt 运行依赖与最小排除验证

核查对象：原 PlotSVG ZIP（SHA-256
`3f2aee2e374f4d97372daf0944dad2ab608b4815b24184d1e054dcf2828119a9`）。
EXE SHA-256 为 `1db99b981f4000c5fff0afef3a422ea764710eee3bfe836f230228cdf6a6a816`。
本轮没有更换 Qt 绑定、修改全局 Qt、删除供应商源码或选择项目自身许可证。

## 两条可行路线

1. 排除业务不使用的 Virtual Keyboard 多收集文件，对剩余 PySide6/Qt 完成适用的
   LGPLv3 义务和嵌套归属材料；项目自身许可仍由权利人选择，不能把 Qt 改标为 MIT。
2. 保留 Virtual Keyboard 时，需满足其 GPLv3 路线，或有适用的 Qt 商业授权。
   两者不能仅靠拷贝 LGPL 文本替代，也不能据此默认替 UNDERLINE 选 GPL。

项目自身许可随后已按用户决定采用 Apache-2.0，暂不新增个人版权行。当前实施路线 1
的打包排除部分；剩余 Qt 对应源码等材料见
[准备与候选计划](Qt_Corresponding_Source_0_1_0.md)，不能由项目 Apache 取代。

## 实物依赖

源码依赖、实际 pyqtgraph 选择、EXE 的 `pyi_rth_pyside6`、PYZ 以及 8 个 Qt `.pyd`
共同确认绑定为 **PySide6 6.11.1**；未找到 PyQt 模块或运行时钩子。
原目录有 15 个 Qt6 DLL。模块级许可对应如下（官方 6.11 文档目前展示 6.11.2，
实际二进制为 6.11.1；这不是精确构建的完整 SBOM 证明）：

| 实带模块 | 许可依据与结论 |
| --- | --- |
| Core、Gui、Widgets、Network | [Qt Core](https://doc.qt.io/qt-6.11/qtcore-index.html)、[GUI](https://doc.qt.io/qt-6.11/qtgui-index.html)、[Widgets](https://doc.qt.io/qt-6.11/qtwidgets-index.html)、[Network](https://doc.qt.io/qt-6.11/qtnetwork-index.html)：提供 LGPLv3 路线，不是 GPL-only。 |
| OpenGL、OpenGLWidgets | [Qt OpenGL](https://doc.qt.io/qt-6.11/qtopengl-index.html)及 Qt Base 模块许可；提供 LGPLv3 路线。 |
| Svg、Test | [Qt SVG](https://doc.qt.io/qt-6.11/qtsvg-index.html)、[Qt Test](https://doc.qt.io/qt-6.11/qttest-index.html)：提供 LGPLv3 路线。 |
| Qml、QmlMeta、QmlModels、QmlWorkerScript、Quick | 属于 [Qt QML](https://doc.qt.io/qt-6.11/qtqml-index.html)/[Quick](https://doc.qt.io/qt-6.11/qtquick-index.html)；提供 LGPLv3 路线。本轮不顺带裁剪这些文件。 |
| Pdf | [Qt PDF](https://doc.qt.io/qt-6.11/qtpdf-index.html)明确提供 LGPLv3 路线，不是 GPL-only。保留 PDF 图像插件。 |
| VirtualKeyboard | [官方说明](https://doc.qt.io/qt-6.11/qtvirtualkeyboard-index.html)：GPLv3 或商业。原包中唯一发现的模块级 GPL-only 开源选项。 |

翻译数据另核对了精确 v6.11.1 的 `qttranslations/licenseRule.json`：默认文件类别包含
LGPLv3 替代选项，`.pl` 工具另列 GPLv3 加 Qt 例外。不能仅因该仓库 LICENSES 文件名
列表没有 LGPL 就把实带 QM 数据判成 GPL-only；规则和翻译 README 原文已保留。

全部打包 DLL/PYD 的静态导入表中，VirtualKeyboard 唯一引用者是输入插件。
源码没有 VirtualKeyboard/QML 输入功能，PYZ 没有其 Python 包装器。PyInstaller
`utils/hooks/qt/_modules_info.py` 把 `platforminputcontexts` 挂在 QtGui，
`collect_plugins()` 收集该类别全部插件，解释了它的进入路径。

原 PYZ 还含 pytest、pluggy、iniconfig、colorama、packaging、Pygments、setuptools，
除去标准库与本项目，映射到 14 个运行期 Python 分发包。可见声明为 MIT/BSD/Apache
或 LGPL/GPL 替代选项，没有发现另一个纯 GPL 的 Python 运行包。NumPy/SciPy 中的
GCC GPL 文本带运行库例外；PyInstaller 的 bootloader 也有例外，不能按字符串包含 GPL
判为应用必须 GPL。许可收集扩展到这些实带包及 setuptools 的供应商文本，合计 58 份。
Qt、PDF 等更深层依赖仍按总核查报告待补，不能将此结论扩大成全面许可放行。

## 最小变更与验证目录

新运行目录仅排除：

- `_internal/PySide6/Qt6VirtualKeyboard.dll`，443192 字节，SHA-256
  `e8db083111dc264c80c81920c882ed1c2c28043edffa988894e0a82723b2aa4b`。
- `_internal/PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll`，33592 字节，
  SHA-256 `d116b216a50037cbfa6ee9afd94bea357cdbee263e0f9b8c6ef2e811da29eb70`。

从原 ZIP 流式提取到新的
`D:\Temp\Underline_RETLDC_v010_validation\plot-chinese-work\license-filtered\Underline_RETLDC`，
没有提取这两个文件；原包、供应商库均保留。不重编译 EXE，不同时制作第二份 ZIP。
未来 `打包.bat` 在新生成目录也作同一两文件排除，并检查排除失败。

新目录的 EXE 和其它运行字节须与原 ZIP 逐项一致；新增内容仅为许可、说明与排除清单。
同一 EXE 在排除目录的完整自动 GUI 验收 **189 项通过，退出码 0**；中/英短启动
各退出 0。短启动各 23 条阶段记录、完整验收 10 条，均到关闭且故障日志为空。
源码输入探针使用新目录的插件路径，ASCII 按键、中文合成提交、负数输入通过；
合成提交不代表真实 Windows IME 人工验收。完整的上一轮 pytest 已回收：317 passed，
346.23 秒，退出码 0。应用/插件源码未改，未为本次两文件排除重新编译 EXE。
逐项核验了其余 528 个运行文件与原 ZIP 字节相同，58 份许可文档哈希一致；
原 PlotSVG EXE/ZIP 和 `.venv` 中两项供应商文件哈希均未变。Ruff、差异检查通过。
既往首次 `0xC0000005` 的根因仍未定位，本轮正常退出不构成根治证明。

过程证据：`qt-license-audit.json`、新目录 `PACKAGING_EXCLUSIONS.json`、
`docs/third_party/runtime/manifest.json`。不推送、不打 tag、不发布。项目自身 Apache-2.0
已确认；约 661.4 MiB 源码提供方案及精确供应商构建材料仍待落实。
