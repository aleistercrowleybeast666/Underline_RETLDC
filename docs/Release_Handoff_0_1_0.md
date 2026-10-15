# 0.1.0 发布交接

用户已验收 FFT_Restored，并授权 README、正式包/哈希、main 推送及新 annotated
`v0.1.0` tag。本次不创建 GitHub Release，不上传资产，不修改仓库 About/主题或制作演示。

## 不变的已验收程序

冻结程序代码提交：`3b21cb4142d947138ce71c87d2bfc2e202681d8b`。
EXE SHA-256：`0dadf29e61f00592eadd19907f6063b82a586175d1b53f7b89b49bc022c7be9d`。
本次只修改 README、版本/交接说明及源码提供路径。最终 tag 的 `src/`、`plugins/`、
`main.py`、`pyproject.toml` 必须与该冻结代码提交无差异。无需重编译或改变已验收功能。
348 项全量、57 项专项、源码/冻结 GUI 各 244 项、语言与便携启动证据继续对应这些程序字节。

## 正式资产

统一暂存在 `dist/release_0_1_0/`：

- `Underline_RETLDC_0_1_0_Windows_Portable.zip`
- `Underline_RETLDC_0_1_0_Corresponding_Sources.zip`
- `SHA256SUMS.txt`

便携 ZIP 基于已验收包，只更新 README、匹配文档及构建来源元数据；逐成员验证，
EXE、依赖和插件代码字节不变。来源 ZIP 从最终 tag 对应提交的 Git 对象制作精确快照，
并复用既有六份原始上游归档。清单分别记录最终源码提交和原冻结程序提交，避免将
文档提交误称为重新冻结的程序。最终哈希在资产旁计算，不写进待哈希归档而造成循环。
保留旧二进制候选；六份上游归档只保留一个可恢复容器，不重复下载或展开 SDK。

## Git 与远端复核

远端为 `GitHub_Underline_RETLDC`，仓库
https://github.com/aleistercrowleybeast666/Underline_RETLDC 。起始远端 main 为
`3c4e436cc0072c0a3f33c068d3a9bb6df1a43fa7`，此前标签到 `v0.0.4`，没有 `v0.1.0`。
仅允许 main 普通快进及新标签推送；若有未知远端提交或同名标签则停止，不强推或移动标签。
推送后回读 main 的提交、README 内容和 annotated tag 解引用，并查询该提交的 CI。
仓库起始无 `.github/workflows`、Actions 历史运行或提交状态，不把“无 CI”写成“CI 通过”。

用户随后在 GitHub 为该 tag 创建 Release，粘贴 `Release_Notes_0_1_0.md` 并上传上述
三份文件，再从公开下载地址验证 SHA-256。推送 tag 不会自动完成这一步；在此之前
README 使用真实 Releases 入口，明确 0.1.0 资产尚待上传。
