# 01 — 全库默认超时：卡住当场变红（含仪器反向验证）

**要做什么：** 一条 `python -m pytest` 跑全套时，任何用例卡住超过阈值就当场判红并打印所有
线程的栈——「卡住」不再表现为无限等待。开发者不必再因为怕卡死而回避整支跑法。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `pytest-timeout` 进 `pyproject.toml` 的 `dev` 可选依赖（与 `pytest` / `httpx` 同处；
      一并加了 `pytest-xdist`，工单 03 用）
- [x] `[tool.pytest.ini_options]` 配 `timeout = 180` + `timeout_method = "thread"`，就近注释写清依据
- [x] 阈值依据实测：`python -m pytest -q -n auto --durations=20` → 最慢正当用例
      `tests/test_full_pack.py::test_repo_start_here_ships_in_package` **47.29s**（并行争用下，
      串行时整个文件才 16.8s）→ 180s ≈ 3.8 倍余量
- [x] **反向验证（仪器会响）**：造 `time.sleep(120)` 的用例、`-o timeout=3` 跑 →
      **6.5s 判红 + 倒栈 + 退出码 1**；另用「一个会睡 + 一个该过」的文件实测到
      **thread 方法触发时中止整场**（第二个用例没跑），这条语义已写进 pyproject 注释与 2.5c
- [x] **反向验证（守卫会红）**：拿掉 `timeout`/`timeout_method` 两行 → `test_suite_timeout.py`
      红，报「pyproject.toml 缺 [tool.pytest.ini_options] timeout —— 整支 pytest 卡死时又回到无限等」；
      恢复后三例全绿
- [x] 全套跑一次确认零回归：**4472 passed / 1 skipped / 0 failed**（9 轮整支 pytest 都是这个结果）

## Comments

- 阈值为什么不压小：`thread` 方法触发时**中止整场**而不是只废掉一格，假红的代价是一整轮白跑；
  而 180s 已经足以把「卡十分钟以上」这种症状变成两分钟的确定失败。
- Windows 上 `--timeout-method=signal` 直接 `INTERNALERROR`（实测），所以只有 thread 一条路。
- 跑测试仍必须用 `python -m pytest`（裸 `pytest` 会走全局 site-packages 那份沙箱 editable 安装，
  见 `docs/agents/local-environment.md` 2.5）——本轮口径没改这一条。
