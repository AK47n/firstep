# 02 — 真机复跑与账本：把「失败之后盘上干净」钉在真机证据上

**要做什么：** 用一条可复跑的命令在沙箱「模拟用户机」上把工单 01 的修复跑一遍真机
（本地可控服务器，不需要发版），并把结论写进账本。

**被谁阻塞：** 01。

**状态：** ready-for-agent

## 为什么需要单独的包装脚本

`drill-02-degraded.py` 起的是**沙箱 `src/`** 那份代码（它的 docstring 明确写着「产品侧一点没改」），
所以要让修复被真跑到，必须先把工作树里修好的源码放进沙箱（＝用户机上跑着的那一代）。
这一步是 harness 步骤，**不写进 drill 脚本**（它是冻结的量具），放在我们自己的包装脚本里、
在证据里显式记账。

## 验收标准

- [ ] 新增 `.scratch/update-verify-failure-leftovers/run-real-machine.py`：
      - 备份沙箱 `src/contest_generator/` → 用工作树的同名目录覆盖 → 跑 drill → **无论成败都还原**；
      - 跑 `--only verify-size` 与 `--only cut-retry` 两格，原始输出落
        `.scratch/update-verify-failure-leftovers/verify-real-machine.{txt,json}`（drill 自己写的那两份
        证据同时保留）；**drill-02-degraded.py 一个字不改**（脚本里对它的 sha256 记账）
      - 记账偏离：沙箱源码来自工作树（不是线上包），以及沙箱起点版本；
      - 收尾：8020 释放、无残留 python 进程、真身数据目录 mtime 未变
- [ ] 判据：`verify-size` 格 `checks` 全真（特别是「半成品被清」「边车被清」）、判红 0；
      `cut-retry` 格「失败态留边车 / 成功后边车已清」成立（证明没把断点删掉）
- [ ] 若某一格判红：如实记进工单，不许把判据改成「现在这样也算对」
- [ ] 账本：`docs/agents/local-environment.md` 第 1.5 节 B2 那一行按复跑结果更新
      （原「两条不成立 = 失败后残留整卷半成品 + 边车 → 工单 01」改为已修 + 已复跑）
