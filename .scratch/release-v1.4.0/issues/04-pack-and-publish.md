# 04 — 打包 + tag + 上传 v1.4.0 八件资产 + Release + 发布后账本

**要做什么：** 线上出现 v1.4.0 的八件套（小发版四件套 + 完整包四件套），`/releases/latest` 指向它——
已装用户点「检查更新」就能拿到全站观感这一批；新用户走完整包拿到同一份内容。

**被谁阻塞：** 01（版本号）/ 02（门禁与读数）/ 03（沙箱真机验收）。

**状态：** resolved

- [x] 打包前确认**工作树干净**（两次打包器都拒绝脏工作树——工单标记与读数落盘本身是变更）
- [x] 打小发版包：`tools\pack-update.ps1 -Tag v1.4.0 -Baseline <v1.3.1 files.txt>` → 落 `pack-update.txt`
- [x] 打完整包：`tools\pack-full.ps1 -Tag v1.4.0 -Baseline <v1.3.1 manifest.json>` → 落 `pack-full.txt`
- [x] **上传前对一次「zip 实算 vs `sha256.txt`」**（两个包都逐字节相同）
- [x] 完整包冒烟：`tar.exe -tf <full zip> | findstr START-HERE` → `00-START-HERE.txt`
- [x] 两个 `removed.txt` 非空；更新包内容抽检（`VERSIONS.md` 首块 = v1.4.0、`__version__ = "1.4.0"`、
      `.scratch` / `.venv` / `sources/materials` 命中 0）
- [x] `git tag -a v1.4.0`（本地，annotated）
- [x] 写 Release 说明（前两行固定：新用户只下 `firstep-full-v1.4.0.zip` / 已装用户走工具内更新），
      落在 `firstep-pack\release-notes-v1.4.0.md`
- [x] `git push origin main v1.4.0`——**钉 IP**：`-c http.curloptResolve=github.com:443:<验过的 IP>`
      `-c http.postBuffer=524288000`（候选 IP 按**内容**验：拿回来的得是 `001e# service=git-upload-pack…`）
- [x] `gh release create` + `gh release upload` 八件资产（ASCII 文件名）
- [x] 验收只看 `git ls-remote` / `gh api .../git/refs/...` 与 `releases/latest`；八件资产**逐件对
      「服务端 size = 本地 size」**
- [x] 打包上传后跑**联网版** `python tools\check-download-docs.py` → PASS，读数落盘
- [x] **发布后按事实更新** `docs/agents/local-environment.md`：第 0 节（线上最新 = v1.4.0、
      这四批"到用户手上了"、落差归零）+ 第 3 节（发布状态表加一行 v1.4.0 与下一版基线）
- [x] 本版两个清单已成下一版基线；四张工单全部 resolved；提交信息中文

## Comments

### 落地事实（2026-09-29）

| 项 | 小发版包 | 完整包 |
|---|---|---|
| 文件 | `firstep-update-v1.4.0.zip` | `firstep-full-v1.4.0.zip` |
| 字节 | **301,895,533**（287.9 MB） | **791,754,929**（755.1 MB，单卷） |
| sha256 | `fc82dae05531281526f9a0038250045856183848b657cca96804c493c93eeff0` | `b8c0975cde59c492a3f11887633ca7c828638eaf01def0760b6e960031207fe2` |
| 清单 | 产品文件 **2937** 条（候选 6860）/ 删除清单 **2231** 条 | 包内文件 **8210** 个（原始 1030.4 MB）/ 资料库基线 12 批次 **5066** 文件 / 删除清单 2231 条 |
| 上传前核对 | zip 实算 sha256 **= `sha256.txt`** | 同上 + `00-START-HERE.txt` 在包内 |

- 读数落盘：`pack-update.txt` / `pack-full.txt` / `publish.txt`（2053 行，含 pre-push 闸门全量输出）/
  `server-verify.txt`（都在本目录）。
