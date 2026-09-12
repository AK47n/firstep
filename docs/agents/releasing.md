# Release & Versioning（发布与版本命名）

本文件定义 firstep 的版本号命名规则与发布流程。生成器**代码更新频繁**，而完整包（含电赛资料库 `sources/materials`）体积约 6.5 GB、重传成本高——因此发布拆成两级：

> **小发版**（代码 / 库 / 文档变更）：发轻量更新包（单 zip，约 0.3 GB，4 件套），工具内置「检查更新 + 一键更新」自动完成替换，用户**不重下完整包**。
> **完整包（一键全量，约 1.0 GB）**：`firstep-full-<tag>.zip`（超 1.9 GB 自动拆 `.part<N>`）+ 清单，工具内「设置 → 完整包下载」一键下载 + 自动替换重启；用于无基线 / 修损坏 / 换机器。**不含**装机用的第三方安装包与视觉 SDK（约省 4.9 GB）。
> **大发版**（`sources/materials` 资料库增删改）：发**资料库增量包**（按批次 zip，只含新增 / 修改文件，工具内「资料库更新」一键下载应用）；完整包（6.2 GB、4 个 7z 分卷）仅作无基线 / 全新安装渠道，低频。

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
2. **完整包（一键全量）**：想让用户能「一键下载整份 firstep」（换机器、修损坏、给尚无资料库基线的用户一条自动出路）→ 小发版四件套之外**再加发**完整包资产（见下文「完整包（zip 分卷）流程」）。资产小（约 1 GB / 1~2 卷），与小发版同 tag，可一起传。
3. **大发版**：`sources/materials` 资料库有增删改 → 打资料库增量包（见下文「大发版流程（资料库增量包）」），发 `materials-vX.Y.Z` tag + Release。
4. 重大里程碑（首次公开、大版本切换）→ 即使资料无变化也可发完整包。

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

## 完整包（zip 分卷）流程（一键全量下载）

> 机制见 `.scratch/full-download/spec.md`。**包内只有会变的内容**：工具本体 + 五个库 + `sources/contest`、`sources/car` + 资料库内容文件；第三方安装包与视觉 SDK 打包件（`*.exe` / `*.rar` / `*.img*` / `*CCS_20.5*` / `*tsp-xbhdcc*` 等，本机约 5.4 GB）、缓存、虚拟环境、本地备份目录都不进包。实测包内约 **8764 个文件 / 原始 1.07 GB**，zip 后约 1.0 GB、1~2 卷。

1. 确认工作区干净（`git status`；脚本默认拒绝脏工作树，`-AllowDirty` 豁免）。
2. 跑打包脚本（仓库根）：

   ```powershell
   powershell -File tools\pack-full.ps1 -Tag v1.1.0 -Baseline <上一版 firstep-full-*.manifest.json>
   ```

   - 产出四件套：`firstep-full-<tag>.zip`（或 `.part<N>.zip` 多卷）、`firstep-full-<tag>.manifest.json`（**含包内全部文件清单 + 资料库基线清单 + 删除清单**）、`firstep-full-<tag>.removed.txt`（人工核对副本）、`firstep-full-<tag>.sha256.txt`。
   - 首次发布没有基线：省略 `-Baseline`（删除清单为空，更新器跳过删除）。
   - 单卷上限默认 1900 MB（GitHub 单资产 2 GB 留余量），`-LimitMB` 可调。
3. 上传到**当次软件版本 tag 的 Release**（与小发版四件套同一个 Release；附件一律 ASCII 文件名）：

   ```powershell
   gh release upload v1.1.0 firstep-full-v1.1.0.zip firstep-full-v1.1.0.manifest.json firstep-full-v1.1.0.removed.txt firstep-full-v1.1.0.sha256.txt --repo AK47n/firstep
   ```

4. 校验：`gh release view v1.1.0 --repo AK47n/firstep` 确认**完整包清单资产在场**——工具内「设置 → 完整包下载 → 检查完整包」靠它发现新版本；资产缺失时前端会明确提示「该版本的 Release 上没有完整包资产」。
5. 把本版 `firstep-full-v1.1.0.manifest.json` 存好——下次完整包的 `-Baseline`。
6. 用户侧效果：下载完成 → 自动替换重启 → 资料库基线随包写回（**无基线状态只出现一次**，之后检查资料库更新只收增量）。

> 与 7z 完整包的关系：7z 路线**保留**（无基线 / 全新安装 / 需要那批第三方安装包时用），zip 完整包是「已装用户的一键全量」路线。两条并存，互不影响。

## 大发版流程（资料库增量包，`sources/materials` 变动时）

> 资料库增量机制见 `.scratch/materials-update/spec.md`。核心：每次发版发布一份**全量清单**（`firstep-materials-<tag>.manifest.json`，含每批次文件集 SHA256），下一版以它为基线算增量；用户侧只下载新增 / 修改文件（按批次分卷 zip），旧版完整包用户第一次需要先有一次全量或初始基线。

