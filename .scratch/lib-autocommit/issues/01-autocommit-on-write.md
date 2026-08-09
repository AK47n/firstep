# 01 — 写库动作自动 git 提交（录入即进历史）

**What to build:** 库 CRUD 落盘后自动 `git add + commit`，录入即进 git 历史。背景：模块库已迁入软件仓库 `library/`（ADR 0008），config.json 指仓库内路径——写库动作自动落盘到 `library/` 工作区，但 git 提交仍靠人工，漏提交 = 变更只在工作区。本工单让写库动作落盘成功后自动提交该次变更。

**Blocked by:** 无

**Status:** resolved

## 需求

1. **写库即提交**：以下动作成功落盘后自动 git 提交（变更仅限库根子树，不碰 src/ 等仓库其他文件）：
   - 模块：`library.add_module` / `update_module_description` / `add_platform_files` / `remove_platform_files` / `delete_module`（`save_manifest` / `update_platform_identity` 是内部辅助，被上述函数调用，不单独触发）
   - 母版：`master_store` 入库事务完成后
   - 赛题：`topic_library` 拆条入库后
   - 参考文件：`archive` 归档确认后（references/）
2. **只当库根在 git 工作树内时生效**：`git rev-parse --show-toplevel` 失败（库在仓库外，如发布后用户自配路径）→ 静默跳过，绝不炸、绝不打印噪音；库根在仓库内 → `git add` 限定库根子树（相对工作树根路径），不能 `git add -A` 全仓。
3. **空提交跳过**：无暂存变更（`git diff --cached --quiet`）→ 不产生空 commit。
4. **可关**：config.json 加开关（默认开），关掉后行为回到现状。
5. **提交消息**：简短中文，带动作标识，如 `lib: add module <slug>` / `lib: distill masters` / `lib: archive reference <name>`——由调用点传入动作描述。
6. **日志**：自动提交成功/跳过/失败（git 命令异常非零，但库在 git 内）打日志不抛出（写库本身已成功，git 失败不能回滚写库——宁可留下工作区变更下次人工提交，也不让录入动作失败）。

## 文件边界

- 新增 `src/contest_generator/autocommit.py`：探测（库根 → git 工作树根）+ 提交（add 限定子树 + commit + 空跳过），纯函数无状态；git 命令走 subprocess，失败静默/记日志
- `config.py`：Config 模型加布尔开关（默认 True），config.json 读写同步
- 调用点：`library.py`（5 个写函数收尾一行）、`master_store.py`、`topic_library.py`、`archive.py`（各入库/归档事务收尾一行）
- 测试：新增 `tests/test_autocommit.py`——tmp 下 `git init` 建伪库 → 调 `add_module` → 断言 `git log` 出现提交且提交只含库根路径；库根指向无 git 目录 → 动作不炸且无提交；空变更不产生提交；开关关闭不提交；提交消息断言
- 结构测试防漏：写库函数清单与调用点一致性（参考 categories.py 结构测试先例，防以后新增写函数漏挂）

## 验收

- [x] 新会话执行（本工单 = 实施提示词，含边界与验收）
- [x] 全量测试绿 + mypy 干净（856 绿 + mypy 0 问题；基线 843 + 本批 13 新测试）
- [x] tmp 伪 git 库实测：`add_module` 一次 → `git log -1` 消息正确、`git show --stat` 只含库根路径（tests/test_autocommit.py 常驻测试）
- [x] 库指向无 git 目录实测不炸、无噪音（同文件 test_outside_git_worktree_silently_skips，连日志零输出）
- [x] CONTEXT.md 库根词条补"写库自动提交"一句
- [x] 提交按项目惯例独立 commit，工作区其他未提交修改不混入（独立 worktree + refactor/docs 分两次提交）

## Comments

- 2026-08-09 立项：用户确认"按工单流程走"；范围澄清 = 写库动作包括参考文件归档（references/）；发布形态与赛题素材版权边界仍待定（ADR 0008 已记）
- 2026-08-09 实施：autocommit.py 纯函数 + config 开关 + 8 调用点（消息模板全部按提示词）+ 结构测试防漏挂（8 函数源码含调用与消息片段双断言）；实现注意点落地 = 库根取调用参数的父目录（四库平级共居），git add 目标与 toplevel 探测按库根算；两处行号钉死测试（file_label / ValidationResult 单源）随 library.py 增行同步更新
