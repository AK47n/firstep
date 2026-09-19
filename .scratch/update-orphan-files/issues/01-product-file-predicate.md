# 01 — 产品文件判据单源：小发版包与完整包对「哪些文件算产品文件」给出同一个答案

**要做什么：** 让「这个仓库根相对路径算不算产品文件」只有一处判据，两个打包器都问它。
用户可观察的结果：小发版更新包不再往用户盘上写完整包永远不会给的文件
（本机库备份 `library/revise-backups/**` 1481 个、`*.exe` 1 个），并且**新版新增的顶层文件
真的发得到**（`00-START-HERE.txt` 这类：v1.1.1 的用户走小发版升级后实测缺它）。

**被谁阻塞：** 无——spec 已拍板（`.scratch/update-orphan-files/spec.md`，本轮澄清选 A）。

**状态：** resolved（2026-09-19）

**完成记录。** 判据收进 `src/contest_generator/full_pack.py` 的
`product_file_reason` / `is_product_file`（判据本体从 `_exclude_reason` 收口而来，
`scan_tree` 与 `excluded_paths` 都改成问它——三家共用一份规则）；小发版打包核心
`src/contest_generator/pack_update.py` 新增 `select_product_files`，
**筛选挪进 Python 核心**（zip 与 `.files.txt` 仍由核心一起写出，一一对应不变）；
`tools/pack-update.ps1` 只剩「`git ls-files` 全量当候选 → 交给核心」两件事，
手抄的 `$TopLevels` / `$TopPattern` 整段删掉。`pack-update.ps1` 的删除清单也顺手改成
拿**核心写出的 `.files.txt`**做差（原先拿候选清单，会一律算成空）。

**真仓库实测**（`git ls-files` 6897 条候选）：

| 判据 | 实测 |
|---|---|
| 产品文件 | **2858 条**（筛掉 4039：`.scratch` 2534 / `library/revise-backups` 1481 / 其它） |
| `00-START-HERE.txt` | **在**（原先小发版包漏发它） |
| `library/revise-backups/**` | **0 条命中**（原先 1481 条随包发出） |
| `*.exe` / `.scratch/**` | 0 / 0 |

交叉核对：线上 v1.2.1 的 `firstep-update-v1.2.1.files.txt` 是 4339 条，减去它里面那 1481 条
`revise-backups` 正好 **2858** —— 与本次筛出来的产品文件数逐条同量。

**判据强度探针 4/4 转红**（`.scratch/update-orphan-files/verify-01-guard-strength.{txt,json}`）：

| 注入 | 结果 |
|---|---|
| ① 谓词放宽（不再按目录名排除） | 转红 ✓ |
| ② 筛选被摘掉（候选原样进包） | 转红 ✓ |
| ③ 判据被抄回 `scan_tree`（行为等价、单源被破坏） | 转红 ✓ |
| ④ 打包脚本里手抄顶层白名单 | 转红 ✓ |

三处复原逐字节相同。**顺带修掉两个探针工程坑**（都写进探针注释）：
① 探针被强杀时 `finally` 跑不到、源文件停在注入态 → 三支探针都加了**前置干净性检查**；
② 读侧原先用文本模式（CRLF↔LF 往返会把混行文件整份归一 → 「复原复核」假红）→ 改成
**逐字节保真读 + 按目标文件换行风格适配锚点**。另：`tools/pack-update.ps1` 少 BOM 会被
`tests/test_ps1_encoding.py` 当场抓住（编辑工具会吞掉 BOM，改完 .ps1 必须复核 BOM）。

聚焦测试：`tests/test_full_pack.py` + `tests/test_pack_update.py` **49 passed**
（新增真值表、`scan_tree` 问单源的结构守卫、扫描结果与谓词一致的行为判据、
小发版不许多发 / 必须带上新顶层文件的判据、打包脚本不许手抄白名单的静态守卫）。

## 背景（这份单子的根因是**更正后**的，别按原措辞读）

原单 `01-orphans-after-multi-version-update.md` 写的「删除清单只覆盖上一版 → 落后两版留下
1483 个孤儿」与本轮重新量出来的证据不符，三条更正见 spec「补充说明 · 更正」：

1. 那 1483（重算 1482）里 **1481 个是这次小发版更新包自己写进去的**
   （`firstep-update-v1.2.1.zip` 条目表里有它们；沙箱里这 1481 个文件的 mtime 全是解包那一刻，
   `last-update.json` 记 `20260919-113411`）；
2. 「落后两版」这个场景 B1 没演到（那次 `-Baseline` 就是用户起点那一版的 `files.txt`，
   算出的 727 条删除项正好等于两清单差集）；
3. 真正「旧版发过、之后不再发、小发版路径清不掉」的是 205 个**未被 git 跟踪**的
   `sources/contest/**` 路径——那一条归本目录的工单 02（累计删除清单）。

量具：`.scratch/update-orphan-files/measure-sets.py`（只读、可复跑）。

## 验收标准

- [ ] `src/contest_generator/full_pack.py` 暴露一个**公开的纯谓词**
      「仓库根相对路径算不算产品文件」：判据本体由既有的排除原因收口而来，
      `scan_tree` 与谓词**共用同一份**（不许各写一份规则）；顶层白名单四类排除规则一个不落
- [ ] 谓词真值表（单测，夹具临时目录）：`00-START-HERE.txt` **算**、
      `library/revise-backups/<ts>/x.c` **不算**、`library/fix-backups/...` **不算**、
      `sources/x/UartAssist.exe` **不算**、`*.pyc` / `*.log` / `__pycache__/` **不算**、
      白名单外的顶层目录（如 `.scratch/`）**不算**
- [ ] `tools/pack-update.ps1` 里**不再出现手抄的顶层数组**（静态守卫断言：
      那份 `$TopLevels` 数组没了，且不再用它做 `-match` 过滤）
- [ ] 筛选发生在 `src/contest_generator/pack_update.py`（谓词单一出处）：给它一份**候选清单**
      （含若干被排除路径），它写出的 zip 条目与 `.files.txt` 都**不含**被排除项，
      含 `00-START-HERE.txt`（单测，夹具树）
- [ ] 「zip 条目 == 清单」这条既有自检仍然成立（清单由核心写出，不是 PowerShell 写）
- [ ] 既有守卫全绿：`tests/test_pack_update.py` 的跨包逐字节一致性、
      `tests/test_full_pack.py` 的路径预算与清单形态、`tests/test_ps1_encoding.py`（改过的 .ps1
      仍 UTF-8 with BOM）
- [ ] 反向注入探针（`.scratch/update-orphan-files/probe-guard-strength.py`）：
      把谓词放宽（不排除备份目录）、把筛选去掉（退回 PowerShell 白名单）两处注入
      **必须让对应用例转红**；跑完复原并复核 sha256
- [ ] 真仓库上手工核对一次：修复后算出的候选清单**不含** `library/revise-backups/**` 与 `*.exe`，
      **含** `00-START-HERE.txt`（把两组计数记进工单）
