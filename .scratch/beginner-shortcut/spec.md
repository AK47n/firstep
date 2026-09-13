# 安装后自动创建桌面快捷方式（beginner-shortcut）

## 问题陈述

新人从 GitHub 拿到 firstep 后，桌面（或解压目录）里没有「启动 firstep」这样的入口，只有一排文件：
`install.bat`、`start-app.vbs`、`stop-firstep.vbs`……他必须先找到自己解压/克隆到哪个目录、
再认出「该双击哪一个」，才能把工具打开。README 里写了「双击 `start-app.vbs`」，
但用户点开的是浏览器下载记录，不是 README；实测提问就是「install.bat 会在桌面上生成 start-app 吗」
——说明这一步的预期本身就模糊，新人会假定安装脚本替他放好入口。

现在 `install.bat` 跑完只打印一行「安装完成！请双击 start-app.vbs 启动」，没有任何桌面入口。

## 方案

`install.bat` 在安装收尾时**自动在桌面创建一个名为 `firstep` 的快捷方式**，双击即启动本工具
（隐藏黑窗口、浏览器自动打开 http://127.0.0.1:8000），与 `start-app.vbs` 行为一致。

- 快捷方式已存在则不重做（幂等；重复跑 `install.bat` 不会覆盖用户自己改过的图标/名称）。
- 创建失败**不影响安装**（依赖等前置步骤早已完成，只是提示用户可以手动双击 `start-app.vbs`）。
- 安装完成提示改为「双击桌面的 firstep 快捷方式，或本目录的 start-app.vbs」——两个入口都告诉用户。

## 用户故事

1. 作为刚克隆/解压完 firstep 的新人，我想要桌面上出现一个能直接点开的入口，以便不用去记哪个文件是启动器。
2. 作为新人，我想要这个入口不需要我懂 `cmd` / `.vbs` / 工作目录，以便双击就能用。
3. 作为反复重跑 `install.bat` 的用户（装依赖失败后重试），我想要它不会重复建快捷方式、也不会覆盖我改过的图标，以便我的桌面保持我自己的样子。
4. 作为把工具装在中文/带空格路径下的用户（如 `D:\我的工具\firstep`），我想要快捷方式仍然能启动，以便路径形态不影响我。
5. 作为克隆在非桌面的用户，我想要安装脚本不去猜我的安装位置，以便快捷方式总是指向我实际用的那份（脚本用自身所在目录）。
6. 作为维护者，我想要这个行为有回归守卫（谁把这段删了会红），以便发布包不会悄悄退回「没有桌面入口」。
7. 作为用户，我想要创建快捷方式失败时安装仍然算成功，以便一个非核心步骤不阻断装依赖这件事。

## 实现决策

- **落点**：`install.bat` 新增一步（原 4 步 → 5 步），放在库目录配置之后、依赖自检之前。
- **调用方式**：`powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand <base64>`。
  选它是因为 `cmd` → `powershell -Command` 的引号嵌套在这类路径/参数场景下极易被吃掉引号
  （本机探针实测：`-Command` 传含引号的 `$s.Arguments` 直接 ParseError），Base64 负载绕开整个转义层。
- **负载内容**（UTF-16LE + Base64，纯 ASCII 源，不含中文——PowerShell 5.1 对命令行按 ANSI 解码，
  中文进负载会乱码，实测确认故描述文字用 `firstep`）：
  - 目标：`%SystemRoot%\System32\wscript.exe`，参数 `"<工具根>\start-app.vbs"`，工作目录 = 工具根。
    用 `wscript.exe` 而不是直接指向 `start-app.bat`，是为了不闪黑窗口（与 `start-app.vbs` 的既有意图一致）。
  - 桌面路径：`[Environment]::GetFolderPath('Desktop')`——`%USERPROFILE%\Desktop` 在 OneDrive
    重定向桌面的机器上会指向不存在的位置，两者可能不一致，故用 API。
  - 幂等：`if (Test-Path $p) { exit 0 }`。
  - 工具根：install.bat 用 `set FIRSTEP_ROOT=%~dp0` 传入（**批处理不自动导出变量给子进程**，
    必须显式 `set`，否则负载里的 `$env:FIRSTEP_ROOT` 为空）。
  - 失败语义：负载顶部 `$ErrorActionPreference = 'Stop'` → 失败退出码非 0 → install.bat 打印中文提示并继续。
- **编码硬约束**：`install.bat` 必须保持 **GBK(cp936)、无 UTF-8 BOM、CRLF**（`.gitattributes` 已钉
  `*.bat text eol=crlf`；`tests/test_onboarding_docs.py` 已守卫无 BOM）。改动必须走精确编码读写，
  不得让整文件在更新包里变成「已修改」。

## 测试决策

- **接缝（复用既有，不新建）**：`tests/test_onboarding_docs.py` —— 该文件已经是 `install.bat` 的门禁
  （存在性 / GBK 中文 / 主流程 needle），本次是同主题追加，不新开文件（测试接缝数保持 1）。
- 守卫什么（外部可观察行为，不锚实现细节）：
  1. install.bat 里出现桌面快捷方式创建的完整链路（`wscript.exe` + `start-app.vbs` + 幂等判据）；
  2. 负载能从文件里被**独立提取并解码**——证明它确实是可执行的 PowerShell 文本（防手改坏 Base64）；
  3. 完成提示同时给出两个入口（桌面快捷方式 / start-app.vbs）。
- 不做：不建真实 `.lnk` 的测试（Windows COM + 真实桌面写操作，属真机验收；本机已手工探针验证过
  Target/Arguments/WorkingDirectory 三项与幂等重跑）。

## 范围外

- 开始菜单 / 任务栏固定 / 开机自启。
- 已装用户的历史快捷方式迁移（他们重跑一次 `install.bat` 即可）。
- `start-app.bat` / `start-app.vbs` 自身行为的任何改动。
- 卸载时删除快捷方式（本工具无卸载器）。
- 非 Windows 平台。

## 补充说明

- 本次改动会随下一个发布包下发；`git clone` 用户 `git pull` 后重跑 `install.bat` 即可获得入口。
- 用户原话背景：问「install.bat 会在桌面上生成 start-app 吗」→ 现状是不生成；已确认要补进 `install.bat`。
