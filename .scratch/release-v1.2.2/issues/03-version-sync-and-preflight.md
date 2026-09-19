# 03 — 四件套版本号同步到 v1.2.2 + 发版自检全绿

**要做什么：** 版本号改到 v1.2.2 并提交，`tools/preflight.ps1` 四项全绿——
这是打 tag / 打包的前提（红了就不许打包）。

**被谁阻塞：** 01（含 01 的修复，才算「这一版该发的内容都在」）。

**状态：** ready-for-agent

- [ ] `src/contest_generator/__init__.py` 的 `__version__` = `1.2.2`（**唯一可信来源**）
- [ ] `pyproject.toml` 的 `project.version` = `1.2.2`
- [ ] `VERSIONS.md` 顶部新增 `## v1.2.2 (2026-09-19)` 区块（**ASCII 括号 + 严格日期**，
      日期后别写中文备注——2026-09-14 的事故就是这块写坏、解析器静默跳过整版）
- [ ] `README.md`「版本与发布」当前版本行改成 `v1.2.2` 并带上这一版的一句话说明
- [ ] `python -m pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` 全绿
- [ ] `powershell -File tools\preflight.ps1` **四项全绿**（三处版本号 / 母版 `.settings/` 编码钉 /
      下载文档一致性 / README 版本行），原始输出留证据
- [ ] 提交信息中文（`.githooks/commit-msg` 会拒英文）

## Comments

- **`VERSIONS.md` 的写法**：照 `docs/agents/releasing.md` 的格式约定——组内条目
  `- <标签>：<一句话>`，标签 ∈ 新增 / 改进 / 修复 / 性能，可选的
  `- 主题：…` 放组内第一条，**写用户听得懂的话**（不写工单编号、不写内部重构与性能黑话）。
- **为什么先跑 `tests/test_changelog.py`**：2026-09-14 那次事故正是「改完 `VERSIONS.md`
  没跑守卫就打包」——版本头写坏 → 解析器静默跳过整块 → 「版本更新记录」页缺本版 →
  两个包都传上线了只能重打重传。现在另有一条绑 `__version__` 的守卫
  （`test_real_versions_file_header_matches_tool_version`），版本块漏写/写坏当场红。
- **本机已配 `core.hooksPath .githooks`**（`local-environment` 第 2.5d 节），所以提交/推送
  会自动过闸门；`python tools/prepush.py --dry-run` 可以先看这次会跑什么。
