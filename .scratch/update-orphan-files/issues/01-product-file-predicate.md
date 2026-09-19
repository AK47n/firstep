# 01 — 产品文件判据单源：小发版包与完整包对「哪些文件算产品文件」给出同一个答案

**要做什么：** 让「这个仓库根相对路径算不算产品文件」只有一处判据，两个打包器都问它。
用户可观察的结果：小发版更新包不再往用户盘上写完整包永远不会给的文件
（本机库备份 `library/revise-backups/**` 1481 个、`*.exe` 1 个），并且**新版新增的顶层文件
真的发得到**（`00-START-HERE.txt` 这类：v1.1.1 的用户走小发版升级后实测缺它）。

**被谁阻塞：** 无——spec 已拍板（`.scratch/update-orphan-files/spec.md`，本轮澄清选 A）。

**状态：** ready-for-agent

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
