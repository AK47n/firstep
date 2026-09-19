# 04 — 打包 + tag + 上传 v1.2.2 八件资产 + Release 说明

**要做什么：** 线上出现 v1.2.2 的八件套（小发版四件套 + 完整包四件套），
`/releases/latest` 指向它——已装用户点「检查更新」就能拿到这三条修复。

**被谁阻塞：** 03（版本号与自检就位才能打包打 tag）。

**状态：** resolved

- [x] 打小发版包：
      `powershell -File tools\pack-update.ps1 -Tag v1.2.2 -Baseline C:\Users\luoji\Desktop\firstep-pack\firstep-update-v1.2.1.files.txt`
- [x] 打完整包：
      `powershell -File tools\pack-full.ps1 -Tag v1.2.2 -Baseline C:\Users\luoji\Desktop\firstep-pack\firstep-full-v1.2.1.manifest.json`
- [x] **上传前对一次「zip 实算 vs `sha256.txt`」**（上一轮踩过：`Select-Object -First N` 接在
      `powershell -File` 后面会提前掐断上游，zip 生成了、校验和文件还是上一版的）
- [x] 删除清单形态核对：应包含 01 摘掉的 6 件 egg-info 路径 + v1.2.1 小发版多发的那批
      `library/revise-backups/**`（累计口径）；`removed.txt` 非 0 字节（0 字节会被 GitHub 拒收）
- [x] `git tag -a v1.2.2` **并 `git push origin main v1.2.2`**（`gh release create` 是在服务端建
      tag，本地不会自动有——想按 tag 引基线就找不到）
- [x] 写 Release 说明（照 `docs/agents/releasing.md` 模板：**前两行固定**是新用户 / 已装用户指引），
      原稿存 `firstep-pack\release-notes-v1.2.2.md`
- [x] `gh release create` + `gh release upload` 八件资产（ASCII 文件名）
- [x] `gh release view v1.2.2 --repo AK47n/firstep` 确认八件齐全、完整包 zip 在场且体积与
      「约 770 MB」同量级（它是新用户唯一的安装包）
- [x] 冒烟：`tar.exe -tf <full zip> | findstr START-HERE` 输出 `00-START-HERE.txt`
- [x] 打包上传后跑一次**联网版**自检 `python tools\check-download-docs.py`（它拿线上最新 Release
      校验 README 体积口径与 Release 说明前两行——正好确认这一版发对了）
- [x] 把本版两个清单存好当下一版基线：`firstep-update-v1.2.2.files.txt` /
      `firstep-full-v1.2.2.manifest.json`

## Comments

### 落地事实（2026-09-19）

| 项 | 值 |
|---|---|
| 小发版包 | `300,820,891` B / sha256 `866416309ab1bfcf7ac585208e33f4b210ff59f43c7634acb85c4e11a9cff7b9`；**产品文件 2858**（v1.2.1 是 4339）/ 删除清单 **2215** 条 |
| 完整包 | `801,949,226` B / sha256 `3be2f0d6cd00173fd994487daffbe8d969db04387a856cb9a3b4d80454d2538e`；**包内文件 8146**（= 产品文件判据算出的数）/ 资料库基线 12 批次 / 5081 文件 |
| 上传前校验 | `.scratch/release-v1.2.2/precheck-upload.py` → **PASS**（zip 实算 vs `sha256.txt` 两个包逐位相同；四件套齐；完整包里 `00-START-HERE.txt` 在场且不含 egg-info / revise-backups；小发版「zip 条目 == `files.txt`」2858/2858） |
| 线上核对 | `verify-online.py` → **PASS**：八件资产全在且 `state=uploaded`、完整包 zip 764.8 MB（与「约 770 MB」同量级）、`/releases/latest = v1.2.2` |
| 联网自检 | `tools/check-download-docs.py`（不带参数）→ **PASS**，三组：README 获取方式 / 线上最新版资产体积口径（full 802 MB、update 301 MB、clone 291 MiB）/ Release 说明前两行 |
| 发布产物 | `.scratch/release-v1.2.2/verify-04-{sets,precheck,online,docs-online}.txt` |

### 包内容四格（这一版修复是否真的落地，从包本身就能看出来）

`.scratch/release-v1.2.2/measure-sets.py`（判据用 `full_pack.is_product_file` 现算，不手写类别名单）：

| 判据 | 结果 |
|---|---|
| ① 不再发的里面混进**产品文件** | **0** ✓（1482 条的排除原因：`dir-name` 1481 + `installer-glob` 1——后者是 `UartAssist.exe`，安装包通配本来就该排除） |
| ② egg-info 6 条全在删除清单里 | ✓ |
| ③ 库备份 1559 条在删除清单里 | ✓ |
| ④ 新增发的唯一一条正是 `00-START-HERE.txt` | ✓（且它本来就在 v1.2.1 完整包里 = 不是凭空冒出来的路径） |

> **判据①第一版写窄了**（手写「库备份 / egg-info / 安装包」类别名单），把
> `UartAssist.exe` 误报成「不再发的产品文件」。改成**问产品判据本身**
> （`full_pack.is_product_file`）之后归零——量具的判据也要单源，别手抄。

### 打包时踩到的一处流程耦合（值得下次直接照做）

打包器默认**拒绝脏工作树**，而「工单标 `claimed` / `resolved`」本身就是 tracked 变更——
第一次打包直接被拒（`M .scratch/release-v1.2.2/issues/04-…md`）。做法：**打包前把标记还原到
提交态**（`git checkout -- <工单>`），收尾时连同证据一次落 `resolved`。这样「发出去的包」
对应的提交树也自洽（不会把「claimed」这种中间态固化进 tag）。

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
