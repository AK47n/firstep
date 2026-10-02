# 03 — 打包 → 发布 → 上传 → 账本收口

**要做什么：** 把要发的树打成两个包（基线 = v1.4.3 两份清单）、抽检、打 annotated tag、推送、
建 Release 传八件资产、服务端对账、联网自检，最后把三份账（交接区 / 台账 / 本目录）收口。

**被谁阻塞：** 02（门禁全绿之后才打包）。

**Status:** pending

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

### 落地事实

（做完回填）
