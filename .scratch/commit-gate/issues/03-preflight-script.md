# A3 — `tools/preflight.ps1`：发版前一条命令

**要做什么：** 打 tag 之前跑**一条**命令就知道「这一版能不能发」——三处版本号一致、母版 `.settings` 在库、版本记录页含本版、文档一致性。判据全部复用既有守卫的同一套事实，不新造第二份判据。

**被谁阻塞：** 无——可与 A1/A2 并行。

**状态：** pending

- [ ] `tools/preflight.ps1`（**UTF-8 with BOM**，`tests/test_ps1_encoding.py` 兜底）一条命令跑 4 项：
      ① 三处版本号一致（`src/contest_generator/__init__.py` / `pyproject.toml` / `VERSIONS.md` 首块）；
      ② 母版 `.settings/` 两件在盘且在 git（`git ls-files` 命中，不是只看盘上）；
      ③ `python tools/check-download-docs.py --offline`；
      ④ `README.md` 当前版本行与 `__version__` 一致
- [ ] 任一红 → 非 0 退出，逐条中文原因 + **怎么修**；全绿 → 一行结论（含当前版本号）
- [ ] 复用而非复制判据：版本号解析与 `.settings` 判据走既有模块/测试里的同一函数（能 import 就 import，不能 import 才在脚本里取同一事实）
- [ ] `docs/agents/releasing.md` 的「发版前」两节加一句「跑 `tools/preflight.ps1`」
- [ ] 反向验证：临时把三处版本号之一改坏 → 脚本红且点名是哪一处；还原 → 绿
