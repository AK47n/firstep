# 02 — 发版前三套门禁（浏览器门禁单独跑）+ 全站读数（probe-00 / probe-04）

**要做什么：** 在**冻结的 revision**上把三套门禁与全站读数各跑一遍，落盘成证据——
验收线：两张尺（页面尺 `SITEWIDE_BACKLOG` / 取值尺 `FROZEN_FONT_SIZES`）**0 / 0**、裸 px 字号 **0**。

**被谁阻塞：** 01（版本号就位后跑的读数才对应要发的那棵树）。

**状态：** resolved

- [x] 前端门禁 `node --test "tests/js/*.test.mjs"` → 落 `readings/js-gate.txt`
- [x] **浏览器门禁单独跑**（不与全量 pytest 并行）`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
      → 落 `readings/browser-gate.txt`
- [x] 全量 `python -m pytest -n auto -q` → 落 `readings/pytest.txt`
- [x] `probe-00-survey.py` → 落 `readings/probe-00.txt`（家底普查）
- [x] `probe-04-scope-calibers.py` → 落 `readings/probe-04.txt`（逐作用域三口径；
      **两张尺 0/0、裸字号 0** 在这里读）
- [x] 落盘读数的时间戳**晚于最后一次改产品面**（三条纪律第 1 条：读数是照片不是结论）
- [x] 读数与三张门禁的摘要写进票尾；提交信息中文

## Comments

### 落地事实（2026-09-29，冻结的 revision = `9504427d` + 它的 CHANGELOG 提交 `3423dca2`）

| 门禁 / 读数 | 结果 | 文件 |
|---|---|---|
| 前端门禁 | **1840 passed / 0 fail**（5.09s） | `readings/js-gate.txt` |
| 浏览器门禁（**单独跑**） | **61 passed / 0 fail**（170.63s） | `readings/browser-gate.txt` |
| 全量 pytest | **5656 passed + 11 skipped / 0 failed**（99.10s） | `readings/pytest.txt` |
| `probe-00` 家底普查 | 裸 px 字号 **0 处 / 取值 0 种**；`--fs-*` 引用 **428 处** | `readings/probe-00.txt` |
| `probe-04` 逐作用域三口径 | 十四个作用域 **bareFont 0 / bareSpace 0**；页面尺 **0 条**（已完工 14）；整圈完整框 **115** | `readings/probe-04.txt` |

- **顺序照纪律走**：前端门禁 → 浏览器门禁 → 全量 pytest，**浏览器门禁不与 pytest 并行**
  （`ui-density-sitewide` 轮固化的第 2 条）。
- **两张尺 0/0 + 裸字号 0** 三条都在 `probe-04` 里读到（页面尺 `SITEWIDE_BACKLOG = 0 条`、
  取值尺在 `probe-00` 第 4 节读成"取值 0 种"），与 08 收尾单的验收线一致。
- **本机偶发本轮没出现**：浏览器门禁 61/61 一次过（`launcher-reload` 那支的老偶发没有触发）。
- ⚠ **一处操作失误，如实记**：跑完浏览器门禁之后、全量 pytest **之前**，我为了核 BOM 单跑了一次
  `pytest tests/test_ps1_encoding.py`（1 秒）——那一次**与浏览器门禁并行**了，违反了"浏览器门禁不与
  任何 pytest 并行"的纪律。本轮浏览器门禁仍 61/61 全绿、全量 pytest 也全绿，所以没有造成假红；
  **但这条不该做**（下一次要核什么东西，等门禁跑完再核）。
- 读数落盘时间戳（13:19–13:25）**晚于**最后一次改产品面的提交（`9504427d`，13:16）。
