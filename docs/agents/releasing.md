# Release & Versioning（发布与版本命名）

本文件定义 firstep 的版本号命名规则与发布流程。

> **完整包口径（2026-09-13 复核后改写）**：完整包 = 工具本体 + 五个库 + 资料库**内容文件**、
> **标准 zip 单卷约 770 MB**（超 1.9 GB 才拆 `.part<N>`）。它同时是**新用户唯一的安装包**
> （README 只指这一个文件，Windows 自带解压，包内带 `00-START-HERE.txt`）。
> 历史上那个 6.2 GB / 4 个 7z 分卷的形态**已下线**：只剩 v1.0.0 那个 release 有，
> 不再打包、不再上传、不再在文档里出现（`tests/test_onboarding_docs.py` 有负向门禁）。

> **小发版**（代码 / 库 / 文档变更）：发轻量更新包（单 zip，约 0.3 GB，4 件套），工具内置「检查更新 + 一键更新」自动完成替换，用户**不重下完整包**。
> **完整包（一键全量，约 770 MB）**：`firstep-full-<tag>.zip`（超 1.9 GB 自动拆 `.part<N>`）+ 清单，工具内「设置 → 完整包下载」一键下载 + 自动替换重启；用于无基线 / 修损坏 / 换机器 / 新用户首次安装。**不含**装机用的第三方安装包与视觉 SDK（约省 4.9 GB）。
> **大发版**（`sources/materials` 资料库增删改）：发**资料库增量包**（按批次 zip，只含新增 / 修改文件，工具内「资料库更新」一键下载应用）。新用户不再需要一条单独的 6.2 GB 渠道——完整包里已带资料库内容文件与基线清单。

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
2. **完整包（一键全量）**：想让用户能「一键下载整份 firstep」（换机器、修损坏、给尚无资料库基线的用户一条自动出路）→ 小发版四件套之外**再加发**完整包资产（见下文「完整包（zip 分卷）流程」）。资产约 770 MB / 1~2 卷，与小发版同 tag，可一起传。
   **它同时是新用户的安装包**：README 的「获取方式」只指这一个文件，所以**每次发版都要确认该资产在场且可被 Windows 自带解压**（`firstep-full-<tag>.zip` 在 release 上、字节数与 README 写的「约 770 MB」同一量级）。
3. **大发版**：`sources/materials` 资料库有增删改 → 打资料库增量包（见下文「大发版流程（资料库增量包）」），发 `materials-vX.Y.Z` tag + Release。
4. 重大里程碑（首次公开、大版本切换）→ 即使资料无变化也可发完整包。

## 发版前：一条命令自检（必做）

```powershell
powershell -File tools\preflight.ps1
```

四件事一次查完，**红了就别打包/别打 tag**（逐条给中文原因与修法）：

1. **三处版本号一致**：`src/contest_generator/__init__.py` / `pyproject.toml` / `VERSIONS.md` 首个版本块；
2. **母版 `.settings/` 编码钉**在盘**且在 git**（mspm0 的 CCS 编码设置，2026-09-15 被清理误删过一次）；
3. **下载文档一致性**（`tools/check-download-docs.py --offline`）；
4. **README 当前版本行**与 `__version__` 一致。

> 2026-09-14 那次事故正是「改完版本号没跑守卫」：`VERSIONS.md` 版本头写坏（日期段混进中文），
> 解析器**静默跳过整块** → 记录页缺本版，而两个包都已经传上线，只能重打重传。
> 判据不新造——全部复用产品自己的解析器与既有守卫脚本，`tools/preflight.ps1` 只是入口。

## 发版前：三处版本号同步（必做）

打 tag 前把版本号改到目标值并提交：

1. `src/contest_generator/__init__.py` 的 `__version__`（**唯一可信来源**，`/api/health` 与「检查更新」都吃它）；
2. `pyproject.toml` 的 `project.version`（打包元数据，必须与 `__version__` 一致）；
3. `README.md`「版本与发布」当前版本行 + `VERSIONS.md` 顶部新增版本区块（用户可见）。

## 发版前：跑一次下载链路自检（联网那一次，必做）

```powershell
python tools\check-download-docs.py
```

`tools/preflight.ps1` 里的第 3 项跑的是它的 `--offline` 版本（不联网，能进 CI）。**打包上传之后**
再跑一次这个不带参数的完整版：它会拿**线上最新的 Release** 去校验 README 的体积口径与 Release
说明前两行，正好确认这一版发对了。

它把**新用户能看到的三个入口**对一遍：README「获取方式」（有没有已下线形态、指向的是不是
`/releases/latest`、点名的包内文件是否真在包里、写的体积与线上字节是否同一量级）、
**线上最新版的 Release 说明前几行**（有没有「新用户只下哪个 / 已装用户走工具内更新」）、
以及 git clone 的体积口径。任一处分叉 → 非 0 退出并逐条给原因。

