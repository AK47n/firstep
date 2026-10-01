# 04 — 打包（更新包 + 完整包）→ tag/推送 → Release → 八件对账 → 联网自检

**要做什么：** 把 v1.4.3 的八件套发到用户手上：两个 zip ＋ 两份清单 ＋ 两份 sha256 ＋ 删除清单；
Release 说明按模板写（头两行给新用户 / 已装用户），并点名**三条文字变清楚**与**浅色焊盘换色**。

**被谁阻塞：** 02（门禁三连全绿）、03（沙箱验收过）。

**状态：** claimed

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

### 读数

（做完填：门禁三连 / 打 tag 时闸门那一发 / 更新包体积 / 完整包体积 / sha256 / tag 与远端 / Release / 联网自检 / 下一版基线）
