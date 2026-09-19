# 04 — 打包 + tag + 上传 v1.2.2 八件资产 + Release 说明

**要做什么：** 线上出现 v1.2.2 的八件套（小发版四件套 + 完整包四件套），
`/releases/latest` 指向它——已装用户点「检查更新」就能拿到这三条修复。

**被谁阻塞：** 03（版本号与自检就位才能打包打 tag）。

**状态：** ready-for-agent

- [ ] 打小发版包：
      `powershell -File tools\pack-update.ps1 -Tag v1.2.2 -Baseline C:\Users\luoji\Desktop\firstep-pack\firstep-update-v1.2.1.files.txt`
- [ ] 打完整包：
      `powershell -File tools\pack-full.ps1 -Tag v1.2.2 -Baseline C:\Users\luoji\Desktop\firstep-pack\firstep-full-v1.2.1.manifest.json`
- [ ] **上传前对一次「zip 实算 vs `sha256.txt`」**（上一轮踩过：`Select-Object -First N` 接在
      `powershell -File` 后面会提前掐断上游，zip 生成了、校验和文件还是上一版的）
- [ ] 删除清单形态核对：应包含 01 摘掉的 6 件 egg-info 路径 + v1.2.1 小发版多发的那批
      `library/revise-backups/**`（累计口径）；`removed.txt` 非 0 字节（0 字节会被 GitHub 拒收）
- [ ] `git tag -a v1.2.2` **并 `git push origin main v1.2.2`**（`gh release create` 是在服务端建
      tag，本地不会自动有——想按 tag 引基线就找不到）
- [ ] 写 Release 说明（照 `docs/agents/releasing.md` 模板：**前两行固定**是新用户 / 已装用户指引），
      原稿存 `firstep-pack\release-notes-v1.2.2.md`
- [ ] `gh release create` + `gh release upload` 八件资产（ASCII 文件名）
- [ ] `gh release view v1.2.2 --repo AK47n/firstep` 确认八件齐全、完整包 zip 在场且体积与
      「约 770 MB」同量级（它是新用户唯一的安装包）
- [ ] 冒烟：`tar.exe -tf <full zip> | findstr START-HERE` 输出 `00-START-HERE.txt`
- [ ] 打包上传后跑一次**联网版**自检 `python tools\check-download-docs.py`（它拿线上最新 Release
      校验 README 体积口径与 Release 说明前两行——正好确认这一版发对了）
- [ ] 把本版两个清单存好当下一版基线：`firstep-update-v1.2.2.files.txt` /
      `firstep-full-v1.2.2.manifest.json`

## Comments

- **实测口径留个印象**（`local-environment` 第 3.5 节末）：打小发版包约 7 分钟、完整包约 4 分钟、
  8 件资产上传约 4 分钟。上传用**后台任务**，别阻塞等待。
- **完整包必须发**：README 的「获取方式」只指 `firstep-full-<tag>.zip` 一个文件，
  它不在新用户就没有入口；同时工具内「设置 → 完整包下载 → 检查完整包」靠
  `manifest.json` 发现新版本，资产缺失时前端会明确提示「该版本的 Release 上没有完整包资产」。
- **`pack-full` 的 `core.autocrlf=false`**：那处修复是**打包器代码**，不随包分发——
  换机器 / 换 clone 打包前先确认它还在（`tests/test_pack_update.py` 有跨包逐字节守卫）。
  本机未换 clone，本轮开工前跑一次该文件即可确认。
- **本版资产内容 = `HEAD`**（`pack-update` / `pack-full` 都取工作树 / `git archive HEAD`），
  所以打包前工作树必须干净（脚本默认拒绝脏工作树）。
