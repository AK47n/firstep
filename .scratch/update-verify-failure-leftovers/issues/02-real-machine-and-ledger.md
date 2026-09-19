# 02 — 真机复跑与账本：把「失败之后盘上干净」钉在真机证据上

**要做什么：** 用一条可复跑的命令在沙箱「模拟用户机」上把工单 01 的修复跑一遍真机
（本地可控服务器，不需要发版），并把结论写进账本。

**被谁阻塞：** 01。

**状态：** resolved（2026-09-19）

**完成记录。** harness 落在**冻结量具旁边的通用包装器**
`.scratch/verify-gate-drills/run-drill-02-with-workspace-src.py`（工单里原写「本目录的
`run-real-machine.py`」——实际写成通用件，因为内容不符那张单要用同一套：一处实现、
drill 零改动、偏离只记一次）。它做四件事：记账 → 备份沙箱源码与 drill 自己的证据文件 →
用工作树的 `src/contest_generator/` 覆盖沙箱（＝用户机上那一代代码）→ 逐场景跑 drill →
`finally` 一律还原（含 drill 的 `verify-02-degraded.*`，免得覆盖 B2 的历史证据）。

**drill 零改动**：`drill-02-degraded.py` sha256 `30ebf6268f74aaa5…`（只记账，不修改）。

真机结果（`verify-real-machine.{txt,json}` + `verify-real-machine-<场景>.{txt,json}`）：

| 场景 | 耗时 | 结果 |
|---|---|---|
| `verify-size` | 7.4s | drill 判红 0；**「半成品被清」（updates/full/ 下不再有分卷）与「边车被清」都成立** |
| `cut-retry` | 23.7s | drill 判红 0；12 条 checks 全成立（失败态留边车 / 成功后边车已清 / 续传起点单调不减 …） |

隔离与收尾：沙箱源码复原后聚合 sha256 与备份**逐字节相同**、8020 无监听、真身数据目录
mtime 未变。**总判 判红 0 / PASS。**

**一处 harness 自身的记账坑**（已修，记在这里免得下次再踩）：第一版把「工作树那一份」的
摘要按**含 `__pycache__`** 算、而拷贝时用 `ignore_patterns("__pycache__")` 排除了它，
于是「放进沙箱的与工作树一致」与「沙箱复原」两条**自记账判据假红**（产品侧两根判据其实
全绿）。修法：拷贝与摘要用同一套口径，**什么都不排除**。

## 为什么需要单独的包装脚本

`drill-02-degraded.py` 起的是**沙箱 `src/`** 那份代码（它的 docstring 明确写着「产品侧一点没改」），
所以要让修复被真跑到，必须先把工作树里修好的源码放进沙箱（＝用户机上跑着的那一代）。
这一步是 harness 步骤，**不写进 drill 脚本**（它是冻结的量具），放在我们自己的包装脚本里、
在证据里显式记账。

## 验收标准

- [x] 新增 `.scratch/verify-gate-drills/run-drill-02-with-workspace-src.py`（通用件：
      `--evidence-dir` + 可重复的 `--only`）：
      - 备份沙箱 `src/contest_generator/` → 用工作树的同名目录覆盖 → 跑 drill → **无论成败都还原**；
      - 原始输出落 `--evidence-dir` 下的 `verify-real-machine-<场景>.{txt,json}` 与汇总
        `verify-real-machine.{txt,json}`；`drill-02-degraded.py` **一个字不改**（脚本里对它 sha256 记账）
      - 记账偏离：沙箱源码来自工作树（不是线上包），以及沙箱起点版本 1.2.1；
      - 收尾：8020 释放、真身数据目录 mtime 未变、沙箱源码逐字节复原
- [x] 判据：`verify-size` 格 checks 全真（「半成品被清」「边车被清」成立）、drill 判红 0；
      `cut-retry` 格 12 条 checks 全成立（证明没把断点删掉）
- [x] 若某一格判红：如实记进工单（本轮产品侧没有判红；harness 自己的两条自记账判据假红已修，
      原因与修法记在完成记录里）
- [x] 账本：`docs/agents/local-environment.md` 第 1.5 节 B2 那一行按复跑结果更新
      （原「两条不成立 = 失败后残留整卷半成品 + 边车 → 工单 01」改为已修 + 已复跑）
