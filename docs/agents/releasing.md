# Release & Versioning（发布与版本命名）

本文件定义 firstep 的版本号命名规则与完整包发布流程。生成器**代码更新频繁**，而完整包（含电赛资料库 `sources/materials`）体积约 6.5 GB、重传成本高——因此核心约定是：

> **发版 = 发布新的完整包**；纯代码更新跟 git 走（`git clone` 即最新），不必发 Release。

## 版本号命名（SemVer）

格式 `v主版本.次版本.修订号`，git tag 与 Release 标题同号：

| 变更类型 | 动作 | 示例 |
| --- | --- | --- |
| 首次发布 / 破坏性变更（大重写、资料库结构重组） | 主版本 +1 | v1.0.0 → v2.0.0 |
| 新增功能（新模块、资料库增补、界面大改） | 次版本 +1 | v1.0.0 → v1.1.0 |
| 小修小补（bug 修复、文档更新、资料小修） | 修订号 +1 | v1.0.0 → v1.0.1 |

## 何时发 Release

1. `sources/materials` 资料库有增删改 → 重打完整包，发新 tag + Release。
2. 重大里程碑（首次公开、大版本切换）→ 即使资料无变化也可发。
3. 其余代码更新：不发。使用者 `git clone https://github.com/AK47n/firstep.git` 始终拿到最新代码。

## 发版流程

1. 确认工作区状态：`git status`——未提交内容先处理干净再打 tag。
2. 重新打包完整包（store 模式，1900 MB 分卷；**分卷必须 < 2 GB**，GitHub 附件单文件上限）：

   ```powershell
   & C:\Users\luoji\Desktop\firstep-tools\7zr.exe a -t7z -mx=0 -v1900m `
     C:\Users\luoji\Desktop\firstep-pack\firstep-full.7z `
     C:\Users\luoji\Desktop\firstep `
     '-xr!.git' '-xr!.scratch' '-xr!__pycache__' '-xr!.pytest_cache' '-xr!.mypy_cache' '-xr!*.log' `
     -bso0 -bsp0
   ```

   注意：排除开关必须带引号（`'-xr!.git'`），否则 7zr 报 `Too short switch r!`。`7zr.exe` 从 https://www.7-zip.org/a/7zr.exe 下载（单文件版，无需安装）。

3. 写 Release Notes（本版变化来自 `git log v上一版..HEAD`；解压方法见 `HOW_TO_EXTRACT.txt` 模板）。
4. 创建 Release 并上传附件：

   ```powershell
   gh release create vX.Y.Z `
     --title 'firstep 电赛工程生成器 · 完整包 vX.Y.Z（含电赛资料库）' `
     --notes-file release-notes.md --repo AK47n/firstep

   gh release upload vX.Y.Z `
     firstep-full.7z.001 firstep-full.7z.002 firstep-full.7z.003 firstep-full.7z.004 `
     HOW_TO_EXTRACT.txt --repo AK47n/firstep
   ```

5. 更新 README「获取方式」与「版本与发布」中的当前版本号（Release 链接形式固定，无需改）。
6. 校验：`gh release view vX.Y.Z --repo AK47n/firstep` 或 GitHub API 确认附件齐全。

## 附件命名注意

gh CLI 上传**中文文件名**会把附件名替换为 `default.txt`——解压说明一律用 ASCII 文件名 **`HOW_TO_EXTRACT.txt`**（文件内容可中文）。Release 页面可放说明，正文用 `HOW_TO_EXTRACT.txt` 指路。

## 快速发版（给 Agent）

- 打包用上表 7zr 命令（store 模式几分钟）。
- 上传 6.2 GB 附件视上行带宽需 20 分钟以上，用后台任务跑，别阻塞等待。
