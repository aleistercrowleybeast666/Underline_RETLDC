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

以下 6.11.1 原始 tar.xz 归档各保留一份，不放入 Git、不展开 SDK、不再套重复源码 ZIP。
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

仍保留的软件 OpenGL `opengl32sw.dll` 含 Mesa 11.2.2、LLVM 3.6.2 版本字符串，
不是 Qt 6.11.1 模块源码的一部分；精确供应商构建归属及嵌套版权材料仍需补齐。
Windows/VC 运行库也按供应商条款单独核对。不能把这些归属问题隐藏在“已下载 Qt 源码”中。

Qt DLL/PYD 是外部动态库，但部分 Python 绑定在 PYZ 中。仓库与 pyside-setup 提供
生成/构建/冻结脚本；修改绑定后的重建、重冻结仍未实测，操作边界见
[库替换说明](Qt_Library_Replacement_0_1_0.md)。

源码当前仅本地保存，未公开托管、上传或作出长期书面提供承诺。公开发布前仍需确定
实际可获的二进制、匹配源码、必要构建信息和许可材料的提供方式。文件清单、源码下载
或 GUI 通过均不单独构成完整法律合规证明。没有推送、打 tag 或发布 Release。
