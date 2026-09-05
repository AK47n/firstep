# Release & Versioning（发布与版本命名）

本文件定义 firstep 的版本号命名规则与发布流程。生成器**代码更新频繁**，而完整包（含电赛资料库 `sources/materials`）体积约 6.5 GB、重传成本高——因此发布拆成两级：

> **小发版**（代码 / 库 / 文档变更）：发轻量更新包（单 zip，约 0.3 GB，4 件套），工具内置「检查更新 + 一键更新」自动完成替换，用户**不重下完整包**。
> **大发版**（`sources/materials` 资料库增删改）：发完整包（6.2 GB、4 个 7z 分卷），低频。

`git clone` 用户不受影响：`git pull` 路线与小发版平级，始终拿到最新代码。

## 版本号命名（SemVer）

格式 `v主版本.次版本.修订号`，git tag 与 Release 标题同号：

| 变更类型 | 动作 | 示例 |
| --- | --- | --- |
| 首次发布 / 破坏性变更（大重写、资料库结构重组） | 主版本 +1 | v1.0.0 → v2.0.0 |
| 新增功能（新模块、资料库增补、界面大改） | 次版本 +1 | v1.0.0 → v1.1.0 |
| 小修小补（bug 修复、文档更新、资料小修） | 修订号 +1 | v1.0.0 → v1.0.1 |

## 何时发 Release

1. **小发版**：代码 / 模块库 / 母版库 / 赛题库 / 参考文件库（`sources` 下除 `materials` 的部分）/ 文档有变更 → 发更新包 4 件套（更新包机制见 `.scratch/auto-update/spec.md`）。
2. **大发版**：`sources/materials` 资料库有增删改 → 重打完整包，发新 tag + Release（可同时附更新包）。
3. 重大里程碑（首次公开、大版本切换）→ 即使资料无变化也可发。

## 发版前：三处版本号同步（必做）

打 tag 前把版本号改到目标值并提交：

1. `src/contest_generator/__init__.py` 的 `__version__`（**唯一可信来源**，`/api/health` 与「检查更新」都吃它）；
2. `pyproject.toml` 的 `project.version`（打包元数据，必须与 `__version__` 一致）；
3. `README.md`「版本与发布」当前版本行 + `VERSIONS.md` 顶部新增版本区块（用户可见）。

## 小发版流程

1. 确认工作区状态：`git status`——未提交内容先处理干净（`tools/pack-update.ps1` 默认拒绝脏工作树打包，`-AllowDirty` 可豁免）。
2. 跑打包脚本（仓库根）：

   ```powershell
   powershell -File tools\pack-update.ps1 -Tag v1.1.0 -Baseline <上次发布的 files.txt 路径>
   ```

   - 产出四件套：`firstep-update-v1.1.0.zip`（仓库 tracked 快照，含 `VERSIONS.md`，**不含** `.scratch` / `.venv` / `sources/materials` / `.git`）、`.files.txt`（文件清单）、`.removed.txt`（自基线起删除的文件；首次发布无基线 = 空）、`.sha256.txt`。
   - 首次小发版没有基线：省略 `-Baseline`（removed 为空，更新器跳过删除）。
3. 创建 Release 并上传更新包四件套（附件用 ASCII 文件名，避免 gh 把中文名替换成 `default.txt`）：

   ```powershell
   gh release create v1.1.0 --title 'firstep 电赛工程生成器 · 更新包 v1.1.0' --notes-file release-notes.md --repo AK47n/firstep
   gh release upload v1.1.0 firstep-update-v1.1.0.zip firstep-update-v1.1.0.files.txt firstep-update-v1.1.0.removed.txt firstep-update-v1.1.0.sha256.txt --repo AK47n/firstep
   ```

4. 校验：`gh release view v1.1.0 --repo AK47n/firstep` 或 GitHub API 确认 4 个附件齐全。
5. 把本次 `firstep-update-v1.1.0.files.txt` 存好——下次小发版的 `-Baseline`。

## 大发版流程（完整包，资料库变动时）

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

- 小发版：`powershell -File tools\pack-update.ps1 -Tag vX.Y.Z -Baseline <上次 files.txt>`（几分钟），产物在输出目录（缺省 `%USERPROFILE%\Desktop\firstep-pack`）。
- 大发版：用上面 7zr 命令（store 模式几分钟）。
- 上传 6.2 GB 附件视上行带宽需 20 分钟以上，用后台任务跑，别阻塞等待。