为什么必须跑：2026-09 出过一次真实事故——README 教用户下 `firstep-full.7z.001~004`（约 6 GB），
而那个形态只在 v1.0.0 那个 release 上，最新版根本没有。**文档与线上分叉，新用户就会白找一圈。**
（不放进 pytest 是因为本仓库测试刻意不联网；它是**发版前手动跑**的自检。）

## 小发版流程

1. 确认工作区状态：`git status`——未提交内容先处理干净（`tools/pack-update.ps1` 默认拒绝脏工作树打包，`-AllowDirty` 可豁免）。
2. 跑打包脚本（仓库根）：

   ```powershell
   powershell -File tools\pack-update.ps1 -Tag v1.1.0 -Baseline <上次发布的 files.txt 路径>
   ```

   - 产出四件套：`firstep-update-v1.1.0.zip`（仓库 tracked 快照，含 `VERSIONS.md`，**不含** `.scratch` / `.venv` / `sources/materials` / `.git`）、`.files.txt`（文件清单）、`.removed.txt`（自基线起删除的文件；首次发布无基线 = 空）、`.sha256.txt`。
   - 首次小发版没有基线：省略 `-Baseline`（removed 为空，更新器跳过删除）。
   - **包内字节口径**（工单 `full-download/08` 定案；两条打包路线必须一致）：以**工作树检出字节**为准——核心里的 `git archive` 已钉 `-c core.autocrlf=false`，故不受本机 `core.autocrlf` 影响；`.gitattributes` 里显式写了 `eol` 的仍按其物化（`*.bat` → CRLF、`.githooks/*` → LF）。改任一侧前先跑 `tests/test_pack_update.py`（跨包逐字节守卫）——两边不一致会让增量发布把大批文件误判为「已修改」，把「只下变化部分」变成「几乎全量重下」（v1.1.0 现场：3474 个共有文件里 926 个字节不同、内容差异 0）。
3. **先在本地打 tag 并推送，再建 Release**（`gh release create` 是在**服务端**建 tag，
   本地不会自动有这个 tag —— 2026-09-13 发 v1.1.0/v1.1.1 时踩到：本地 `git tag` 只有
   v1.0.0，下次要按 tag 引基线就找不到）：

   ```powershell
   git tag -a v1.1.0 -m "firstep v1.1.0"
   git push origin main v1.1.0
   ```

   已经用 `gh release create` 建过 tag 的，补一条同步即可：`git fetch origin --tags`。
4. 创建 Release 并上传更新包四件套（附件用 ASCII 文件名，避免 gh 把中文名替换成 `default.txt`）：

   ```powershell
   gh release create v1.1.0 --title 'firstep 电赛工程生成器 · 更新包 v1.1.0' --notes-file release-notes.md --repo AK47n/firstep
   gh release upload v1.1.0 firstep-update-v1.1.0.zip firstep-update-v1.1.0.files.txt firstep-update-v1.1.0.removed.txt firstep-update-v1.1.0.sha256.txt --repo AK47n/firstep
   ```

   - **空 `removed.txt` 会被拒收**：首次发布（无基线）时该文件是 0 字节，`gh release
     upload` 报 `HTTP 400: Bad Content-Length`。上传前写成一行注释
     （`# 本次无被删除的文件`）——更新器本就跳过 `#` 行，语义不变。
5. 校验：`gh release view v1.1.0 --repo AK47n/firstep` 或 GitHub API 确认 4 个附件齐全。
6. 把本次 `firstep-update-v1.1.0.files.txt` 存好——下次小发版的 `-Baseline`。

## 完整包（zip 分卷）流程（一键全量下载）

> 机制见 `.scratch/full-download/spec.md`。**包内只有会变的内容**：工具本体 + 五个库 + `sources/contest`、`sources/car` + 资料库内容文件；第三方安装包与视觉 SDK 打包件（`*.exe` / `*.rar` / `*.img*` / `*CCS_20.5*` / `*tsp-xbhdcc*` 等，本机约 5.4 GB）、缓存、虚拟环境、本地备份目录都不进包。实测包内约 **8787 个文件 / 原始 1055.8 MB**，zip 后 **约 770 MB**（v1.2.0 实测 `807,732,722` 字节；
v1.1.1 是 `821,352,026`，差额来自库治理回收的重复文件与压缩率）、1~2 卷。
>
> **包内还有面向新用户的 `00-START-HERE.txt`**（工单 `newuser-download/02`）：名字前的 `00-` 让它排在解压目录第一位，新人第一眼就看得到。它必须在 `full_pack` 顶层白名单里，改完跑 `tests/test_full_pack.py` 确认它真的进了包与清单。

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
   **同时确认 `firstep-full-<tag>.zip` 在场且体积与「约 821 MB」同量级**——它是新用户的安装包，README 只指这一个文件；它不在，新用户就没有入口（`gh api repos/AK47n/firstep/releases/tags/<tag>` 看 `size`）。
