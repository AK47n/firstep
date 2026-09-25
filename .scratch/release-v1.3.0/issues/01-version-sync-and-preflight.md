# 01 — 三处版本号同步到 v1.3.0 + 发版自检全绿

**要做什么：** 版本号改到 v1.3.0 并提交，`tools/preflight.ps1` 四项全绿——这是打 tag / 打包的前提。

**被谁阻塞：** 无（`driver-defect-fixes` 三张单已 resolved 并提交）。

**状态：** resolved

- [x] `src/contest_generator/__init__.py` 的 `__version__` = `1.3.0`（唯一可信来源）
- [x] `pyproject.toml` 的 `project.version` = `1.3.0`
- [x] `VERSIONS.md` 顶部新增 `## v1.3.0 (2026-09-25)` 区块（ASCII 括号 + 严格日期）
- [x] `README.md`「版本与发布」当前版本行 = v1.3.0，并把 v1.2.2 挪成「上一版」
- [x] `tests/test_changelog.py` 的版本列表**追加** v1.3.0（不替换既有项）+ 最新版日期
- [x] `python -m pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` 全绿
- [x] `powershell -File tools\preflight.ps1` 四项全绿
- [x] 提交信息中文

## Comments

### 落地事实（2026-09-25）

- 提交 `b55dac14`（`chore: 自动更新 CHANGELOG` 紧随其后 `e47d9a8c`）。
- preflight 输出：`结论：全绿，可以发版（当前版本 v1.3.0）`——三处版本号 1.3.0 一致 /
  母版 `.settings/` 两件在盘且在库且编码钉在场 / README 与包内文件一致（offline）。
- **顺手修掉一处既有缺陷**（不修就推不动）：`tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest`
  的 docstring 与断言停在「--full 两支都跑」，而 `tools/prepush.py` 自工单 `ui-dom-contract-gate/03`
  起已有**第三支** `run_browser_tests`；`--full` 会置 `selection.browser=True`，那条用例没 stub 它
  ⇒ 真跑整支真浏览器套件。本机实测 **42 条 / 183.7 秒** > `pyproject.toml` 的全局
  `timeout = 180`（thread，超时**中止整场**）⇒ 必红（`-n auto` 下表现为 worker 崩，
  与 `local-environment` 记的那条"并行争用偶发"**不是同一件事**，本轮量准了根因）。
  改法：第三支也 stub 并断言顺序 `js → browser → pytest`；「浏览器门禁真被执行 / dry-run 不执行」
  的判据仍在 `tests/test_prepush.py`。修前单跑超时（180s）→ 修后 **29 passed / 0.43s**。
- VERSIONS.md 的写法照 `docs/agents/releasing.md`：组内 `- <标签>：<一句话>`，
  可选的 `- 主题：…` 放第一条；**写用户听得懂的话**（不写工单编号与内部重构）。
