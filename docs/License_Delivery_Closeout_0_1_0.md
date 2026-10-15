# 0.1.0 许可与源码交付收尾

本轮只添加许可、源码提供材料和开发者重组工具，未修改 `src/`、`plugins/`、`main.py`
或已验收 EXE。EXE 保持 SHA-256
`6506a3aeb6378aa092fc46a61d182e4c7c415e52ad1dc3bdb1a2b069dd274113`。
既有 336 项全量测试和 220 项冻结 GUI 结果仍对应同一科学程序。

## 软件 OpenGL

目标为 `_internal/PySide6/opengl32sw.dll`，20,639,544 字节，SHA-256
`4a7d90f91fdecb5df7b426bc2d05974b8d7ffa450af2d1f93f3eca05800718da`。
其 PE 所有节和去掉签名/校验字段后的完整图像，与 Qt 官方 2020、2022 两个 Mesa
11.2.2 签名包一致。两个官方归档本身也已校验发布的 SHA-256；没有把不同签名文件
误说成完整文件哈希相同。图像 SHA-256 为
`d303dd60bbf11418063f4bb72292e481ca1e88d84915fbd049a21666b92c0ee0`。

[Qt 官方归档](https://download.qt.io/development_releases/prebuilt/llvmpipe/windows/)
仅含 DLL，无许可证。先前普通源码入口返回了访问挑战；之后通过官方公开 API 取得
Mesa tag `mesa-11.2.2`，提交 `3a9f6283f435f90ca1a2901be39ec9d629c95bb6`。
实际归档 VERSION 为 11.2.2，`docs/license.html` 与单文件 API 结果逐字节一致。
从源码 `src/` 和 `include/` 保留 721 段原始字节的版权/许可块，补充完整 Boost 1.0。
LLVM 精确为 3.6.2，固定 release_36 提交
`19ade095e8c3ea61f84b71074433309f0c7c7b3b`，CMake 版本号交叉核实；保留 UIUC 主许可、
OpenBSD regex、MD5 和条件 ARM 版权文件。未用较新的 Apache LLVM 条款替代旧版许可。

文件、来源 URL、哈希、归档/图像证明在 `third_party/software-opengl/manifest.json`。
源码版权清单是保守的源文件级超集，不断言其中每一项都编译进这个 Windows DLL；
没有以网站链接替代实际许可证，也没有声称得到供应商最终构建 SBOM。

## Qt/PySide 重新组合验证

从官方 6.11.1 源码中提取 `PySide6.support`，仅添加验证标记，使用新的开发工具
`scripts/reassemble_qt_binding.py` 重组临时 EXE 的 PYZ。其他 1791 个压缩模块和其他
CArchive 条目均独立验证为原字节。修改模块实际执行，完整 GUI 220 项通过、退出 0。
便携示例 `third_party/qt-6.11.1/reassembly_example.py` 另行启动退出 0，确认 marker。
证明在 `third_party/qt-6.11.1/binding-reassembly-proof.json`。

原程序和 `.venv` 未改，原生 DLL/PYD 作为外部共享库加载。未进行新的 C++ 库编译，
不保证任意不兼容 ABI 修改都能工作；这不再是“只有脚本名字、未经验证的 PYZ 替换”。
可执行命令、版本条件和安全边界见 [重组说明](Qt_Library_Replacement_0_1_0.md)。

## 可交付资产与用户动作

准备 `Underline_RETLDC_0_1_0_Windows_Portable.zip`（只更新许可/文档，EXE 不变）和
`Underline_RETLDC_0_1_0_Corresponding_Sources.zip`，另附 `SHA256SUMS_0_1_0.txt`。
旧 FFT_Apache ZIP 与更早候选保留。单一源码 ZIP 内含五份原始 Qt/PySide 6.11.1
归档、补充 Mesa 官方源码、完整跟踪应用源码快照、构建/重组脚本、校验清单和证明。
源码不展开 SDK；完成成员校验后移除任务下载的外部原归档，D 盘只留一套源码内容。

源文件版本、官方校验值及每个归档成员正文哈希全部保留。Mesa API 归档固定提交，
正文 SHA 是实测值，未冒充官方另行发布的校验值。发布方应在同一 Release 同时提供
二进制、源码及校验表，并下载复核；计划链接见 `third_party/SOURCE_ACCESS.txt`。

尚待用户决定/执行：人工 Windows IME 验收（未测）；最终发布动作授权；获授权后
推送、创建 tag/Release 并上传这些已准备的资产，验证公开源码下载和哈希。
没有新的大 SDK 下载、额外环境或工作树；没有推送、打 tag 或发布。材料与可替换路径
已实物准备，不将“尚未取得某种格式的 SBOM”单独当作必须等待的技术动作。
