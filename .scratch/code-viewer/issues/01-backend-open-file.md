# 01 — 后端：目录打开与文件读取端点

**要做什么：** 代码查看器的数据食粮——用户选一个文件夹（或从最近记录进入输出目录）后，后端能返回该目录的扁平文件清单；用户点树内任意文本文件时能安全读到全文。端到端：`POST /api/code/open`（body `{dir}`）→ `{root, files: [{path, size_bytes}]}`（噪音目录跳过、条目超限 400 中文）；`GET /api/code/file?dir=&path=` → `{path, size_bytes, content, outline: null}`（穿越 / 二进制 / 超限三类均 400 中文）。**载荷不含 language 字段**（前端用既有 fx/languageOf(path) 单源判定渲染语言；大纲在 03 接入前 outline 恒为 null）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 新模块 codeview.py：`list_code_tree(root)`（不存在/非目录 400；treewalk.iter_project_files 同口径噪音跳过、确定性排序；超 `CODE_TREE_MAX_ENTRIES=5000` 400 中文「目录文件过多」）与 `read_code_file(root, rel_path)`（路径安全三约束照母版 read_master_tree_file：is_unsafe_path 同拒绝面 + resolve 后必须在 root 内 + NUL 二进制拒绝；`CODE_FILE_MAX_BYTES=1024*1024` 超限拒绝；utf-8 errors=replace + \r\n 归一；返回 {path, size_bytes, content, outline: null}，不含 language——前端 fx/languageOf 单源）。
- [x] 新错误类 CodeViewError 登记 errors.py（照 MasterError 先例 → 400 中文；未登记异常 = 真 bug → 500 不变量不变）。
- [x] webapp.py 注册 `POST /api/code/open` 与 `GET /api/code/file`（照既有路由转调风格，dir = 服务器本地绝对路径，与 /api/masters/import 同风险面）。
- [x] tests/test_codeview.py（tmp_path 造树：清单结构/噪音跳过/上限/不存在目录/三类 400/语言判定/换行归一）+ tests/test_webapp.py 端点 200/400；全量 pytest 绿。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点）：实现位置 `src/contest_generator/codeview.py`——
  `CODE_TREE_MAX_ENTRIES=5000`/`CODE_FILE_MAX_BYTES=1MB`（26/28 行）、
  `list_code_tree`（81-113：`root.is_dir()` 否则 400、`_iter_project_dirs` 走
  `skip_project_noise` 单源剪枝、`iter_project_files` 同口径、`entries.sort` 确定性、
  超限 400「目录文件过多」）、`read_code_file`（136-177：`_resolve_in_root` 116-133
  调 `entry_store.is_unsafe_path` + resolve 后必须落 root 内、NUL 二进制拒绝 161-162、
  超限 158-159、`errors="replace"` + `\r\n`/`\r` 归一 169、返回不含 language）。
  `CodeViewError` 定义 codeview.py:50，登记 `src/contest_generator/errors.py:256`
  → 400 中文。路由 `src/contest_generator/webapp.py:4377 @app.post("/api/code/open")`、
  `:4392 @app.get("/api/code/file")`。
  测试：`tests/test_codeview.py:47/68/77/82/90`（清单/空目录/缺目录/文件当根/上限）、
  `:106/118/137/144/152`（读全文归一/缺文件/穿越参数化/NUL/超限）、
  `tests/test_webapp.py:8228/8243/8250/8261/8275/8287/8300`（端点 200/400）。
  验收逐条对照：① list_code_tree + 上限 400 ✓ ② read_code_file 三约束 + 归一 ✓
  ③ CodeViewError 登记 ✓ ④ 路由注册 ✓ ⑤ 测试与 pytest 绿 ✓。
  唯一口径偏差（不影响行为）：工单原文说「03 接入前 outline 恒为 null」，03 已落地，
  现 `.c/.h` 返回大纲数组、非 C 仍 null（codeview.py:174）。
