# 08 — 两个打包器的换行符口径不一致（跨包逐字节一致性）

**要做什么：** 让「小发版更新包」与「完整包」对**同一个源文件**产出**同一份字节**。

现状（2026-09-13 发 v1.1.0 时实测发现）：两个包对 3474 个共有文件里有 **926 个字节不同、真实内容差异 0 个**——差异**全部是换行符**。根因：

- `tools/pack-update.ps1` 用 `git archive`，**会应用 `.gitattributes` 转换**：本机 `core.autocrlf=true` → 包内文本是 **CRLF**；
- `tools/pack-full.ps1` 走 `full_pack.scan_tree`，**读工作树字节**：本机检出是 **LF**。

**为什么这是真隐患（不是洁癖）**：清单里的 SHA256 来自**实际写入 zip 的字节**。两条安装路线拿到的是不同字节的同一文件 → 走增量时（发布侧 diff 以上一版清单为基线）会把这些文件一律判为「已修改」，**把「只下变化部分」变成「几乎全量重下」**。发行侧自检（`.scratch/full-download/verify_release_assets.py`）只对单个包自洽，抓不到跨包口径差。

**本次是否影响 v1.1.0 用户**：不影响。v1.1.0 是首次完整包发布，没有上一版完整包基线可比；用户无论走哪条路线，拿到的包**各自自洽**（自检 26 项全过、线上哈希复核通过）。隐患在**下次**发布时显现。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 先定口径（二选一，推荐 A）：
      - **A：统一成 git 口径（`git archive` 的字节）**。工具树全部 tracked，`full_pack` 对 tracked 文件改用 `git show HEAD:<path>` / `git cat-file` 取字节，资料库（未 tracked）仍读工作树。改动集中在 `full_pack.scan_tree`，不动全局换行策略、不动任何既有文件字节。
      - **B：统一成工作树口径**。加 `.gitattributes` 的 `* -text`（或 `* text eol=lf`）+ `git add --renormalize .` 重写索引，让两处都读同一份字节。**影响面大**（会改仓库所有文本文件的索引字节），需单独评估与充分回归。
- [ ] 落一条**跨包不变量测试**：同一 commit 下分别跑两个打包核心，断言共有文件路径的字节逐一相等（这是本次缺的守卫）
- [ ] 发行侧自检脚本（`verify_release_assets.py`）补一条：两个 zip 的共有文件字节一致
- [ ] 重新出一次两包并实测：共有文件差异数 = 0（记录到工单）
- [ ] 若选 A：确认 `full_pack` 在**非 git 目录**（测试夹具 / 用户手动打包）下回退读工作树，且既有单测不破
- [ ] 文档补一句：包内字节口径以哪个为准（`docs/agents/releasing.md` 的打包段落）

## Comments

- 发现经过：v1.1.0 发版后做跨包抽查，`diagnose_pack_diff.py` 把 926 个差异逐字节归一化后判定「仅换行符差异」。
- 相关证据文件（`.scratch/full-download/`）：`verify_pack_versions.py`（版本号与 diff 概览）、`diagnose_pack_diff.py`（换行符定性）。
- 另一个**顺手要修**的既有缺陷：`removed.txt` 为空时是 **0 字节文件**，`gh release upload` 直接 `HTTP 400: Bad Content-Length` 拒收（本次现场踩到，靠改写成 `# 注释行` 绕过）。发布侧应在生成时对空清单写注释行，而不是靠发版人手改。
