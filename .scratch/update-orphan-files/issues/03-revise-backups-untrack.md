# 03 — `library/revise-backups/**` 移出 git 索引（与 `fix-backups` 对齐）

**要做什么：** 让本机的库修订备份不再进仓库、也不再进任何发布清单。用户可观察的结果：
小发版更新包不再夹带开发者机器上的库备份（实测 1481 个文件）；`git clone` / `git status`
不再被这批与本产品无关的东西污染。

**被谁阻塞：** 无（可与 01 并行；但同批提交时放在 01 之后更清楚）。

**状态：** resolved（2026-09-19）

**完成记录。** `.gitignore` 增加 `library/revise-backups/`（注释与既有
`library/fix-backups/` 那行同族，并写明「判据单源见 full_pack.product_file_reason」）+
`git rm -r --cached library/revise-backups`（1481 条移出索引）。

| 判据 | 实测 |
|---|---|
| 盘上文件 | **3668 个，逐字节未动**（聚合金标 sha256 `da89ea4ee66c9845…` 前后相同） |
| 索引里 | 1481 → **0** |
| 提交后 `git status --porcelain` | 干净（被忽略的文件不以 untracked 形态冒出） |
| 运行时不变量 | `revision.py` / `deepen.py` / `task_progress.py` 只在**运行时**读写这些目录（备份与回滚入口），与 git 索引无关 |
| 聚焦测试 | `test_revision` / `test_library_invariants` / `test_wordlist` / `test_lckfb_attribution` **70 passed** |

**与工单 02 的闭环**：这次 `git rm --cached` 只解决「以后不再入库」；**老用户盘上已经收到**的
那 1481 个备份文件由工单 02 的累计删除清单清掉（线上 v1.1.1 的小发版清单里就有它们——
`firstep-update-v1.1.1.files.txt` 命中 1559 条），两件事合起来才算闭环。

## 背景

`library/fix-backups/` 早在 `.gitignore` 里（注释写着「fix-errors 运行产物：真机修复的备份目录
（输出目录外，可回滚；不入库）」），而**同族的 `library/revise-backups/` 没被忽略**——
2026-09-12 库自动提交（`e2e2b04e`）把 1481 个备份文件带进了索引，随后它们就随小发版包
发到了每个用户盘上（本目录工单 01 修的就是「小发版多发」这一半；本单修的是仓库这一半）。

## 验收标准

- [ ] `.gitignore` 增加 `library/revise-backups/`，注释与既有 `library/fix-backups/` 那行同款
      （说明「本机库备份，可回滚，不入库」）
- [ ] `git rm -r --cached library/revise-backups` 执行并提交；**盘上文件一个不删**
      （提交前记下文件数、提交后复核盘上文件数与 sha256 抽样未变）
- [ ] `git status --porcelain` 之后是干净的（被忽略的文件不该以 untracked 形态冒出来）
- [ ] 运行时行为零变化：`src/contest_generator/revision.py` 的备份读写只碰盘上目录，
      与 git 索引无关；`python -m pytest tests/test_revision.py -q` 全绿
- [ ] 库里其它扫描类测试全绿（`tests/test_library_invariants.py` / `tests/test_wordlist.py` /
      `tests/test_reference_library.py` 的库根扫描不把备份目录当内容）
- [ ] 工单里记一笔：这次 `git rm --cached` 之后，**老用户盘上已经收到的**那 1481 个备份文件
      由工单 02 的累计删除清单清掉（两件事合起来才算闭环）
