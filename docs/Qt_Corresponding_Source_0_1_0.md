# Qt/PySide 对应源码准备与候选交付计划

本轮只准备材料，没有下载以下源码归档、Qt SDK，没有重编译或发布。用户已选择原创
项目代码采用 Apache-2.0；根 LICENSE 与 SilverStar 标准文本的 Git blob 一致：
`d645695673349e3947e8e5ae42332d0ac3164cd7`。未新增个人版权行或空白项目版权声明。
Apache 附录中的示例不是实际署名，第三方版权和许可原样保留。

## 精确版本与目前证据边界

已过滤目录中 14 个 Qt6 DLL 的 ProductVersion 全部为 `6.11.1.0`；PySide6、Essentials、
Addons、Shiboken 的分发版本均为 `6.11.1`。实际 Qt 构建信息为 Windows AMD64、
MSVC 2022、shared/dynamic、release。PySide wheel 标签是 `cp310-abi3-win_amd64`，
当前 Python 运行时为 3.14.0。55 个 Qt/绑定/插件/运行文件与已安装供应商文件字节一致。
文件路径、大小、SHA-256、PE 版本及对应 wheel RECORD 线索在
`third_party/qt-6.11.1/binary-inventory.json`。

已取得精确 `v6.11.1` 标签的源版本归属目录：95 条组件记录、56 份被引用的许可文档，
以及相关模块 LICENSES/REUSE 原文，出处与哈希逐项保存。部分条目是特定平台或编译选项
才使用的组件；**这是一份源版本目录，不是此 Windows wheel 已编译组件的结论性 SBOM**。
当前安装材料中没有找到与本 wheel 精确匹配的供应商构建 SBOM/完整构建配置。

Qt PDF 的 PDFium/Chromium 嵌套内容没有由上述小目录完整覆盖；Mesa 软件 OpenGL 等
额外运行文件也须按供应商构建材料核对，不能用相近 Qt SDK 的 SBOM 假充匹配。
[Qt 的 SBOM 文档](https://doc.qt.io/qt-6.11/sbom.html)说明它与平台和构建配置有关。

## 需要准备的精确版本源码

以下字节数来自官方归档 HEAD 和镜像元数据；已记录公布的 SHA-256，**尚未下载正文，
因此没有宣称验证了归档正文或完成对应源码交付**。完整 URL/校验值见
`third_party/qt-6.11.1/corresponding-sources.json`。

| 归档（均为 6.11.1 tar.xz） | 用途 | 压缩字节 | 约 MiB |
| --- | --- | ---: | ---: |
| qtbase-everywhere-src | Core/Gui/Widgets/Network/OpenGL/Test 及平台、TLS 等插件 | 50,648,500 | 48.30 |
| qtdeclarative-everywhere-src | 仍分发的 QML/Quick 系列 DLL | 38,744,644 | 36.95 |
| qtsvg-everywhere-src | SVG 库及插件 | 2,336,944 | 2.23 |
| qtimageformats-everywhere-src | 实带图像格式插件 | 2,032,792 | 1.94 |
| qttranslations-everywhere-src | 实带 QM 翻译数据的来源 | 1,684,616 | 1.61 |
| pyside-setup-everywhere-src | PySide6、Shiboken、生成和构建脚本 | 17,963,432 | 17.13 |
| qtshadertools-everywhere-src | 构建时可能需要，须与原构建配方核对；不冒充实带 DLL | 1,216,568 | 1.16 |
| qtwebengine-everywhere-src | Qt PDF/qpdf 及其源码依赖；不是整套 SDK | 578,914,356 | 552.10 |

合计 693,541,852 字节，约 **661.41 MiB**；其中除 qtwebengine 外约 109.32 MiB。
解压大小尚未测量，不能据压缩大小承诺所需磁盘。来源为
[Qt 分模块官方目录](https://download.qt.io/official_releases/qt/6.11/6.11.1/submodules/)和
[Qt for Python 官方目录](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/)。
这些来源替代整套 SDK 下载，但本身仍须确认完整对应关系、必要构建脚本和配置。

## 提供方案与最小剩余阻塞

建议将经核验的对应源码作为独立的源码资产，与二进制放在同一发布记录中；保留原
压缩归档和 SHA-256，不为检查而整套解压，也不把大归档提交进源码 Git。
另一方案是经审查建立持续可用、明确关联二进制版本的源码托管/获取安排。
这两者目前都是准备方案，不是已经履行的交付或已发出的书面提供承诺。

不能仅放一个 Qt 首页、最新版链接或无责任保证的第三方链接就写“LGPL 已完成”。
需确认源码确实对应所分发库，含必要修改/构建材料；选择的访问方式还要满足适用许可
的完整性、清晰指引和持续提供要求。见本仓库保留的 LGPLv3 第 4 节、GPLv3 第 6 节和
[Qt 的官方义务说明](https://www.qt.io/development/open-source-lgpl-obligations)。

当前最小剩余阻塞为：

1. 与所分发库匹配的源码/构建材料及归属证据，含 Qt PDF、Mesa。可以是匹配 SBOM 或
   等效材料，并非强制某一种文档形式；当前证据不足以作出完整对应性结论。
2. 是否保留现有 PDF 图像读取插件并接受约 552 MiB 的主要源码资产，或另行决定评估
   更小的分发范围。本轮没有悄悄移除 PDF、QML/Quick 或其它已分发功能。
3. 确认约 661.4 MiB 源码资产的实际托管/提供方案，再获取正文、验证公布的哈希并完成
   对应关系检查。未经这些步骤，不宣称已可公开发布。
4. PySide 的纯 Python 部分在 PYZ 中，最终交付还需验证重新冻结/替换流程，不能只说
   “DLL 可替换”就把全部绑定层义务视作完成。

## 独立候选计划

已验证运行目录仍是任务目录内 `license-filtered/Underline_RETLDC`，不覆盖原 PlotSVG。
补齐本轮 LICENSE、声明和材料后，先作为用户功能验收目录；只有完成上述材料与公开
发布确认后，才生成新的命名 ZIP/校验和，并分别记录冻结源码提交和打包文档提交。
EXE 可复用既有字节；许可/说明更新无需重新 PyInstaller。若再改运行组件，须针对变化
验证。当前 317/189 项通过证据保留，本轮不无谓重复全量运行。

动态库和绑定层替换边界见 [替换说明](Qt_Library_Replacement_0_1_0.md)。
