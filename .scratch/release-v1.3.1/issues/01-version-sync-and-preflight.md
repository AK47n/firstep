# 01 — 三处版本号同步到 v1.3.1 + 发版自检全绿

**要做什么：** 版本号改到 v1.3.1 并提交，`tools/preflight.ps1` 四项全绿——这是打 tag / 打包的前提。

**被谁阻塞：** 无——`hwcheck-hygiene` 的 `01`–`14` 已全部 resolved 并落 main（最近一笔 `6402839b`）。

**状态：** resolved

- [x] `src/contest_generator/__init__.py` 的 `__version__` = `1.3.1`（唯一可信来源）
- [x] `pyproject.toml` 的 `project.version` = `1.3.1`
- [x] `VERSIONS.md` 顶部新增 `## v1.3.1 (2026-09-27)` 区块（ASCII 括号 + 严格日期）
- [x] `README.md`「版本与发布」当前版本行 = v1.3.1，并把 v1.3.0 挪成「上一版」
- [x] `tests/test_changelog.py` 的版本列表**追加** v1.3.1（不替换既有项）+ 最新版日期
- [x] `python -m pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` 全绿
- [x] `powershell -File tools\preflight.ps1` 四项全绿
- [x] 提交信息中文

## Comments

### 落地事实（2026-09-27）

| 项 | 值 |
|---|---|
| 提交 | `a88167a5`（`chore: 自动更新 CHANGELOG` 紧随其后 `1bea22a1`——**tag 就打在它上面**） |
| 同步手段 | `.scratch/release-v1.3.1/_bump_version.py`（逐字节 `newline=""` 读写，锚点只写单行；单行锚点命中次数 == 1 才写） |
| 改动面 | 5 个文件：`__init__.py` / `pyproject.toml` / `README.md`（当前 + 上一版两行）/ `VERSIONS.md`（+7 行新区块）/ `tests/test_changelog.py`（docstring + 版本列表 + 日期） |
| 单测读数 | `pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` → **86 passed**（63.95s） |
| preflight 读数 | **四项全绿**，末行 `结论：全绿，可以发版（当前版本 v1.3.1）`，退出码 0 — `.scratch/release-v1.3.1/preflight-01.txt` |

### 两处按口径走的地方

- **`VERSIONS.md` 的换行**：这是本目录里唯一一个盘上是 **LF** 的文件（`README.md` / `__init__.py` 等
  盘上是 CRLF）——脚本读文件现算换行再拼新区块，不写死（`local-environment` §0 那条纪律）。
- **`tests/test_changelog.py` 是夹具，不是判据**：它自己的 docstring 写着「下个版本发布时更新此断言
  （**追加而非替换**）」，所以这里只追加 `v1.3.1` 与最新日期，不动任何既有项。
