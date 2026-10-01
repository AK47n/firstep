# 02 — 门禁三连 → 打包 → 打 tag 推送 → Release 上传 → 联网自检

**要做什么：** 把 v1.4.2 的八件套发到用户手上：两个 zip + 两份清单 + 两份 sha256 + 删除清单，
Release 说明按模板写（头两行给新用户 / 已装用户），并点名**不可选形态三处**的样子变了。

**被谁阻塞：** 01（版本号同步与自检先过）。

**状态：** resolved（2026-10-01）

- [x] 门禁三连，顺序照纪律（**先浏览器单独跑，再全量 pytest**；三段互不重叠）
- [x] 更新包：`tools\pack-update.ps1 -Tag v1.4.2 -Baseline …update-v1.4.1.files.txt`
- [x] 完整包：`tools\pack-full.ps1 -Tag v1.4.2 -Baseline …full-v1.4.1.manifest.json`
- [x] 包内抽检（`VERSIONS.md` 首块 / `__version__` / 不该进包的三处 / `00-START-HERE.txt`）+ 两个 zip 实算 sha256
- [x] 本地打 annotated tag `v1.4.2` → `c9d0b327`（打包那一刻的 CHANGELOG 提交；tag 对象 `8f2784a9`）
- [x] 推送 `main` + `v1.4.2`（钉 IP `20.27.177.113` + `postBuffer`；**一次过**）
- [x] `gh release create` + 八件资产上传 + **服务端 size 逐件对账（8/8）**
- [x] 联网自检 `python tools\check-download-docs.py` → **PASS**

## 读数

| 项 | 值 |
|---|---|
| 门禁三连（本机现跑，树冻结后） | 前端 `node --test "tests/js/*.test.mjs"` **1845 / 0**（`probe-03-js-gate.txt`）；浏览器 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` **61 / 0**（`probe-03-browser-gate.txt`，**单独跑**，174.3 s）；全量 `pytest -q` **5694 passed + 11 skipped**（`probe-03-pytest.txt`，420.1 s） |
| 打 tag 时 pre-push 闸门（**独立复核一遍**） | 前端 **1845 / 0**、浏览器 **61 / 0**、pytest **5694 passed + 11 skipped**（105.9 s，闸门自带 `-n auto`）——读数 `push-01.txt` |
| 更新包 | `301,981,072` B（302.0 MB）；产品文件 **2939** 条 / 候选 7273；删除清单 2231 条；sha256 `1518774e…` |
| 完整包 | `791,840,471` B（**单卷** 755.2 MB）；包内 **8212** 个文件（原始 1030.6 MB）；资料库 12 批次 / 5066 文件；sha256 `ebd188a1…` |
| 包内抽检 | `VERSIONS.md` 首块 = `## v1.4.2 (2026-10-01)`；`__init__.py` = `1.4.2`；`.scratch/` / `.venv/` / `sources/materials` 命中 **0**；`00-START-HERE.txt` 在完整包内；两个 zip **实算 sha256 = `sha256.txt`** |
| tag / 远端 | annotated `v1.4.2` → 对象 `8f2784a9`，解引用 = `c9d0b327`；`git ls-remote` 实测 `refs/heads/main` = `c9d0b327`、`refs/tags/v1.4.2` = `8f2784a9`；推送报告 `0d313294..c9d0b327 main -> main` ＋ `[new tag] v1.4.2` |
| Release | `https://github.com/AK47n/firstep/releases/tag/v1.4.2`；**八件资产服务端 size 与本地逐件相同（8/8、0 处不一致）** |
| 联网自检 | `tools\check-download-docs.py` **PASS**（三组全 `[OK]`；`/releases/latest` = v1.4.2、资产 8 件、README「约 800 MB」↔ 线上 792 MB、「约 296 MB」↔ 302 MB）——读数 `post-publish-check.txt` |
| 下一版基线 | 更新包 `firstep-update-v1.4.2.files.txt`；完整包 `firstep-full-v1.4.2.manifest.json`（都在 `%USERPROFILE%\Desktop\firstep-pack`） |

## 网络那条（本轮实测，下次直接用）

1. **推送前一次性验了 6 个候选 IP**：本轮 **5 个通**（`140.82.113.3` / `140.82.116.3` / `20.27.177.113` /
   `20.200.245.247` / `4.208.26.197`），`140.82.114.3` 当场 `Recv failure: Connection was reset`——
   而它正是上一轮"换过去就通"的那个。**验过的 IP 只保证那一刻**这条又实锤一次。
2. **推送一次过**：`git -c http.curloptResolve=github.com:443:20.27.177.113 -c http.postBuffer=524288000
   push origin main v1.4.2` → `0d313294..c9d0b327 main -> main` ＋ `[new tag] v1.4.2`。
   本轮**没有**用到 `FIRSTEP_PREPUSH=select-only`（那是上次被掐断后的补救）。
3. ⚠ **推 tag 必然触发 pre-push 整套**（`tools/prepush.py` 认 tag → pytest + 前端 + 浏览器），
   所以"本地已经跑过三套门禁"省不掉这一次复跑——预留十几分钟，别当成卡死。
   闸门的 pytest 走 `-n auto`（105.9 s），比本地那一发（420.1 s）快得多，**两者不是同一把尺**。
4. ⚠ 钩子输出的中文在 `push-01.txt` 里是乱码（GBK 管道），**读数看数字行**（`pass N` / `fail M` /
   `N passed`）即可，别去读那些方块字。
