# 08 — 两个打包器的换行符口径不一致（跨包逐字节一致性）

**要做什么：** 让「小发版更新包」与「完整包」对**同一个源文件**产出**同一份字节**。

现状（2026-09-13 发 v1.1.0 时实测发现）：两个包对 3474 个共有文件里有 **926 个字节不同、真实内容差异 0 个**——差异**全部是换行符**。根因：

- `tools/pack-update.ps1` 用 `git archive`，**会应用 `.gitattributes` 转换**：本机 `core.autocrlf=true` → 包内文本是 **CRLF**；
- `tools/pack-full.ps1` 走 `full_pack.scan_tree`，**读工作树字节**：本机检出是 **LF**。

**为什么这是真隐患（不是洁癖）**：清单里的 SHA256 来自**实际写入 zip 的字节**。两条安装路线拿到的是不同字节的同一文件 → 走增量时（发布侧 diff 以上一版清单为基线）会把这些文件一律判为「已修改」，**把「只下变化部分」变成「几乎全量重下」**。发行侧自检（`.scratch/full-download/verify_release_assets.py`）只对单个包自洽，抓不到跨包口径差。

**本次是否影响 v1.1.0 用户**：不影响。v1.1.0 是首次完整包发布，没有上一版完整包基线可比；用户无论走哪条路线，拿到的包**各自自洽**（自检 26 项全过、线上哈希复核通过）。隐患在**下次**发布时显现。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

### 验证结果（2026-09-18 真机）

| 项 | 结果 | 证据 |
|---|---|---|
| 真实仓库跨包逐字节 | **共有文件 3480 个，字节差异 = 0**（完整包 8780 个文件 / 小发版 5042 个；完整包 25.9s、小发版 11.6s） | `.scratch/full-download/verify-08-cross-pack-bytes.txt`（脚本 `verify-08-cross-pack-bytes.py`：完整包 + **真 `pack-update.ps1`** 两条路径） |
| `.gitattributes` 物化口径未被碰坏 | `install.bat` → CRLF=83/LF=0；`.githooks/commit-msg` → CRLF=0/LF=34 | 同上 |
| 小发版四件套自洽 | zip 条目 = `.files.txt`；`.sha256.txt` 与实测一致；空删除清单写注释行（非 0 字节） | 同上（6 项判据全 ✓） |
| **新判据在历史包上有效性** | 对 v1.1.0 旧包报出 **926 个**差异（与工单记载一致）、v1.1.1 报 **929 个**，逐条归一化后**全部仅换行符、真实内容差异 0** | `.scratch/full-download/verify-08-historical-cross-pack.txt`（脚本 `probe-08-historical-cross-pack.py`，对拍本机保留的真实发版四件套） |
| 回归 | pytest **4339 passed / 1 skipped**；node **1550 pass / 0 fail** | 全量实跑 |

- [x] 先定口径（二选一，推荐 A）：

      **先把事实量清（本机真机实测，命令与结果都在）**：

      | 事实 | 证据 |
      |---|---|
      | `git archive` 默认会被 `core.autocrlf` 转 | 本机 `core.autocrlf=true`：`README.md` 索引 12987B/LF → 包内 **13110B/123 个 CR**；加 `-c core.autocrlf=false` → 12987B/LF（与工作树一致）。`-c core.eol=lf` **压不住**（仍 13110B/CR） |
      | `.gitattributes` 的 `-text` 压不住 archive 的转换 | 建探针仓库加 `* -text`（仓库级 + `--worktree-attributes` 两种）→ archive 内仍 CRLF |
      | 仓库现状：**3403 个 tracked 文本文件索引 LF / 工作树 CRLF**（`core.autocrlf=true` 检出的），另 3121 个两边都 LF，775 个 `-text` | `git ls-files --eol` 统计 |
      | v1.1.0 的**完整包读工作树 → 这 3403 个是 CRLF**；`git archive` 也是 CRLF → **本来就一致** | 上表两条合起来：`scan_tree` 读盘 + archive 转换后同为 CRLF |

      **推论（决定了做法）**：那 926 个差异是**少数面**，而且完整包（已发布给用户的字节）
      站在 CRLF 一侧。原设想「`full_pack` 改读 `git show HEAD:<path>` 的 blob 字节」
      会把 3403 个文件（含 `library/` 2748 个）**从 CRLF 翻成 LF**——正好撞上本工单要防的
      那件事：下个增量包把它们全判成「已修改」，用户几乎全量重下。
      所以正确方向是**让 archive 侧朝已发布字节收敛**，而不是让完整包改口径。

      **定案做法**：把 `git archive` 的属性转换**钉成确定性**——`-c core.autocrlf=false`：
      不钉时结果取决于调用方机器的 autocrlf（同一 commit 在两台机器上出不同包，这才是根因）；
      钉住后 archive 不做文本转换、`.gitattributes` 里显式写了 `eol` 的仍按属性物化
      （`*.bat` → CRLF、`.githooks/*` → LF），于是**更新包字节 = 工作树字节 = 完整包字节**，
      与 v1.1.0 已发布字节也一致（零额外churn）。
