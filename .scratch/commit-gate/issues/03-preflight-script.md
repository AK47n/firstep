# A3 — `tools/preflight.ps1`：发版前一条命令

**要做什么：** 打 tag 之前跑**一条**命令就知道「这一版能不能发」——三处版本号一致、母版 `.settings` 在库、版本记录页含本版、文档一致性。判据全部复用既有守卫的同一套事实，不新造第二份判据。

**被谁阻塞：** 无——可与 A1/A2 并行。

**状态：** resolved——`tools/preflight.py`（判据）+ `tools/preflight.ps1`（薄壳）+ `tests/test_preflight.py`（10 例）

- [x] `tools/preflight.ps1`（**UTF-8 with BOM**，`tests/test_ps1_encoding.py` 兜底）一条命令跑 4 项：
      ① 三处版本号一致（`__init__.py` / `pyproject.toml` / `VERSIONS.md` 首块）；
      ② 母版 `.settings/` 两件在盘**且在 git**（`git ls-files` 命中，不是只看盘上）+ 编码钉内容在场；
      ③ `python tools/check-download-docs.py --offline`；
      ④ `README.md` 当前版本行与 `__version__` 一致
- [x] 任一红 → 非 0 退出，逐条中文原因 + **怎么修**；全绿 → 一行结论（含当前版本号）
- [x] 判据复用而非复制：版本号解析走 `contest_generator.changelog.load_versions`（与「版本更新记录」页同一解析器）；`preflight.ps1` 是薄壳，**不含任何判据**（用例明令禁止它出现 `VERSIONS.md` / `.prefs` / `pyproject.toml` 字样）
- [x] `docs/agents/releasing.md` 新增「发版前：一条命令自检（必做）」，并把原「下载链路自检」标成联网那一次
- [x] 反向验证 4 项逐条实测（见 Comments）

## Comments

**反向验证（2026-09-16 实测，逐项破坏 → 都红且点名）**：

| 破坏 | 结果 |
|---|---|
| `pyproject.toml` 版本改 9.9.9 | 红「三处版本号一致」，点名 `pyproject.toml = '9.9.9'` |
| `VERSIONS.md` 版本头写成 `(2026-09-16，重发)`（**重演 09-14 真事故**） | 红，点名 VERSIONS.md 首个版本块 + 提示「日期后别写中文备注」 |
| README 当前版本行改回 v1.2.0 | 红，点名 README |
| 编码钉只从索引摘掉（盘上还在） | 红「未被 git 跟踪」+ 提示查 `.gitignore` 母版例外 |

还有一条**不是破坏、而是真缺陷的发现**：`preflight.ps1` 首次落盘时**没有 BOM**
（首字节 `23 20 74` = `# t`），已补成 `EF BB BF` 并用例钉住——这正是仓库那条硬性约定
（PowerShell 5.1 按 GBK 解码无 BOM 脚本会吞行）在真实工作流里的又一次复现。

**入口选择**：`.ps1` 优先用仓库 `.venv\Scripts\python.exe`（`install.bat` 装出来的那个，
带运行依赖），否则退回系统 `python` / `py`；并把 `PYTHONPATH` 钉到仓库 `src`
（防全局 site-packages 里那份指向别处的 editable 安装，见 local-environment.md 2.5）。
