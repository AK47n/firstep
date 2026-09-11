# 01 — 提交主题带 BOM 时打穿 CHANGELOG 跳过清单

**要做什么：** `changelog._is_displayable` 对带 UTF-8 BOM（`\ufeff`）的提交主题判不出
`docs:` / `chore:` / `test:` / `merge` 前缀，于是这类机器提交会被**当成用户可见条目**
补录进 CHANGELOG（污染定稿区上游的草稿区）。修法 = 判定前先 `lstrip("\ufeff \t")`
（顺带吃掉前导空格/制表符），并补一条 `\ufefftest: …` → 不显示的用例。

来源：在途盘点「新发现」第 6 条 + `real-acceptance/00` 单「两笔自己冒出来的待办」第二笔
（另一笔是生成期引脚冲突门禁，见 `.scratch/pin-conflict-gate/`）。

**被谁阻塞：** 无（可立即开始）。

**状态：** resolved

## 落地记录

- `changelog._is_displayable` 判定前先 `subject.lstrip("\ufeff \t")`（只吃前导噪声，
  不做别的规范化）；docstring 写清触发路径（PS 5.1 `Out-File -Encoding utf8` 的 BOM
  经 `git commit -F` 进主题 → `git log --format=%s` 带 `\ufeff` → startswith 判不出跳过前缀）。
- 红证：`git stash` 掉 changelog.py 改动后新用例失败（`\ufefftest:` 被判为可显示），
  改后全绿。
- 测试：`tests/test_changelog.py::test_is_displayable_skips_bom_prefixed_machine_commits`
  —— BOM + docs/chore/test/merge/lib 四种跳过形态 + 前导空白 + 两条「只有 BOM 的真条目
  照常显示」；全量 pytest 绿。

## 现场与影响

- 触发路径：提交信息文件是在 Windows 上用 `Out-File -Encoding utf8`（PS 5.1）写的 →
  文件头带 BOM → `git commit -F` 把 BOM 带进主题 → `git log --format=%s` 取出的主题以
  `\ufeff` 开头 → `subject.lower().startswith(("merge", "docs:", "chore:", "test:"))` 不命中
  → 该条进 CHANGELOG。
- 影响面小但真实：CHANGELOG 是发版定稿（`VERSIONS.md`）的上游，噪声条目会被人肉带进
  定稿区；且这类污染**事后看不懂**（条目文本看着就是普通中文，看不出是机器提交）。
- 现状代码：`changelog.py:246` `_is_displayable(subject)`——直接 `startswith`，无清洗。

## 文件边界

- `src/contest_generator/changelog.py`（`_is_displayable` 一行清洗）
- `tests/test_changelog.py`（新增用例：BOM 前缀的四种跳过形态 + 正常条目不受影响）

## 验收标准

- [x] 红证先行：新增用例在改前失败（`\ufefftest: 随便` 被判为可显示）
- [x] 改后 `\ufeff` + `docs:` / `chore:` / `test:` / `merge` 四种形态一律不显示；
      `\ufefffeat: …` 这类**真条目**仍照常显示（只吃 BOM，不做别的规范化）
- [x] 既有用例全绿（清洗不改任何既有判定）
- [x] 全量 `pytest` + `node --test tests/js/*.test.mjs` 绿

## 不做什么（范围外）

- 不改 CHANGELOG 的补录机制（post-commit → `changelog.py` 流程、`_SKIP_PREFIXES` 词表不动）。
- 不加「提交信息规范化」的额外规则（大小写、空白之外的清洗不在范围）。
- 不动 git 钩子（`.githooks/commit-msg` 的中文门禁与本单无关）。
