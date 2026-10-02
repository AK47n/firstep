# 03 — 打包 → 发布 → 上传 → 账本收口

**要做什么：** 把要发的树打成两个包（基线 = v1.4.3 两份清单）、抽检、打 annotated tag、推送、
建 Release 传八件资产、服务端对账、联网自检，最后把三份账（交接区 / 台账 / 本目录）收口。

**被谁阻塞：** 02（门禁全绿之后才打包）。

**Status:** resolved（2026-10-02）

- [ ] **打更新包**：`powershell -File tools\pack-update.ps1 -Tag v1.4.4 -Baseline firstep-update-v1.4.3.files.txt`
      → `pack-01-update.txt`；**先把工作树弄干净**（本机事实①：打包脚本拒脏树，而落盘读数会把树弄脏）
- [ ] 提交更新包读数 → **再打完整包**：`powershell -File tools\pack-full.ps1 -Tag v1.4.4
      -Baseline firstep-full-v1.4.3.manifest.json` → `pack-02-full.txt`；再提交读数
- [ ] **包内抽检**（照 `.scratch/release-v1.4.3/check-packs.py` 复制一支改 tag/日期）→ `pack-03-inspect.txt`
- [ ] `git tag -a v1.4.4 -m "firstep v1.4.4"`（annotated）
- [ ] 推送：先按内容验 IP（`git -c http.curloptResolve=… ls-remote origin main`），
      `git push origin main v1.4.4`；⚠ pre-push 会整套复跑（十几分钟，不是卡死）→ `push-01.txt`
- [ ] `gh release create v1.4.4 --title 'firstep 电赛工程生成器 · v1.4.4（浅色主题引脚配色变清楚）'
      --notes-file release-notes-v1.4.4.md --repo AK47n/firstep`
- [ ] **两发 `gh release upload`**（八件、ASCII 名）；⚠ 上行极慢 ⇒ **后台任务跑**
- [ ] **服务端逐件对账**：`gh release view --json assets` → Python 解析（别用 `--jq '\(…)'`，
      PowerShell 会拆参数）比 8 件 size 与本地逐件相同
- [ ] `python tools\check-download-docs.py` → **PASS** → `post-publish-check.txt`
- [ ] **账本收口**：
      `local-environment.md` §0（新区块：本批已发 / 落差归零 / 版本与 tag 与八件资产读数 / 基线指针）
      ＋ §3（版本表补 v1.4.4 行、基线换成 v1.4.4 两份、旧基线降级历史）
      ＋ §1（沙箱状态：**本轮没动沙箱**，仍是 v1.4.3）＋ §2（端口实况）；
      `backlog.md` §35 的「本轮不发版」划掉；
      `.scratch/pin-type-contrast/README.md` 的「本轮不发版」回改；
      本目录 `README.md`（如建）与三张单的状态
- [ ] 提交信息中文；最后确认 `git rev-list --left-right --count origin/main...main` = **`0 0`**

## Comments

### 落地事实（2026-10-02）

| 项 | 值 | 落点 |
|---|---|---|
| 更新包 | **302,015,729 B**（288.0 MB）；产品文件 **2939** 条 / 候选 8219 条；删除清单 **2231** 条（累计口径） | `pack-01-update.txt` |
| 完整包 | **791,875,154 B**（755.2 MB）；包内 **8212** 文件（原始 1030.7 MB）；资料库 12 批次 / 5066 文件 | `pack-02-full.txt` |
| 包内抽检 | **全过**——两个包禁止面（`.scratch` / `.venv`；更新包另加 `sources/materials`）命中 **0**、`VERSIONS.md` 首块 = `## v1.4.4 (2026-10-02)`、`__version__ = "1.4.4"`、`00-START-HERE.txt` 在完整包内、两个 zip 实算 sha256 与 `.sha256.txt` **逐字相同** | `pack-03-inspect.txt` |
| tag | annotated `v1.4.4` → 对象 **`46273844`**，解引用 = **`82cd7753`**（打包那一刻的 CHANGELOG 提交） | `git rev-list -n 1 v1.4.4` |
| 推送 | **一次过**：`81396d20..82cd7753  main -> main` ＋ `* [new tag] v1.4.4`；pre-push 闸门**独立复核**前端 **1848 / 0**、浏览器 **61 / 0**（182.3 s）、pytest **5695 + 11 skipped**（112.1 s） | `push-01.txt` |
| Release | `https://github.com/AK47n/firstep/releases/tag/v1.4.4`，标题 = `firstep 电赛工程生成器 · v1.4.4（浅色主题引脚配色变清楚）` | `https://.../releases/tag/v1.4.4` |
| 上传 | 八件一次传完（**约 25 分钟**：09:31 → 09:56），退出码 0 | `upload-01.txt` |
| 八件对账 | **8 / 8 一致**（服务端 size 与本地逐件相同，0 处不一致） | `verify-01-assets.txt` |
| 联网自检 | **PASS**（三组全 `[OK]`：README 获取方式 / 线上最新版 v1.4.4 八件＋体积口径 / Release 说明前几行） | `post-publish-check.txt` |
| 账本 | `local-environment.md` §0（新区块 ＋ 上一条降级为「上一批」）§1（沙箱本轮没动）§2（8000 仍未跑、8020 已释放、孤儿 PID 21848/10396 仍在）§3（v1.4.4 行 ＋ 基线换新）；`backlog.md` §35；`.scratch/pin-type-contrast/{README,spec,issues/05}` | 本次提交 |

- **打包顺序照本机事实①走**（先提交手上的改动 → 打更新包 → 提交读数 → 打完整包 → 再提交读数），
  **两次打包一次过**（上一轮各被拒过一次）。
- **IP 现验现用**：推送前一次性按内容验 6 个候选（`140.82.114.3` / `140.82.113.3` / `140.82.116.3` /
  `20.27.177.113` / `20.200.245.247` / `4.208.26.197`）**六个全通**，用 `20.27.177.113` 一次推成。
- **上传比上一轮快得多**：1.08 GB **约 25 分钟**（上一轮 ≈ 0.22 MB/s、一个多小时）；
  中途查资产清单会看到「小件都到了、两个 zip 还没影」——**那不是失败**（`gh` 对多资产是并发传的）。
