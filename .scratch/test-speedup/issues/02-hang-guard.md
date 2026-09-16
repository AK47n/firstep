# 02 — 口径守卫 + 卡死现场取证（probe-hang）

**要做什么：** 「超时口径已配置且值在合理区间」由用例钉住（谁删谁红）；同时把「整支 pytest
间歇性卡死」这件事用可复跑的探针钉出结论——复现到就留下倒栈证据，复现不到就如实记
「n 轮未复现」，不编根因。

**被谁阻塞：** 01（阈值定下来才能钉区间）。

**状态：** resolved

- [x] `tests/test_suite_timeout.py`：断言 `timeout` 在场且值 ∈ [60, 600]、
      `pytest-timeout` / `pytest-xdist` 在 dev 依赖里、**仪器真的会响**（子进程 pytest +
      会睡的临时用例，外层再套 `subprocess.run(timeout=90)`——守卫自己也不能卡住）
- [x] 反向验证：删配置 → 红；恢复 → 绿（证据见工单 01）
- [x] `.scratch/test-speedup/probe-hang.py` 跑 **9 轮**整支 pytest（3 轮 + 6 轮），
      每轮输出落 `run-<i>.txt`（保留最后 6 轮）
- [x] **结论：9 轮全部没卡**，每轮 155.2～172.1s，`rc=0`，`faulthandler_timeout=30` 从未触发
      → 记「未定性」，**不写「已解决」**
- [x] 结论写回 `docs/agents/local-environment.md` 2.5c（含「别把这条写成已解决」）

## Comments

- 本轮没有把「卡死」钉到任何一条具体用例上。2.5 节那次（工单 12）曾把它钉到
  `test_download_status_surface.py::test_message_cleared_when_backoff_window_closes` 的 spy 上，
  但那时是**逐文件**跑也卡；本轮该文件单跑 7.3s、整支 9 轮全绿，**无法复现**。
  按纪律：不拿旧结论当本轮结论，也不编新根因。
- 副产品：整支跑法的耗时基线有了（155～172s，9 个样本），这是后面判断「是不是变慢了」的尺子。
- 顺带发现 main 上有一条红（mspm0 `.settings/` 误删）——本轮修掉，见工单 03 与
  `docs/agents/local-environment.md` 第 7 节。
