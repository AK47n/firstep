# 04 — 打包 + tag + 上传 v1.4.0 八件资产 + Release + 发布后账本

**要做什么：** 线上出现 v1.4.0 的八件套（小发版四件套 + 完整包四件套），`/releases/latest` 指向它——
已装用户点「检查更新」就能拿到全站观感这一批；新用户走完整包拿到同一份内容。

**被谁阻塞：** 01（版本号）/ 02（门禁与读数）/ 03（沙箱真机验收）。

**状态：** ready-for-agent

- [ ] 打包前确认**工作树干净**（两次打包器都拒绝脏工作树——工单标记与读数落盘本身是变更）
- [ ] 打小发版包：`tools\pack-update.ps1 -Tag v1.4.0 -Baseline <v1.3.1 files.txt>` → 落 `pack-update.txt`
- [ ] 打完整包：`tools\pack-full.ps1 -Tag v1.4.0 -Baseline <v1.3.1 manifest.json>` → 落 `pack-full.txt`
- [ ] **上传前对一次「zip 实算 vs `sha256.txt`」**（两个包都逐字节相同）
- [ ] 完整包冒烟：`tar.exe -tf <full zip> | findstr START-HERE` → `00-START-HERE.txt`
- [ ] 两个 `removed.txt` 非空；更新包内容抽检（`VERSIONS.md` 首块 = v1.4.0、`__version__ = "1.4.0"`、
      `.scratch` / `.venv` / `sources/materials` 命中 0）
- [ ] `git tag -a v1.4.0`（本地，annotated）
- [ ] 写 Release 说明（前两行固定：新用户只下 `firstep-full-v1.4.0.zip` / 已装用户走工具内更新），
      落在 `firstep-pack\release-notes-v1.4.0.md`
- [ ] `git push origin main v1.4.0`——**钉 IP**：`-c http.curloptResolve=github.com:443:<验过的 IP>`
      `-c http.postBuffer=524288000`（候选 IP 按**内容**验：拿回来的得是 `001e# service=git-upload-pack…`）
- [ ] `gh release create` + `gh release upload` 八件资产（ASCII 文件名）
- [ ] 验收只看 `git ls-remote` / `gh api .../git/refs/...` 与 `releases/latest`；八件资产**逐件对
      「服务端 size = 本地 size」**
- [ ] 打包上传后跑**联网版** `python tools\check-download-docs.py` → PASS，读数落盘
- [ ] **发布后按事实更新** `docs/agents/local-environment.md`：第 0 节（线上最新 = v1.4.0、
      这四批"到用户手上了"、落差归零）+ 第 3 节（发布状态表加一行 v1.4.0 与下一版基线）
- [ ] 本版两个清单已成下一版基线；四张工单全部 resolved；提交信息中文

## Comments

（做完补：字节 / sha256 / 清单条数 / 服务端对账 / 联网自检 / 账本改了哪几段）
