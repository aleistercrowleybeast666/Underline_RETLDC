# Qt/PySide 动态库替换与重新冻结说明

本说明支持用户调试和修改第三方库，不替代 LGPL/GPL 的完整条款，也不表示对应源码
已经交付。项目原创代码的 Apache-2.0 不取消 Qt/PySide/Shiboken 的原有权利。
不得以产品条款限制适用 LGPL 所保护的库修改或为调试该修改而进行的逆向工程。

## 实际位置和兼容条件

程序采用 PyInstaller onedir，Qt/绑定为外部共享文件，不在 EXE 中静态链接：

- Qt：`_internal/PySide6/Qt6*.dll`；插件：`_internal/PySide6/plugins/`。
- PySide 绑定：`_internal/PySide6/pyside6.abi3.dll` 与相应 `Qt*.pyd`。
- Shiboken：`_internal/shiboken6/shiboken6.abi3.dll`、`Shiboken.pyd`。
- Qt 翻译：`_internal/PySide6/translations/`。

当前 ABI/平台为 Windows x64、MSVC 2022、Qt/PySide 6.11.1 shared release，
绑定 wheel 为 cp310-abi3。替换件须保持兼容接口和一致的模块集合；不要混入 x86、
Linux、debug 构建或不匹配的 Qt/PySide/Shiboken 组合。系统运行库另有其许可要求。

## 在运行副本中替换

关闭该副本程序后，在独立运行副本中放入从对应源码构建的兼容修改库，保持上述路径。
一并提供匹配插件/依赖，Qt 插件必须与 Qt 版本和构建兼容。保留经过验证的原分发目录，
不要直接修改项目 `.venv`、全局 Qt、原 PlotSVG 或测量数据。

应用没有新增 Qt DLL 白名单锁或库签名限制；本次 SHA-256 是发布核验记录，不是阻止
用户加载修改库的应用检查。测量源文件的 SHA-256 校验仍必须保留，不能借库替换关闭
它，不能改原始数据、时间戳、单位或工程科学配置来使检查通过。

替换后检查启动、普通输入/中文输入、绘图、语言、PNG/CSV/SVG 等实际使用路径。
修改件的结果应有自己的验证记录，不能沿用原二进制的通过结论。当前测试只证明原
供应商库及两文件排除目录正常，不证明任意修改库都兼容；真实 Windows IME 人工
验收尚未进行。

## PYZ 中的 Python 绑定部分

PySide6/shiboken6 的部分 Python 包代码在 EXE 的 `PYZ.pyz` 内，单独放一个新 `.py`
文件不保证能覆盖冻结导入器。若修改这些部分，需要可验证的重新冻结/重组路径。
应提供精确应用源码提交、对应 PySide/Shiboken 源码、构建/打包脚本与所需配置，使
使用者能重新组合修改后的库，而不是只给 DLL 路径。

仓库已有 `打包.bat` 和许可收集脚本；PySide 对应源码含构建/生成脚本，模块子集是
Core、Gui、Widgets、Network、OpenGL、OpenGLWidgets、Svg、Test。
但本轮没有构建修改版绑定并重冻验证，因此这仍是交付前待核对项，不能声称仅有脚本
名称或上游链接就已经满足全部替换/对应源码义务。

本文件没有发出长期源码提供承诺。待完成的材料、精确来源/体积和候选计划见
[对应源码准备](Qt_Corresponding_Source_0_1_0.md)。
