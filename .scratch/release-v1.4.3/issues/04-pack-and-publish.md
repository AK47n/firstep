# 04 — 打包（更新包 + 完整包）→ tag/推送 → Release → 八件对账 → 联网自检

**要做什么：** 把 v1.4.3 的八件套发到用户手上：两个 zip ＋ 两份清单 ＋ 两份 sha256 ＋ 删除清单；
Release 说明按模板写（头两行给新用户 / 已装用户），并点名**三条文字变清楚**与**浅色焊盘换色**。

**被谁阻塞：** 02（门禁三连全绿）、03（沙箱验收过）。

**状态：** resolved（2026-10-01）

- [ ] 更新包：`powershell -File tools\pack-update.ps1 -Tag v1.4.3 -Baseline <…update-v1.4.2.files.txt>`
- [ ] 完整包：`powershell -File tools\pack-full.ps1 -Tag v1.4.3 -Baseline <…full-v1.4.2.manifest.json>`
- [ ] 包内抽检（`VERSIONS.md` 首块 / `__version__` / `.scratch` + `.venv` + `sources/materials` 命中 0 /
      `00-START-HERE.txt` 在完整包内）＋ 两个 zip **实算 sha256 = `sha256.txt`**
- [ ] 本地打 annotated tag `v1.4.3` → 打包那一刻的 CHANGELOG 提交
- [ ] 推送 `main` ＋ `v1.4.3`（**推 tag 会触发 pre-push 整套复跑**，十几分钟；
      用 `-c http.curloptResolve=github.com:443:<当场验过的 IP> -c http.postBuffer=524288000`）
- [ ] `gh release create` ＋ 八件资产上传 ＋ **服务端 size 逐件对账（8/8）**
- [ ] 联网自检 `python tools\check-download-docs.py` → **PASS**（读数 `post-publish-check.txt`）
- [ ] 读数表写进票尾；提交信息中文

## Comments

### 读数（2026-10-01）

| 项 | 值 |
|---|---|
| 门禁三连（本机现跑，树冻结后） | 前端 `node --test "tests/js/*.test.mjs"` **1847 / 0**（`js-gate.txt`，15.5 s）；浏览器 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` **61 / 0**（`browser-gate.txt`，**单独跑**，228.9 s）；全量 `pytest -n auto -q` **5694 passed + 11 skipped**（`pytest.txt`，201.3 s） |
| 打 tag 时 pre-push 闸门（**独立复核一遍**） | 前端 **1847 / 0**、浏览器 **61 / 0**（241.0 s）、pytest **5694 passed + 11 skipped**（194.0 s）——读数 `push-01.txt`（与上一行同数） |
| 更新包 | **`301,994,538` B（288.0 MB）**；产品文件 **2939** 条 / 候选 7516；删除清单 2231 条；sha256 `edb80903…` |
| 完整包 | **`791,853,978` B（单卷 755.2 MB）**；包内 **8212** 个文件（解压 1,080,697,511 B = 1030.6 MB）；资料库 12 批次 / 5066 文件；sha256 `006af16b…` |
| 包内抽检（`check-packs.py`） | `VERSIONS.md` 首块 = `## v1.4.3 (2026-10-01)`；`__init__.py` = `1.4.3`；禁止面命中 **0**；`00-START-HERE.txt` 在完整包内；**两个 zip 实算 sha256 = 边车 `.sha256.txt`**（`pack-03-inspect.txt`） |
| tag / 远端 | annotated `v1.4.3` → 对象 `95380bfe`，解引用 = **`47067b14`**（打包那一刻的 CHANGELOG 提交）；推送报告 `01beebce..47067b14 main -> main` ＋ `[new tag] v1.4.3`；`git ls-remote` 复验两端同值 |
| Release | `https://github.com/AK47n/firstep/releases/tag/v1.4.3`；标题回读**逐字一致**（`release-title-readback.txt`） |
| 八件对账 | `verify-assets.py` → **8/8 一致、0 处不一致**（`verify-01-assets.txt`）；两个 zip 服务端 size 与本地逐字节同值（`301,994,538` / `791,853,978`） |
| 联网自检 | `tools\check-download-docs.py` → **PASS**（三组全 `[OK]`：`/releases/latest` = v1.4.3、资产 8 件、README「约 800 MB」↔ 线上 792 MB、「约 296 MB」↔ 302 MB、Release 说明前几行两行固定指引在场）——读数 `post-publish-check.txt` |
| 下一版基线 | `firstep-update-v1.4.3.files.txt` / `firstep-full-v1.4.3.manifest.json`（都在 `%USERPROFILE%\Desktop\firstep-pack`） |

### ⚠ 两条本轮踩到的（下次直接用）

1. **打包脚本会拒绝"脏工作树"，而"读数落盘"本身就会把它弄脏**：第一发两条打包命令**都**被拒
   （`[错误] 工作树存在未提交的 tracked 变更`）——原因是落盘读数的 `.txt` 是 tracked 的，
   写一次就脏一次。顺序要摆成这样：**先提交手上的改动 → 打更新包 → 提交更新包读数 →
   打完整包 → 再提交读数**（本轮就是这么修好的），或者明写 `-AllowDirty`（不推荐：那是把闸门关掉）。
2. **`check-packs.py` 第一版判据写错**（真红过一次，不是产品问题）：把 `sources/materials`
   也列进了"不该进包"——**完整包本来就带资料库内容文件**（12 批次 / 5066 个），那三处禁止面
   里只有 `.scratch/` 与 `.venv/` 是两个包共有的。改口径后两包全过。**教训与工单 03 那条同源：
   红了先自证量具。**

### 网络那条（本轮实测）

- 推送前一次性验了 6 个候选 IP：**6/6 全通**（`140.82.113.3` / `140.82.114.3` / `140.82.116.3` /
  `20.27.177.113` / `20.200.245.247` / `4.208.26.197`，判据 = 拿回来的是真 git 广告）。
- 推送用 `20.27.177.113` **一次过**（`git -c http.curloptResolve=… -c http.postBuffer=524288000 push origin main v1.4.3`）。
- ⚠ **推 tag 必然触发 pre-push 整套复跑**（本轮 ≈ 7.5 分钟：pytest 194 s + 前端 16 s + 浏览器 241 s）——
  本地已跑过三套门禁也省不掉这一次，预留时间、别当卡死。
- ⚠ **`gh release upload` 这一段的上行很慢**（本轮实测网卡发送 ≈ **0.22 MB/s**，
  1.08 GB 的两个 zip 要跑一个多小时；`gh` 对多个资产是并发传的，所以中途看资产清单会看到
  "小件都到了、两个 zip 还没影"——那不是失败）。**用后台任务跑，别阻塞等。**
- ⚠ **`gh release view … > 文件` 写出来是 UTF-16LE**（PowerShell 5.1 的 `>`），
  直接 `json.loads(read_text(encoding="utf-8"))` 会炸 `0xff` 开头——本轮真踩过。
  取数的正解：`subprocess.run(..., text=True, encoding="utf-8")`（`verify-assets.py` 就是那么写的）。
