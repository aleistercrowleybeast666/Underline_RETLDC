# Underline 本轮交付（2026-11-17）

源码提交：[df9446f](https://github.com/aleistercrowleybeast666/Underline_RETLDC/commit/df9446f1db40ced01d24d76e466013123dd28796)。沿用 `codex/release-candidate-20261103`，保留既有五工作区、科学处理、导出插件和事务流程。

关闭及其他有父窗口的确认框现在按所属窗口与屏幕可用区域居中，使用 Qt 逻辑尺寸。取消仍保留工程。启动入口取消了一次重复主题初始化；没有延后科学计算校验或改变默认参数。

验证：全量 pytest **421 通过**，Ruff 通过；正式 `打包.bat` 又完整执行 **421 项**和 Ruff，随后新生成 EXE 的亮色、暗色 smoke 均成功。150% 缩放的真实 Qt 模态框居中/取消测试通过。命令及完整日志见本目录压缩日志、[打包收据](package-receipt.json)。这些 GUI 检查使用 offscreen，不作为物理显示器验证。

新便携交付位于：

`D:\python_software\Underline_RETLDC\dist\platform_finish_20261117\Underline_RETLDC_platform_finish_20261117_Windows_x64.zip`

SHA256：`fd187372111ebe2158f239dcc93f0200dace1ad95cc6bfa92a3dfd08e6f32a0c`。解压后运行 `Underline_RETLDC\Underline_RETLDC.exe`，请保留完整文件夹。源码运行为 `.venv\Scripts\python.exe main.py`。

使用实际 CLI、既有导出插件和仓库内明确标为 synthetic 的试验工程，新导出了 `underline.motor-test-package/1` 包。其文件 SHA256 为 `66c6232d0ccec6ceaabdec9186e9059a2f16dc9eeedea0c94221f06a8ceaed96`。TreeDiagram 新 wheel 已实际导入、仿真并导出参数；数据不是硬件试验实测结果。

未完成项：当前电脑的 Computer Use 原生抓屏辅助进程返回 `Computer Use helper already has an active request`，因此本轮没有完成便携包的原生桌面视觉复验，也不宣称解决了物理显示链路问题。工具已退出。硬件项另列：真实传感器单位/标定、测量精度、发动机试验真实性均未在本轮采集证据。

原有发布包未覆盖。用户原有未跟踪文件 `docs/Repository_Showcase_Review_20261016.md` 保留，SHA256仍为 `482606c54b1ae66f2a721267c3dcf6eed8b82c08d7e08a8fbe0e61e286d5ce2a`。当前任务生成目录有独立标签；旧 `.work`、用户工程和源数据不在清理范围。

本轮清理已执行：逐项核对绝对路径、无链接/联接、文件数和 SHA256 后，仅删除上述新任务的可再生产物，共 16 个文件、51389317 字节。Underline 对应本次 PyInstaller 中间目录；TreeDiagram 对应本次独立 wheel 安装验证副本。正式 dist、验证输入/结果、完整日志和历史输出保留。完整记录见 [清理清单](cleanup-inventory.json) 与 [执行结果](cleanup-result.json)。