1. **基线准备**：上一版清单 = 上次发布时上传的 `firstep-materials-<tag>.manifest.json`（GitHub Release 资产里取，或本地存一份）。
   - 首次引入（无基线）：先跑 `-Mode init` 产出当前快照清单，作为「初始基线」随完整包/联系用户分发；或直接 `-Mode full` 打全量（等同于旧完整包路线，低频）。
2. **打增量包**（仓库根；资料库 tag 用 `materials-vX.Y.Z`，与软件版本无关）：

   ```powershell
   powershell -File tools\pack-materials.ps1 -Tag v1.1.0 -Mode diff -Baseline <上版清单.json>
   ```

   - 产出（缺省 `%USERPROFILE%\Desktop\firstep-pack-materials`）：`firstep-materials-v1.1.0.manifest.json`（本版全量清单）+ 按批次 `firstep-materials-v1.1.0-<slug>.zip`（超 1.9 GB 自动 `.part<N>`）。
   - 版本号语义：`-Tag` 是**资料库版本号**（与软件版本同 SemVer 文法，独立递增）；GitHub Release tag 再加 `materials-` 前缀（见下）。
   - `-Mode init`：只出清单不打包（初始基线用）；`-Mode full`：全量打包（无基线时）。
   - 注意：`-Baseline` 支持本地上版清单路径或 GitHub Raw URL；资料库内新顶级目录需先在 `src/contest_generator/materials_pack.py` 的 `DIR_SLUGS` 登记 slug，否则脚本报错。
3. **创建 Release 并上传**（Release tag = `materials-v1.1.0`，与软件 tag 区分；附件一律 ASCII 文件名）：

   ```powershell
   gh release create materials-v1.1.0 --title 'firstep 资料库更新 v1.1.0' --notes-file release-notes.md --repo AK47n/firstep
   gh release upload materials-v1.1.0 firstep-materials-v1.1.0.manifest.json firstep-materials-v1.1.0-<slug>.zip [.part1.zip ...] --repo AK47n/firstep
   ```

4. 校验：`gh release view materials-v1.1.0 --repo AK47n/firstep` 确认清单 + 各批次 zip 齐全（用户在工具「设置 → 资料库更新」检查即见）。
5. 把本版 `firstep-materials-v1.1.0.manifest.json` 存为下一版基线。

### 完整包路线（保留，无基线 / 全新安装 / 资料库全量重下时）

1. 重新打包完整包（store 模式，1900 MB 分卷；**分卷必须 < 2 GB**，GitHub 附件单文件上限）：

   ```powershell
   & C:\Users\luoji\Desktop\firstep-tools\7zr.exe a -t7z -mx=0 -v1900m `
     C:\Users\luoji\Desktop\firstep-pack\firstep-full.7z `
     C:\Users\luoji\Desktop\firstep `
     '-xr!.git' '-xr!.scratch' '-xr!__pycache__' '-xr!.pytest_cache' '-xr!.mypy_cache' '-xr!*.log' `
     -bso0 -bsp0
   ```

   注意：排除开关必须带引号（`'-xr!.git'`），否则 7zr 报 `Too short switch r!`。`7zr.exe` 从 https://www.7-zip.org/a/7zr.exe 下载（单文件版，无需安装）。

2. 写 Release Notes（本版变化来自 `git log v上一版..HEAD`；解压方法见 `HOW_TO_EXTRACT.txt` 模板）。
3. 创建 Release 并上传附件：

   ```powershell
   gh release create vX.Y.Z `
     --title 'firstep 电赛工程生成器 · 完整包 vX.Y.Z（含电赛资料库）' `
     --notes-file release-notes.md --repo AK47n/firstep

   gh release upload vX.Y.Z `
     firstep-full.7z.001 firstep-full.7z.002 firstep-full.7z.003 firstep-full.7z.004 `
     HOW_TO_EXTRACT.txt --repo AK47n/firstep
   ```

4. 更新 README「获取方式」与「版本与发布」中的当前版本号（Release 链接形式固定，无需改）。
5. 校验：`gh release view vX.Y.Z --repo AK47n/firstep` 或 GitHub API 确认附件齐全。

## 附件命名注意

gh CLI 上传**中文文件名**会把附件名替换为 `default.txt`——解压说明一律用 ASCII 文件名 **`HOW_TO_EXTRACT.txt`**（文件内容可中文）。Release 页面可放说明，正文用 `HOW_TO_EXTRACT.txt` 指路。

## 快速发版（给 Agent）

- 小发版：`powershell -File tools\pack-update.ps1 -Tag vX.Y.Z -Baseline <上次 files.txt>`（几分钟），产物在输出目录（缺省 `%USERPROFILE%\Desktop\firstep-pack`）。
- 完整包：`powershell -File tools\pack-full.ps1 -Tag vX.Y.Z -Baseline <上版 firstep-full-*.manifest.json>`（本机实测打包 ≤ 数分钟），产物同上；与小发版同 tag 一起上传。
- 大发版：用上面 7zr 命令（store 模式几分钟）。
- 上传 6.2 GB 附件视上行带宽需 20 分钟以上，用后台任务跑，别阻塞等待；完整包约 1 GB，可一并后台传。