5. 把本版 `firstep-full-v1.1.0.manifest.json` 存好——下次完整包的 `-Baseline`。
6. 用户侧效果：下载完成 → 自动替换重启 → 资料库基线随包写回（**无基线状态只出现一次**，之后检查资料库更新只收增量）。
7. **写 Release 说明**（模板见本文件末「Release 说明模板」；新用户的落点全在这里）。

> **7z 完整包渠道已下线（2026-09-13）**：不再打 7z、不再传分卷、文档不再提。存量资产只剩 v1.0.0 那个 release，
> 保留不动（不删已发布的东西）。要那批第三方安装包的用户走各自官网，完整包**故意不含**它们。

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

### 旧 7z 完整包路线：已下线（不要再跑）

2026-09-13 起不再打 7z 完整包：新用户走 zip 完整包（README 唯一入口），资料库变动走增量包，
没有任何用户需要那条 6.2 GB 的路线了。历史命令与踩坑记录不再保留在本文件
（需要时看 git 历史里本节的旧版本）。

**遇到「用户要那批第三方安装包」时的答复**：完整包**故意不含**它们（CCS 安装包 / 视觉 SDK /
VSCode 等约 5.4 GB，几乎不变、只在装机时用一次）；去各自官网下载即可，已装用户本机那份不会被删。

## 附件命名注意

**附件一律用 ASCII 文件名**：`gh release upload` 对中文文件名不可靠（历史上出现过被替换成 `default.txt`，
本地也没留下当时的实测记录）。因此：

- 现状（**继续这么做**）：`firstep-full-<tag>.zip` / `firstep-update-<tag>.zip` / `firstep-materials-<tag>-<slug>.zip`。
- 想在文件名里带中文（工单 `newuser-download/03` 的目标）**必须先实测** `gh release upload` 的中文名行为，
  并确认工具内「检查完整包」仍能发现该资产（它按**清单里的 `zip_name`** 去 release 上找同名资产，
  改名必须同步改写清单，否则整条链路判「不可下」）。测不出来就退回 ASCII 名，用 Release 说明补人话。

## Release 说明模板（新用户就看这一段）

每条 release 的说明**前两行固定**，其余随意（本版修了什么、加了什么）：

```markdown
> **新用户**：只下 `firstep-full-<tag>.zip`（约 770 MB），Windows 自带解压即可，解压后照包里的 `00-START-HERE.txt` 走。
> **已装用户**：不用看这里——打开工具「设置 → 软件更新 → 检查更新 → 一键更新」。

## 这一版有什么变化

- …（`git log v上一版..HEAD` 归纳成 3~6 条人话，别抄 commit 标题）
```

为什么固定这两行：Release 页上 8 个资产并列，新用户无从判断该下哪个；把答案写在**正文第一行**，
比指望他读完 README 更可靠（实测下载计数里 `firstep-update-*.zip` 与 `firstep-full-*.zip` 都在被下，
说明确实有人在两个 zip 之间犹豫）。

## 快速发版（给 Agent）

- **发版前先跑自检**：`python tools\check-download-docs.py`（README / Release 说明 / 包内文件三处一致性；红了先修再发）。
- **Release 说明照模板写**（本文件末「Release 说明模板」）——前两行是固定的新用户 / 已装用户指引，
  新用户就看这两行。
- 小发版：`powershell -File tools\pack-update.ps1 -Tag vX.Y.Z -Baseline <上次 files.txt>`（几分钟），产物在输出目录（缺省 `%USERPROFILE%\Desktop\firstep-pack`）。
- 完整包：`powershell -File tools\pack-full.ps1 -Tag vX.Y.Z -Baseline <上版 firstep-full-*.manifest.json>`（本机实测打包 ≤ 数分钟），产物同上；与小发版同 tag 一起上传。
  - 打完包手查一眼新用户要看的那个文件在不在：`tar.exe -tf <zip> | findstr START-HERE`
    （应输出 `00-START-HERE.txt`）。
- 大发版：`powershell -File tools\pack-materials.ps1 -Tag vX.Y.Z -Mode diff -Baseline <上版清单.json>`，发 `materials-` tag 的 Release。
- 上传完整包约 770 MB，视上行带宽需几分钟到十几分钟，**用后台任务跑，别阻塞等待**；小发版约 0.3 GB，可一并后台传。
- **发完再跑一次自检**（此时线上已有新 tag）：`python tools\check-download-docs.py` ——
  它会拿**最新 release** 校验，正好确认这一版的 README 体积口径与 Release 说明都对得上。
