# 02 — 打包 + tag + 上传 v1.3.1 八件资产 + Release 说明

**要做什么：** 线上出现 v1.3.1 的八件套（小发版四件套 + 完整包四件套），`/releases/latest`
指向它——已装用户点「检查更新」就能拿到 `hwcheck-hygiene` 这一批。

**被谁阻塞：** 01（版本号与自检就位才能打包打 tag）。

**状态：** ready-for-agent

- [ ] 打小发版包：`tools\pack-update.ps1 -Tag v1.3.1 -Baseline <v1.3.0 files.txt>`
- [ ] 打完整包：`tools\pack-full.ps1 -Tag v1.3.1 -Baseline <v1.3.0 manifest.json>`
- [ ] **上传前对一次「zip 实算 vs `sha256.txt`」**（上一轮踩过截断管道把校验和写成上一版）
- [ ] 完整包冒烟：`tar.exe -tf <full zip> | findstr START-HERE` → `00-START-HERE.txt`
- [ ] 两个 `removed.txt` 非空（0 字节会被 GitHub 拒收）
- [ ] `git tag -a v1.3.1`（本地）
- [ ] 写 Release 说明（照 `docs/agents/releasing.md` 模板：**前两行固定**），落在
      `%USERPROFILE%\Desktop\firstep-pack\release-notes-v1.3.1.md`
- [ ] `git push origin main v1.3.1`——**必须钉 IP**：
      `git -c http.https://github.com/.resolve=github.com:443:<IP> push origin main v1.3.1`
- [ ] `gh release create` + `gh release upload` 八件资产（ASCII 文件名）
- [ ] 验收只看 `gh api repos/AK47n/firstep/git/refs/heads/main` 与
      `gh api repos/AK47n/firstep/releases/latest`（**不看 curl 200**）；八件资产**逐件对
      「服务端 size = 本地 size」**
- [ ] 打包上传后跑一次**联网版** `python tools\check-download-docs.py`，读数落
      `.scratch/release-v1.3.1/post-publish-check.txt`
- [ ] 存好本版两个清单当下一版基线

## Comments

> **顺序纪律**：推送成功之前**不建 Release**——`gh release create` 会在服务端按**远端默认分支的
> HEAD** 建 tag，远端还没收到 main 的新提交时会把 tag 打到旧提交上（v1.3.0 那一轮记过这条）。
