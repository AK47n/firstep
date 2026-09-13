# 01 — install.bat 安装收尾自动创建桌面快捷方式

**要做什么：** 跑完 `install.bat` 后，桌面出现一个名为 `firstep` 的快捷方式；双击它启动本工具
（无黑窗口、浏览器打开 http://127.0.0.1:8000），行为与双击 `start-app.vbs` 一致。
重复跑 `install.bat` 不重建、不覆盖已有同名快捷方式；创建失败只提示、不让安装失败。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `install.bat` 为 5 步：新增「[5/5] 创建桌面快捷方式」，且原 4 步编号同步更新为 `[n/5]`
- [x] 快捷方式目标 = `wscript.exe`，参数 = `"<工具根>\start-app.vbs"`，工作目录 = 工具根（工具根取自脚本自身位置 `%~dp0`，不猜路径）
- [x] 桌面路径经 `[Environment]::GetFolderPath('Desktop')` 取（兼容 OneDrive 重定向桌面）
- [x] 幂等：`firstep.lnk` 已存在 → 跳过且退出码 0；同一安装目录连续跑两次 `install.bat`，第二次不再报「已创建」
- [x] 失败不阻断：创建失败时打印中文提示（含手动启动路径）且安装流程继续，最终仍提示安装完成
- [x] 完成提示同时给出两个入口：桌面 `firstep` 快捷方式 + `start-app.vbs`
- [x] `install.bat` 仍是 GBK 无 BOM + CRLF（不得引入 UTF-8 BOM；`git diff` 字节口径与打包器一致）
- [x] `tests/test_onboarding_docs.py` 新增守卫：链路 needle（`wscript.exe` / `start-app.vbs` / 幂等判据）+ 负载可提取解码 + 完成提示含两个入口
- [x] 真机验证：在本机 `Desktop\firstep` 跑一次 `install.bat`，桌面出现 `firstep.lnk` 且三个属性正确；再跑一次保持幂等
- [x] 文档同步：`README.md`「三步装好」补一句「安装时自动在桌面创建 firstep 快捷方式」

## 验收记录（2026-09-13 本机实测）

- 编码口径：install.bat 2582 → 4526 bytes，GBK 无 BOM + 全 CRLF（脚本内断言 + `git diff` 复核）。
- 真机 e2e（`.scratch/beginner-shortcut/verify_shortcut_e2e.py`，负载取自 install.bat 原文、真实桌面写入后还原）：
  - 第 1 跑 `exit=0`，桌面出现 `firstep.lnk`；
  - 读回属性：`Target=C:\Windows\System32\wscript.exe`、`Args="C:\Users\luoji\Desktop\firstep\start-app.vbs"`、`WorkDir=C:\Users\luoji\Desktop\firstep`；
  - 第 2 跑（先把 Description 改成哨兵值再重跑）`exit=0` 且哨兵仍在 → 幂等成立、不覆盖用户改动。
- 踩坑留痕：
  1. `cmd` → `powershell -Command` 会吃掉内层引号（`$s.Arguments` 直接 ParseError）→ 改用 `-EncodedCommand`（Base64 UTF-16LE）。
  2. 中文进 `-EncodedCommand` 负载会乱码（PowerShell 5.1 命令行按 ANSI 解码）→ 负载内描述文字用 ASCII `firstep`。
  3. `%~dp0` 自带尾反斜杠 → 负载里 `TrimEnd('\')`，否则 `Arguments` 出现 `firstep\\start-app.vbs`。
  4. 守卫断言首版写错一层：`wscript.exe` 在 Base64 负载**里**，不在批处理明文中（红→改断言→绿）。

