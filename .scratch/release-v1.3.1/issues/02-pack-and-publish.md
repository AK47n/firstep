# 02 — 打包 + tag + 上传 v1.3.1 八件资产 + Release 说明

**要做什么：** 线上出现 v1.3.1 的八件套（小发版四件套 + 完整包四件套），`/releases/latest`
指向它——已装用户点「检查更新」就能拿到 `hwcheck-hygiene` 这一批。

**被谁阻塞：** 01（版本号与自检就位才能打包打 tag）。

**状态：** resolved

- [x] 打小发版包：`tools\pack-update.ps1 -Tag v1.3.1 -Baseline <v1.3.0 files.txt>`
- [x] 打完整包：`tools\pack-full.ps1 -Tag v1.3.1 -Baseline <v1.3.0 manifest.json>`
- [x] **上传前对一次「zip 实算 vs `sha256.txt`」**（两个包都逐字节相同）
- [x] 完整包冒烟：`tar.exe -tf <full zip> | findstr START-HERE` → `00-START-HERE.txt`
- [x] 两个 `removed.txt` 非空（2231 / 2231 行）
- [x] `git tag -a v1.3.1`（本地）
- [x] 写 Release 说明（前两行固定），落在 `firstep-pack\release-notes-v1.3.1.md`
- [x] `git push origin main v1.3.1`——**钉 IP**：`-c http.curloptResolve=github.com:443:140.82.114.3`
      `-c http.postBuffer=524288000`（键名与理由见下）
- [x] `gh release create` + `gh release upload` 八件资产（ASCII 文件名）
- [x] 验收只看 `git ls-remote` / `gh api .../git/refs/...` 与 `releases/latest`；八件资产**逐件对
      「服务端 size = 本地 size」→ 8/8 相同、0 处不一致**
- [x] 打包上传后跑**联网版** `python tools\check-download-docs.py` → **PASS**（退出码 0），
      读数 `.scratch/release-v1.3.1/post-publish-check.txt`
- [x] 本版两个清单已成下一版基线（见下表）

## Comments

### 落地事实（2026-09-27）

| 项 | 小发版包 | 完整包 |
|---|---|---|
| 文件 | `firstep-update-v1.3.1.zip` | `firstep-full-v1.3.1.zip` |
| 字节 | **301,813,614**（287.8 MB） | **791,672,980**（755.0 MB） |
| sha256 | `bb57333271cb362a358e6bd431a99f296e9d8c7f5d951cd6fc8081fb33995cc5` | `dcba7726ae6c4b2439e98067e4e017af6862773c9ce4c43597b8661483c68c6e` |
| 清单 | 产品文件 **2933** 条（候选 6484）/ 删除清单 **2231** 条 | 包内文件 **8206** 个（原始 1030.2 MB）/ 资料库基线 12 批次 5066 文件 / 删除清单 2231 条 |
| 上传前核对 | zip 实算 sha256 **= `sha256.txt`** | 同上 + `00-START-HERE.txt` 在包内 |
| 服务端对账 | 4/4 相同 | 4/4 相同（`gh api .../releases/latest`） |

- 读数落盘：`pack-update-v1.3.1.txt` / `pack-full-v1.3.1.txt` / `upload-v1.3.1.txt` /
  `push-v1.3.1-try3.txt` / `post-publish-check.txt`（都在本目录）。
- 更新包另做了一次**内容**抽检（不只是体积）：包内 `VERSIONS.md` 首块 = `## v1.3.1 (2026-09-27)`、
  `src/contest_generator/__init__.py` 的 `__version__ = "1.3.1"`、`.scratch` / `.venv` /
  `sources/materials` 命中 **0** 条。

### 服务端验收（口径：只看 git ref 与 Release API）

| 判据 | 读数 |
|---|---|
| `refs/heads/main` | `1bea22a18be2e51bde09e2293e959d086f6ee53d`（= 本地 HEAD；`origin/main...main` = `0 0`） |
| `refs/tags/v1.3.1` | tag 对象 `e95be162f14e4907d3e5fb2bd3f2029e639af4b0` → 解引用 `1bea22a1`（annotated） |
| `releases/latest` | `tag_name = v1.3.1`、`assets = 8`、`draft = false`、`prerelease = false` |
| 八件资产 size | **8/8 与本地逐件相同**（791,672,980 / 301,813,614 / …） |
| 联网自检 | `check-download-docs.py` 三组全 `[OK]` → **PASS** |

### 网络这一段的真实现场（**别再按旧账本那条命令推**）

- 第一次推送用的就是账本里那条 `git -c "http.https://github.com/.resolve=…"` ——
  **当场失败**：`fatal: unable to access ... Failed to connect to github.com port 443 after 21094 ms`，
  说明**那个键在 git 2.54.0.windows.1 上根本不生效**（git 仍按 hosts 解析到 127.0.0.1）。
  实测有效的键是 **`http.curloptResolve`**（`ls-remote` 立刻返回真 ref）。
- 换正确键后第一次推仍然被掐：`Recv failure: Connection was reset`（exit 128，一个字节没上去，
  pre-push 钩子都还没跑）。判定为中间人对 POST 体的干扰 → 换验过的 IP
  （`140.82.114.3`，连测 5/5 `ls-remote` 成功）**并加 `-c http.postBuffer=524288000`**
  （默认 1 MiB 之上走 chunked，中间人更容易掐），**第三次一次过**。
- **验收只认 git ref 与 Release API**：本轮全程有 `curl` 200 的假象（本机中间人对任意域名都可能
  答 200），IP 是按**内容**验的（拿回来的得是 `001e# service=git-upload-pack…` + 真 ref）。

### 一次被判据拦下来的真缺陷（pre-push 闸门抓的）

第一次推送跑到闸门时 **红了两条**：`tests/test_ps1_encoding.py::test_all_ps1_files_have_utf8_bom`
与 `::test_no_nonascii_ps1_without_bom` —— 本目录新写的 `finish-publish.ps1` **没有 UTF-8 BOM**
（CLAUDE.md 的硬性约定）。补 BOM 后两条转绿、重推一次过。代价是白跑一整轮 pre-push 闸门（≈5 分钟）。
**新写任何 `.ps1` 都要当场补 BOM**（`upload-assets.ps1` 这次就是写完立刻补的）。

### 推送时闸门读数（与 13 号单的基线一致）

| 闸门 | 读数 |
|---|---|
| 前端门禁 | **1830 passed / 0 fail**（8.98s） |
| 浏览器门禁 | **60 passed / 0 fail**（255.8s） |
| 全套 pytest | **5604 passed + 11 skipped**（211.48s） |
