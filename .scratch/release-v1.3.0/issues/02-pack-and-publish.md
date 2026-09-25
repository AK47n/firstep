# 02 — 打包 + tag + 上传 v1.3.0 八件资产 + Release 说明

**要做什么：** 线上出现 v1.3.0 的八件套（小发版四件套 + 完整包四件套），`/releases/latest`
指向它——已装用户点「检查更新」就能拿到「硬件检测」与那三处驱动修复。

**被谁阻塞：** 01（版本号与自检就位才能打包打 tag）。

**状态：** resolved（打包与核对 2026-09-25 早先完成；**推送 + 建 Release + 传八件资产已在同日收尾轮真做完**）

- [x] 打小发版包：`tools\pack-update.ps1 -Tag v1.3.0 -Baseline <v1.2.2 files.txt>`
- [x] 打完整包：`tools\pack-full.ps1 -Tag v1.3.0 -Baseline <v1.2.2 manifest.json>`
- [x] **上传前对一次「zip 实算 vs `sha256.txt`」**（上一轮踩过截断管道把校验和写成上一版）
- [x] 完整包冒烟：`tar.exe -tf <full zip> | findstr START-HERE` → `00-START-HERE.txt`
- [x] `removed.txt` 非空（0 字节会被 GitHub 拒收）
- [x] `git tag -a v1.3.0`（本地）
- [x] `git push origin main v1.3.0`
- [x] 写 Release 说明（照 `docs/agents/releasing.md` 模板：**前两行固定**）
- [x] `gh release create` + `gh release upload` 八件资产（ASCII 文件名）
- [x] `gh release view v1.3.0` 确认八件齐全、完整包 zip 在场且体积与「约 770 MB」同量级
- [x] 打包上传后跑一次**联网版** `python tools\check-download-docs.py`
- [x] 存好本版两个清单当下一版基线

## Comments

### 落地事实（2026-09-25）

| 项 | 值 |
|---|---|
| 小发版包 | `301,635,963` B / sha256 `3c26c155d9b39e5ee1a6f7c3caf37149dd8395829c210899e3624dfcc2c4cb38`；产品文件 **2918**（v1.2.2 是 2858）/ 删除清单 **2230** 条（累计口径） |
| 完整包 | `791,495,348` B（754.8 MB）/ sha256 `29f5d55f4dcbed2b2e4427e08a56484b97858d31d02f94c26f7a47d9d01944a1`；包内文件 **8191** / 资料库基线 12 批次 5066 文件 |
| 上传前核对 | 两个 zip 的 sha256 **实算 = `sha256.txt` 记录**（逐字节相同）；`00-START-HERE.txt` 在完整包里；两个 `removed.txt` 都非空（152,960 / 155,190 B） |
| Release 说明 | `firstep-pack\release-notes-v1.3.0.md`（前两行固定：新用户只下 `firstep-full-v1.3.0.zip` / 已装用户走工具内更新） |

### 网络中断（本轮真实撞上，如实记账）

推 `main` + tag 时 `github.com:443` **连不上**（`curl` 20s 超时；同一时刻 `api.github.com`
200 正常、其它站点正常，DNS 解出 `20.205.243.166`）——`git push` 报
`RPC failed; curl 56 Recv failure: Connection was reset`。
**已确认**：推送前的 pre-push 闸门是真跑过的（整套 pytest **5523 passed + 11 skipped**，
前端门禁与浏览器门禁在它之前已过），所以卡住的只是最后那一段网络。

> **处置**：不绕过、不伪造——tag 已在本地打好，等网络恢复后 `git push origin main v1.3.0`
> 重试即可；**在推送成功之前不建 Release**（`gh release create` 会在服务端按**远端默认分支的
> HEAD**建 tag，远端还没有 main 的新提交时，那会把 tag 打到 v1.2.2 那个提交上）。

### 推送成功 + Release 上线（2026-09-25 收尾轮）

`github.com:443` 恢复可达后跑 `.scratch\release-v1.3.0\finish-publish.ps1`（退出码 **0**），四步全过：

| 步 | 读数 |
|---|---|
| ① 推 main + tag（带整套 pre-push 闸门） | `b96a9f4a..606494b1  main -> main` / `* [new tag] v1.3.0 -> v1.3.0`；闸门读数：前端门禁 **1796 passed / 0 fail**、浏览器门禁 **42 passed / 0 fail / 191.5s**、pytest **5523 passed + 11 skipped / 203.7s** |
| ② 建 Release | `https://github.com/AK47n/firstep/releases/tag/v1.3.0`（draft=false / prerelease=false） |
| ③ 传八件资产 | `gh release view` 列出八件齐全 |
| ④ 联网自检 | `python tools\check-download-docs.py` 三项全 `[OK]` → **PASS**，退出码 0（读数存 `.scratch/release-v1.3.0/post-publish-check.txt`） |

**独立复核（服务端口径，不是脚本自己的话）**：

- `gh api repos/AK47n/firstep/git/refs/heads/main` → `606494b1253c8974cbed674c8d9e7987546e824b`
  （= 本地 HEAD，`git rev-list --left-right --count origin/main...main` = `0 0`）；
- `gh api repos/AK47n/firstep/releases/latest` → `tag=v1.3.0`、`assets=8`；
- 八件资产**逐件对账「服务端 size = 本地文件 size」**：**8/8 相同、0 处不一致**
  （full zip 791,495,348 / update zip 301,635,963）；
- 两个 zip 的 sha256 **本地重算 = `sha256.txt` 记录**（`3c26c155…` / `29f5d55f…`），
  而服务端记录的字节数与本地逐字节相同——完整性这一环闭合。

**一条要更正的事前预测**：本文件此前把「tag 指向」写成 `606494b1`。实际
`git cat-file -p v1.3.0` 显示 **annotated tag 指向 `e47d9a8c`**（打包那一刻的 CHANGELOG 提交，
也正是本文件「落地事实」段记的那个），而 `606494b1` 是**其后**由 `0ea76e18` 的 post-commit
钩子生成的 `chore: 自动更新 CHANGELOG`——它按设计落在 tag 之后（「先打包打 tag，再落账本」）。
所以 tag 打在对的提交上，**没有落到 v1.2.2 那个提交上**。
