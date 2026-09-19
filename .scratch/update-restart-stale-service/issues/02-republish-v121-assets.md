# 02 — 重打并重传 v1.2.1 两套资产（同 tag 换资产）

**要做什么：** 让**修复真的到用户手上**，并且让真机验收有东西可下。线上那份 v1.2.1 的包里，
`start-app.bat` 与我们修之前的工作树**逐字节相同**（sha256 `88a9c45b9917…` 三处相等：工作树 /
v1.1.1 全量包清单 / v1.2.1 全量包清单）——**修复不在线上包里**，所以不重发就永远到不了用户手上。

**被谁阻塞：** 01（要先有修好的、已提交的工作树）。

**状态：** ready-for-agent

## 做法（版本号不动）

1. `powershell -File tools\pack-update.ps1 -Tag v1.2.1 -Baseline <firstep-pack\firstep-update-v1.1.1.files.txt>`
2. `powershell -File tools\pack-full.ps1 -Tag v1.2.1 -Baseline <firstep-pack\firstep-full-v1.1.1.manifest.json>`
3. `gh release upload v1.2.1 <8 件> --clobber`——**大件先传、`*.sha256.txt` 最后传**，
   把「新 zip 配旧 sha256」的不一致窗口压到最小。

## 验收标准

- [ ] 打包前 `powershell -File tools\preflight.ps1` 四项全绿（三处版本号 / 母版编码钉 / 下载文档 / README 版本行）
- [ ] 打包前工作树干净（`pack-*.ps1` 默认拒绝脏树；**先提交修复再打包**，包内容 = 那笔提交）
- [ ] **自校验（判据强）**：重打出来的 `firstep-update-v1.2.1.removed.txt` 与 `firstep-full-v1.2.1.removed.txt`
      与线上那份**逐字节相同**——本次改动只增不删，若不同说明基线选错（换了基线就会把大批文件误判成删除）
- [ ] 两套资产各自 `.sha256.txt` 与本地 zip 的实算 sha256 一致（sha256sum 格式，更新器按它校验）
- [ ] 更新包内 `start-app.bat` 的 sha256 **不再等于** `88a9c45b9917…`，且等于工作树那份（修复真进包了）
- [ ] 线上 8 个附件齐全、字节数与本地一致（`gh api repos/AK47n/firstep/releases/tags/v1.2.1`）
- [ ] **不回改 tag**：本地与线上 `v1.2.1` tag 仍指向原提交（照 v1.2.0 两次重发的先例），
      在 `local-environment` 第 3 节如实记「资产内容 = 重发时的 main，tag 未动」
- [ ] 重发后再跑一次 `python tools\check-download-docs.py`（联网版：拿线上最新 release 校验 README 体积口径）
- [ ] 如实记账**用户可见代价**：已经装了旧 v1.2.1 的用户**不会收到更新提示**（检查更新比的是版本号），
      与 v1.2.0 两次重发留下的缺口同源
