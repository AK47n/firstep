# 02 — 后端：跨文件搜索端点

**要做什么：** 学生输入关键词后，后端跨文件查找并返回命中。端到端：`GET /api/code/search?dir=&q=` → `{hits: [{path, line, text}], truncated, files_scanned}`——大小写不敏感子串匹配（中文不受影响），跳过噪音（treewalk 同口径）/ 二进制（NUL 探测）/ 超限文件（1MB）；命中上限 `CODE_SEARCH_MAX_HITS=200`，到达即停并置 truncated；空 q → 400 中文。

**被谁阻塞：** 无——与 01 平行（01 先审出拒绝面与错误类，02 复用同一批原语；若 01 尚未 resolved 则 02 落票时调用处与既有函数对齐）。

**状态：** resolved

- [x] codeview.py 增 `search_code_files(root, q)` + `GET /api/code/search` 路由；命中行 text 裁剪（前后各约 60 字符、空白压缩）。
- [x] 空 q 400 中文；结果上限 200 + truncated 标志；二进制 / 超限 / 噪音跳过。
- [x] tests/test_codeview.py 增 search 用例（命中/大小写不敏感/上限 truncated/跳过/空 q）+ test_webapp.py 端点 200/400；全量 pytest 绿。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点）：`src/contest_generator/codeview.py:243`
  `search_code_files`——空 q 400（256-258）、目录不存在 400（259-260）、
  `needle = q.lower()` 大小写不敏感（261）、`iter_project_files` 噪音跳过 +
  超 1MB 跳过（266-267）+ 头 512 字节 NUL 二进制跳过（268-271）、
  `CODE_SEARCH_MAX_HITS=200` 到达截断 truncated（30 行常量）、命中行裁剪
  `_snippet`（287-305：空白压缩 + 以命中点为中心两侧各 60 字符 + 省略号）。
  路由 `src/contest_generator/webapp.py:4422 @app.get("/api/code/search")`。
  测试：`tests/test_codeview.py:220`（大小写）/`:229`（中文）/`:237`（跳过噪音二进制超限）/
  `:248`（上限 truncated）/`:261`（snippet 裁剪）/`:275`（零命中仍报 files_scanned）/
  `:283`（空 q 400）/`:290`（缺目录 400）；端点 `tests/test_webapp.py:8312/8327/8335`。
  验收逐条对照：① 端点 + 命中行裁剪 ✓ ② 空 q 400 / 上限 200 + truncated /
  二进制超限噪音跳过 ✓ ③ 测试与 pytest 绿 ✓。
