# spec — 提交闸门（提交前先跑得动、发版前一条命令自检）

## 问题陈述

今天（2026-09-16）发 v1.2.1 时暴露了同一件事的两面：

1. **红的改动能推上 main 并挂一整天没人发现。** `local-environment.md` 7.1 记着：母版同步守卫在 main 上挂了整整一天（2026-09-15 → 09-16），根因那句写在括号里——"因为没人跑全套"。今天实测全套只要 **58 秒**（`-n auto`，4475 passed），闸门成本早已降到可接受，却仍然没有闸门。
2. **发版前该查的东西全靠人肉记得。** 今天我是靠记忆一条条跑：三处版本号同步、`check-download-docs.py`、母版 `.settings` 在不在盘上、`test_changelog.py`。少跑任何一条，都可能再演一次「线上包带着坏文件」（09-14 的 `VERSIONS.md` 版本头事故就是这么发生的）。

## 方案

两道本地闸门 + 一道远端闸门，判据全部复用既有测试与既有自检脚本（**不新造判据**）：

- **推之前**：`.githooks/pre-push` 按本次要推的改动**选关联测试子集**跑（秒级～十几秒）；改动面大或发版时用强制全套。
- **发版前**：`tools/preflight.ps1` 一条命令把「版本号三处一致 + `.settings` 在盘且在库 + 版本记录页 + 文档一致性」串起来。
- **远端**：GitHub Actions 在 `windows-latest` 上跑全套 pytest（与用户机同平台，能覆盖路径/编码/CRLF 口径），并在 `ubuntu-latest` 上跑 preflight 的离线部分。

## 用户故事

1. 作为仓库维护者，我推代码时如果改动打破了既有守卫，希望在 push 被拦下并看到失败的用例名，以便当场修而不是等一天后偶然发现。
2. 作为维护者，我希望 push 的等待时间与我改动的范围相称（改文档不该等一分钟，改核心逻辑必须跑全套），以便闸门不会因为"太慢"被我自己用 `--no-verify` 绕过。
3. 作为维护者，我希望改动面无法判断时**倒向更严**（宁可多跑），以便闸门不会被一个没想到的文件类型绕过。
4. 作为发版人，我希望在打 tag 之前跑**一条**命令就知道「这一版能发」，而不是凭记忆跑四条互不相干的检查，以便不再出现"改完忘了跑守卫就打包"的事故。
5. 作为发版人，我希望 preflight 在版本号三处不一致 / `.settings` 不在库 / 版本记录页缺本版时**大声说清是哪一个、怎么修**，以便不必回头翻文档。
6. 作为接手的人，我希望 CI 在每次 push 与 PR 上自动跑全套，以便红不会只存在于我这一台机器上（别人 clone 后没配 `hooksPath` 也仍然有一道网）。
7. 作为接手的人，我希望子集选择逻辑有单元测试（含"未知文件类型 → 全套"的反向用例），以便闸门本身不会静默失效。

## 实现决策

- **闸门落点**：`.githooks/pre-push`（shell 壳，与既有 `commit-msg` / `post-commit` 同族）+ `tools/prepush.py`（选择与执行逻辑，可单测）+ `tools/preflight.ps1`（发版前自检）+ `.github/workflows/ci.yml`。
- **子集映射（`tools/prepush.py`）**：
  - `tests/test_X.py` 改动 → 跑该文件（改名成 `tests/_x.py` 等）→ 跑全套；
  - `src/contest_generator/X.py` 改动 → 跑 `tests/test_X.py`（若存在）；**文件不存在同名测试或命中"核心面"（`errors.py` / `config.py` / `budget.py` / `generator.py` / `webapp.py` / `selection.py` / `library.py` / `patchers.py` 等被广泛 import 的模块）→ 全套**；
  - `library/`（模块库 / 母版库 / 赛题库 / 参考库）改动 → 库不变量族 + 母版同步守卫 + 相关结构测试；
  - `pyproject.toml` / `.githooks/` / `tools/` / `conftest.py` / 未知后缀 → **全套**（倒向更严）；
  - 纯文档（`README.md` / `VERSIONS.md` / `docs/` / `CHANGELOG.md` / `.scratch/`）→ 文档相关守卫（`test_readme.py` / `test_changelog.py` / `test_onboarding_docs.py` / `test_repo_language.py`）。
- **强制全套**：`FIRSTEP_PREPUSH=full` 环境变量或 `--full` 参数；pre-push 在**推 tag**（发版）时自动全套。
- **不阻塞的边界**：prepush 自身出错（git 读不到改动、pytest 没装）→ **打印原因并放行**，绝不因为闸门坏了而卡住维护者（与 `post-commit` 的"任何失败都不阻塞原提交"同口径）；但**测试红了必须拒推**。
- **preflight 断什么**：① 三处版本号一致（`__init__.py` / `pyproject.toml` / `VERSIONS.md` 首块，与既有守卫同判据）；② 母版 `.settings/` 两件在盘且在 git（`test_master_template_config.py` 的判据）；③ `check-download-docs.py --offline`；④ `README.md` 当前版本行与 `__version__` 一致。任何一条红 → 非 0 退出 + 逐条中文原因 + 修法。
- **CI**：windows job 跑 `python -m pytest -n auto`；ubuntu job 跑 `tools/preflight.ps1` 的等价 Python 部分（版本号/`.settings`/offline 文档检查）+ `tests/test_repo_language.py` + `tests/test_ps1_encoding.py`。**不联网、不吃 secret**（仓库既有约定：`tests/fakes.py`）。
- **编码**：新增 `.ps1` 一律 UTF-8 with BOM（`tests/test_ps1_encoding.py` 兜底）。

## 测试决策

- **测什么**：`tools/prepush.py` 的**选择函数**（`select_tests(changed_files) -> Selection`）——纯函数、吃路径列表、吐要跑的文件与"是否全套 + 理由"。覆盖：同名测试命中 / 核心面 → 全套 / 未知后缀 → 全套 / 库改动 / 纯文档 / 空改动 / 多类混合取并集。
- **不测什么**：不测 pytest 子进程真的跑起来（那是集成面，由 CI 与真机使用覆盖）；不测 git 钩子脚本的 shell 语法（由"钩子能跑通一次"的真实使用覆盖）。
- **既有先例**：`tests/test_suite_timeout.py`（配置断言 + "仪器真的会响"的子进程实测）是同类守卫的模板；`tests/test_repo_language.py` 是"机械拦截"的模板。测试需带**反向验证**（改坏映射规则 → 用例变红）。

## 范围外

- 不做"推送后自动回滚"或"main 分支保护"（GitHub 侧设置，非本仓库代码）。
- 不改既有的 `commit-msg` / `post-commit` 行为（自动 CHANGELOG 照旧）。
- 不把 `prepush` 做成"按覆盖率选测试"那类玄学——判据只按文件路径映射，宁可多跑。
- 不动 `.scratch/` 下既有的逐文件跑法探针（`run-11-suite.py` 仍可用）。

## 补充说明

- 这套闸门**不改产品代码**，只加仓库工具与 CI；对用户可见的只有"下一版包里多了这几个文件"。
- 与 `docs/agents/releasing.md` 的关系：preflight 是那篇文档里"三处版本号同步 + 发版前自检"两段的**可执行化**，文档要同步加一句"跑 `tools/preflight.ps1`"。
