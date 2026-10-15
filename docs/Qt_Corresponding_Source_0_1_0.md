# Qt/PySide 对应源码与本地候选

项目原创代码采用标准 Apache-2.0；根 LICENSE 与 SilverStar 的标准文本 Git blob
相同：`d645695673349e3947e8e5ae42332d0ac3164cd7`。没有新增个人版权行；附录示例
不作为项目版权声明。第三方库保留自己的授权。

## 新候选的实际模块范围

新输出保留 8 个 Qt6 DLL：Core、Gui、Widgets、Network、OpenGL、OpenGLWidgets、Svg、Test。
版本为 6.11.1.0；PySide6/Essentials/Addons/Shiboken 为 6.11.1，Windows AMD64、
MSVC 2022、shared release、cp310-abi3，Python 3.14.0。文件与供应商 wheel 的对应证据在
`third_party/qt-6.11.1/binary-inventory.json`。

排除 Virtual Keyboard 两文件、PDF 读图插件/库和孤立的 QML/Quick 闭包七文件，合计九个。
正常/延迟 PE 导入、业务 API、PYZ 和资源检查支持该边界；写出图像格式全部保留，读入格式
仅少了 PDF。后七文件合计 17,865,864 字节。规则已加入 `打包.bat`，详见
`third_party/qt-6.11.1/optional-runtime-exclusions.json`。

因此旧八归档 **661.4 MiB** 计划已被取代；新候选不需要 qtwebengine、qtdeclarative、
qtshadertools。旧 PlotSVG 包原字节保持不变。冻结 GUI 在九文件排除后 189 项通过；
后续 FFT 小修的冻结版本与验证另记于 `FFT_Apache_Acceptance_0_1_0.md`。

## 五份官方精确版本源码

以下 6.11.1 原始 tar.xz 归档各保留一份，不放入 Git、不展开 SDK；最终移入单一源码 ZIP，保留原 tar.xz 成员字节。
正文大小及 SHA-256 必须均匹配官方镜像元数据，才标记为下载完成。执行状态、完整 URL、
哈希和本地路径见 `third_party/qt-6.11.1/corresponding-sources.json`。

| 归档 | 对应范围 | 压缩字节 |
| --- | --- | ---: |
| qtbase-everywhere-src | 7 个 Qt Base 库、平台/TLS 等插件及源码依赖 | 50,648,500 |
| qtsvg-everywhere-src | SVG 库与插件 | 2,336,944 |
| qtimageformats-everywhere-src | 保留的图像格式插件 | 2,032,792 |
| qttranslations-everywhere-src | QM 翻译数据与生成材料 | 1,684,616 |
| pyside-setup-everywhere-src | PySide6/Shiboken，生成与构建脚本 | 17,963,432 |

合计 **74,666,284 字节（71.21 MiB）**，低于用户批准的 750 MiB 上限。来源为
[Qt 官方分模块目录](https://download.qt.io/official_releases/qt/6.11/6.11.1/submodules/)
与 [Qt for Python 官方目录](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/)。
截断响应在同一 `.part` 续传；未通过完整正文哈希的临时文件不算交付源码。

归档采用流式 tar 读取检查版本/构建/许可材料，不展开源码树。检查结果在
`third_party/qt-6.11.1/archive-inspection.json`。此前精确 v6.11.1 固定 tag 材料含
95 条归属元数据和 56 份引用许可，涵盖条件构建和其他平台内容，是源码版本目录，
不是这个 Windows wheel 的最终 SBOM。

## 实际证据边界与待发布事项

五归档是当前 Qt/PySide 模块的官方发行源码集合，不自动证明供应商每个二进制/嵌套
组件的完整构建对应关系。本地 wheel 没有匹配的供应商构建配置/SBOM；不能用邻近 SDK
的 SBOM 替代。[Qt SBOM 文档](https://doc.qt.io/qt-6.11/sbom.html)说明其依赖具体构建。

软件 OpenGL 的代码图像已与 Qt 官方两份历史 Mesa 11.2.2 包匹配；
Mesa 11.2.2 官方源码、许可证和 721 段原始版权块，以及 LLVM 3.6.2 主许可/嵌套版权
已实物取得并保留，见 `third_party/software-opengl/manifest.json`。这是一份保守源码级
版权清单，不把其中每项都说成编译进 Windows 库的组件。
Windows/VC 运行库也按供应商条款单独核对。不能把这些归属问题隐藏在“已下载 Qt 源码”中。

Qt DLL/PYD 是外部动态库，但部分 Python 绑定在 PYZ 中。仓库与 pyside-setup 提供
生成/构建/冻结脚本；Python 库部分重新组合并运行完整 GUI 的验证已通过；C++ 库没有重新编译，操作边界见
[库替换说明](Qt_Library_Replacement_0_1_0.md)。

源码当前仅本地保存，未公开托管、上传或作出长期书面提供承诺。公开发布前仍需确定
实际可获的二进制、匹配源码、必要构建信息和许可材料的提供方式。文件清单、源码下载
或 GUI 通过均不单独构成完整法律合规证明。没有推送、打 tag 或发布 Release。

## 最终源码提供方案

计划 Release 附带 `Underline_RETLDC_0_1_0_Corresponding_Sources.zip`：五份 Qt/PySide
原始压缩归档、补充的 Mesa 11.2.2 官方固定提交源码、精确应用源码快照、重组工具及
许可证据均在其中。原 tar.xz/gz 字节不改，不再次展开 SDK。校验完成后只保留 ZIP 中
唯一一套归档，不在 D 盘留下重复源码。每个成员的大小/哈希在 `SOURCE_MANIFEST.json`。

拟随同一 `v0.1.0` Release 上传二进制 ZIP、源码 ZIP 和 SHA256SUMS。现在没有上传，
不能把计划 URL 当成已提供；实际发布授权及资产上传完成后才算该提供方案已执行。
这是一份交付包方案，不额外作出三年书面提供承诺。