- 更新包**内容**抽检（不只是体积）：包内 `VERSIONS.md` 首块 = `## v1.4.0 (2026-09-29)`、
  `src/contest_generator/__init__.py` 的 `__version__ = "1.4.0"`、`.scratch` / `.venv` /
  `sources/materials` 命中 **0**；包内条目 2937 条与 `files.txt` 同数。

### 服务端验收（口径：只看 git ref 与 Release API）

| 判据 | 读数 |
|---|---|
| `refs/heads/main` | `d527c65c83da5bfadfb0865ba70c4d8846290733`（= 本地 HEAD；`origin/main...main` = `0 0`） |
| `refs/tags/v1.4.0` | tag 对象 `686e83766bbd31365e5cec908df400527c3d0c8f` → 解引用 `d527c65c`（annotated） |
| `releases/latest` | `tag_name = v1.4.0`、`assets = 8`、`draft = false`、`prerelease = false` |
| 八件资产 size | **8/8 与本地逐件相同、0 处不一致**（791,754,929 / 301,895,533 / …） |
| 联网自检 | `check-download-docs.py` 三组全 `[OK]` → **PASS**（README 体积口径 792 MB / 302 MB / clone 291 MiB 同量级） |
| Release | `https://github.com/AK47n/firstep/releases/tag/v1.4.0`（`created 05:30:15Z` / `published 05:36:18Z`） |

### 网络这一段（本机中间人那套老问题，本轮又量了一遍）

- **键名照旧是 `http.curloptResolve`**（不是 `http.https://github.com/.resolve`）。
- 推送前一次性验了 **6 个候选 IP**：`140.82.114.3` / `140.82.113.3` / `140.82.116.3` / `20.27.177.113` /
  `20.200.245.247` **按内容验通过**（`001e# service=git-upload-pack…` + 真 ref），
  `4.208.26.197` **54 秒后 `Recv failure: Connection was reset`**。
- **推送用的 `140.82.114.3` 一次过**（`git -c http.curloptResolve=… -c http.postBuffer=524288000 push origin main v1.4.0`，
  没出现 v1.3.1 那种白推）。但**推送后复验时它 reset 了一次**，换 `20.27.177.113` 立刻通
  ⇒ **"验过的 IP"只保证那一刻**；失败就换一个，别怀疑认证。
- 验收只认 git ref 与 Release API（`curl` 200 不算数）。

### pre-push 闸门（推 tag 时真跑，独立复核了发版前的读数）

| 闸门 | 读数 |
|---|---|
| 前端门禁 | **1840 passed / 0 fail** |
| 浏览器门禁 | **61 passed / 0 fail**（189.9s） |
| 全套 pytest | **5656 passed + 11 skipped / 0 failed**（116.8s） |

与工单 02 的那一轮逐字相同（1840 / 61 / 5656+11）——两次独立跑给同一读数。

### 账本改了什么（发布后当场）

- **第 0 节**：交接区标题改成「v1.4.0 已发布 / 落差归零」，加一整块「✅ 最新发布」——
  四批内容、发布表（线上最新 / 远端 main / tag / Release / 联网自检 / 发版产物留档）、
  发版前三道关的读数、打包产物读数、沙箱真机验收 33/33、以及三条本机新事实
  （IP 成功率会变、第一次推就过、`readings.py --out-dir` 只认仓库内路径）。
- **第 2 节**：8000 / 8020 两行按实测改写；补一条**控制台显示坑**（`Select-Object` 把表格列渲染成空行，
  同一轮误导过两次）+ 读数前那一眼命中的 4 个 python 进程（含 9/28 的两个孤儿，本轮未清）。
- **第 3 节**：**这一节此前长期停在 v1.2.2**（v1.3.0 / v1.3.1 两轮只更新了第 0 节）——
  本轮一次补齐 **v1.4.0 / v1.3.1 / v1.3.0** 三行 + 把 v1.2.2 行标成"已被取代" +
  基线表换成 v1.4.0 那三件 + Release 说明原稿。