- [x] 落**跨包不变量测试**：`tests/test_pack_update.py` 14 例——同一 commit 跑两个打包器断言共有文件字节逐一相等（本工单缺的守卫）；另含「钉与不钉必须不同」的红证、`core.autocrlf` true/false 两态一致、`.bat` CRLF 与 `.githooks/*` LF 不被碰坏、完整包清单 SHA256 = zip 实际字节
- [x] 发行侧自检脚本（`verify_release_assets.py`）补「两个 zip 的共有文件字节一致」（`cross_pack_byte_diff` + `main()` 落地；顺带把它改成可导入——原先模块级执行，一 import 就崩）
- [x] 重新出一次两包并实测：共有文件差异数 = 0（记录到工单）
- [x] 确认 `full_pack` 在**非 git 目录**（测试夹具 / 用户手动打包）下行为不变，且既有单测不破（`tests/test_full_pack.py` 全绿；小发版侧另有一条「非 git 目录回退读盘」用例）
- [x] 文档补一句：包内字节口径以哪个为准（`docs/agents/releasing.md` 小发版段落）
- [x] 顺手修 `removed.txt` 空清单：无基线时写注释行而不是 0 字节文件（原先靠发版人手改绕过 `gh` 的 `HTTP 400: Bad Content-Length`）

## Comments

- 发现经过：v1.1.0 发版后做跨包抽查，`diagnose_pack_diff.py` 把 926 个差异逐字节归一化后判定「仅换行符差异」。
- 相关证据文件（`.scratch/full-download/`）：`verify_pack_versions.py`（版本号与 diff 概览）、`diagnose_pack_diff.py`（换行符定性）。
- 另一个**顺手要修**的既有缺陷：`removed.txt` 为空时是 **0 字节文件**，`gh release upload` 直接
  `HTTP 400: Bad Content-Length` 拒收（本次现场踩到，靠改写成 `# 注释行` 绕过）。发布侧应在生成时对空清单写注释行，而不是靠发版人手改。
  → **已修（本轮）**：`tools/pack-update.ps1` 无基线时直接写注释行占位。

### 落地清单（2026-09-18）

| 文件 | 改动 |
|---|---|
| `src/contest_generator/pack_update.py` | **新增**：小发版打包核心（`git archive -c core.autocrlf=false` + `--ignore-missing`，清单过长自动分块；非 git 目录回退按清单读盘） |
| `tools/pack-update.ps1` | 去掉裸 `git archive`，改调核心（`PYTHONPATH=src` + `-m contest_generator.pack_update`，与 `pack-full.ps1` 同款姿势）；空 `removed.txt` 写注释行；SHA256 从核心输出取并与实测复核 |
| `src/contest_generator/full_pack.py` | 只补口径注释（**逻辑零改动**：继续读工作树） |
| `tests/test_pack_update.py` | **新增**：14 例跨包守卫 |
| `.scratch/full-download/verify_release_assets.py` | 补 `cross_pack_byte_diff` + `main()` 里两包对拍；改为可导入 |
| `.scratch/full-download/verify-08-cross-pack-bytes.py` | **新增**：真实仓库端到端验证（完整包 + 真 `pack-update.ps1` → 逐字节对拍） |
| `.scratch/full-download/probe-08-historical-cross-pack.py` | **新增**：拿新判据照本机保留的真实发版包（判据有效性红证） |
| `docs/agents/releasing.md` | 小发版段落补「包内字节口径」一句 |
| `.gitignore` | 验证产物目录 `_verify08/`（真实仓库 1 GB 级分卷，脚本可重建） |

**真机演练踩到的第二个坑（已修，`2d3acb8c`）**：`python -B <脚本路径>` 直接跑核心会让
`from .full_pack import _validate_version` 报 `ImportError: attempted relative import with
no known parent package`——必须 `PYTHONPATH=src` + `-m`。第一次端到端验证就是这么失败的。

**注意（改这个特性前必读）**：`git archive` 的 EOL 行为**不受 `.gitattributes` 的 `-text` 控制**
（实测仓库级与 `--worktree-attributes` 两种都压不住），只受 `core.autocrlf` 控制；
所以 `-c core.autocrlf=false` 这个钉子是**唯一**的确定性来源，别当成可有可无的装饰删掉。
