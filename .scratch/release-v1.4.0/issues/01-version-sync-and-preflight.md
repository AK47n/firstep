# 01 — 三处版本号同步到 v1.4.0 + VERSIONS.md 中文要点 + 发版自检全绿

**要做什么：** 版本号改到 v1.4.0 并提交，`tools/preflight.ps1` 四项全绿——这是打 tag / 打包的前提；
同时把**用户视角**的版本要点写进 `VERSIONS.md`（这一轮用户能看见的是全站观感：字号档位 / 描边层级 / 间距）。

**被谁阻塞：** 无——四批改动已全部 resolved 并落 main（HEAD `aaa2a3ab`，`main` 领先 `origin/main` 75 笔）。

**状态：** resolved

- [x] `src/contest_generator/__init__.py` 的 `__version__` = `1.4.0`（唯一可信来源；注释里那句
      "发版时三处同步"就是这条纪律的出处）
- [x] `pyproject.toml` 的 `project.version` = `1.4.0`
- [x] `VERSIONS.md` 顶部新增 `## v1.4.0 (2026-09-29)` 区块（ASCII 括号 + 严格日期 + 中文要点，
      用户视角：全站观感一段为主，另带更新面板体量数字 / MQ 词表 / 并发写更稳）
- [x] `README.md`「版本与发布」当前版本行 = v1.4.0，并把 v1.3.1 挪成「上一版」
- [x] `tests/test_changelog.py` 的版本列表**追加** v1.4.0（不替换既有项）+ 最新版日期
- [x] `python -m pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` 全绿
- [x] `powershell -File tools\preflight.ps1` 四项全绿（读数落 `preflight-01.txt`）
- [x] 提交信息中文

## Comments

### 落地事实（2026-09-29）

| 项 | 值 |
|---|---|
| 同步手段 | `.scratch/release-v1.4.0/_bump_version.py`（逐字节 `newline=""` 读写，锚点只写单行；命中次数 == 1 才写） |
| 改动面 | 5 个文件：`__init__.py` / `pyproject.toml` / `README.md`（当前 + 上一版两行）/ `VERSIONS.md`（+8 行新区块）/ `tests/test_changelog.py`（docstring + 版本列表 + 日期） |
| 单测读数 | `pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` → **86 passed**（26.85s）— `.scratch/release-v1.4.0/pytest-version-01.txt` |
| preflight 读数 | **四项全绿**，末行 `结论：全绿，可以发版（当前版本 v1.4.0）`，退出码 0 — `preflight-01.txt` |

### 两处按口径走的地方

- **`VERSIONS.md` 的换行**：本工作树这一次是 **LF 检出**（`git diff` 的 warning 也是这么说的），
  脚本读文件现算换行再拼新区块，不写死。
- **`tests/test_changelog.py` 是夹具，不是判据**：它自己的 docstring 写着「下个版本发布时更新此断言
  （**追加而非替换**）」，所以只追加 `v1.4.0` 与最新日期，不动任何既有项；
  「版本列表」那条断言从 8 项变 9 项，`releases[-1]` 仍是 v1.0.0（首版）那条锚。
