# 01 — 三处版本号同步到 v1.3.1 + 发版自检全绿

**要做什么：** 版本号改到 v1.3.1 并提交，`tools/preflight.ps1` 四项全绿——这是打 tag / 打包的前提。

**被谁阻塞：** 无——`hwcheck-hygiene` 的 `01`–`14` 已全部 resolved 并落 main（最近一笔 `6402839b`）。

**状态：** claimed

- [ ] `src/contest_generator/__init__.py` 的 `__version__` = `1.3.1`（唯一可信来源）
- [ ] `pyproject.toml` 的 `project.version` = `1.3.1`
- [ ] `VERSIONS.md` 顶部新增 `## v1.3.1 (2026-09-27)` 区块（ASCII 括号 + 严格日期；
      照模板写用户听得懂的话，标签 ∈ 新增 / 改进 / 修复 / 性能，第一条可带「主题：」）
- [ ] `README.md`「版本与发布」当前版本行 = v1.3.1，并把 v1.3.0 挪成「上一版」
- [ ] `tests/test_changelog.py` 的版本列表**追加** v1.3.1（不替换既有项）+ 最新版日期
- [ ] `python -m pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` 全绿
- [ ] `powershell -File tools\preflight.ps1` 四项全绿
- [ ] 提交信息中文
