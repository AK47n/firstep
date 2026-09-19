# 03 — 四件套版本号同步到 v1.2.2 + 发版自检全绿

**要做什么：** 版本号改到 v1.2.2 并提交，`tools/preflight.ps1` 四项全绿——
这是打 tag / 打包的前提（红了就不许打包）。

**被谁阻塞：** 01（含 01 的修复，才算「这一版该发的内容都在」）。

**状态：** resolved

- [x] `src/contest_generator/__init__.py` 的 `__version__` = `1.2.2`（**唯一可信来源**）
- [x] `pyproject.toml` 的 `project.version` = `1.2.2`
- [x] `VERSIONS.md` 顶部新增 `## v1.2.2 (2026-09-19)` 区块（**ASCII 括号 + 严格日期**，
      日期后别写中文备注——2026-09-14 的事故就是这块写坏、解析器静默跳过整版）
- [x] `README.md`「版本与发布」当前版本行改成 `v1.2.2` 并带上这一版的一句话说明
- [x] `python -m pytest tests/test_changelog.py tests/test_readme.py tests/test_preflight.py -q` 全绿
- [x] `powershell -File tools\preflight.ps1` **四项全绿**（三处版本号 / 母版 `.settings/` 编码钉 /
      下载文档一致性 / README 版本行），原始输出留证据
- [x] 提交信息中文（`.githooks/commit-msg` 会拒英文）

## Comments

### 落地事实（2026-09-19）

- preflight 输出原文落 `verify-03-preflight.txt`；结论行：
  `全绿，可以发版（当前版本 v1.2.2）`，三项明细 = 四处版本号 1.2.2 一致 /
  母版 `.settings/` 两件在盘且在库且编码钉在场 / README 与包内文件一致（offline）。
- 版本号一改，**两条既有守卫当场转红**——都是用例把「当时那一版」写成了夹具，
  不是产品问题，本轮顺手解耦（与 `local-environment` 第 2.1 节记的那条同源病）：
  1. `tests/test_changelog.py::test_load_versions_real_file_reflects_released_versions`
     ——期望列表写成 `["v1.2.1", …]` 五块。按它自己的说明「下个版本发布时更新此断言
     （追加而非替换）」追加 `v1.2.2` 并更新最新版日期。
  2. `tests/test_preflight.py::test_wrong_pyproject_version_is_red`
     ——夹具写死 `text.replace('version = "1.2.1"', …)`，版本一动 `replace` 就空转，
     于是「写入 9.9.9」这件事没发生、自检当然全绿，用例反而红。**这正是本地环境第 2.1 节
     记的那类「用例把环境当夹具」**：改成从被测仓库的 pyproject 现读当前版本再替换。

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
