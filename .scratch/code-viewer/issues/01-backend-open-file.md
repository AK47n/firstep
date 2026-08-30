# 01 — 后端：目录打开与文件读取端点

**要做什么：** 代码查看器的数据食粮——用户选一个文件夹（或从最近记录进入输出目录）后，后端能返回该目录的扁平文件清单；用户点树内任意文本文件时能安全读到全文。端到端：`POST /api/code/open`（body `{dir}`）→ `{root, files: [{path, size_bytes}]}`（噪音目录跳过、条目超限 400 中文）；`GET /api/code/file?dir=&path=` → `{path, size_bytes, content, outline: null}`（穿越 / 二进制 / 超限三类均 400 中文）。**载荷不含 language 字段**（前端用既有 fx/languageOf(path) 单源判定渲染语言；大纲在 03 接入前 outline 恒为 null）。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

- [x] 新模块 codeview.py：`list_code_tree(root)`（不存在/非目录 400；treewalk.iter_project_files 同口径噪音跳过、确定性排序；超 `CODE_TREE_MAX_ENTRIES=5000` 400 中文「目录文件过多」）与 `read_code_file(root, rel_path)`（路径安全三约束照母版 read_master_tree_file：is_unsafe_path 同拒绝面 + resolve 后必须在 root 内 + NUL 二进制拒绝；`CODE_FILE_MAX_BYTES=1024*1024` 超限拒绝；utf-8 errors=replace + \r\n 归一；返回 {path, size_bytes, content, outline: null}，不含 language——前端 fx/languageOf 单源）。
- [x] 新错误类 CodeViewError 登记 errors.py（照 MasterError 先例 → 400 中文；未登记异常 = 真 bug → 500 不变量不变）。
- [x] webapp.py 注册 `POST /api/code/open` 与 `GET /api/code/file`（照既有路由转调风格，dir = 服务器本地绝对路径，与 /api/masters/import 同风险面）。
- [x] tests/test_codeview.py（tmp_path 造树：清单结构/噪音跳过/上限/不存在目录/三类 400/语言判定/换行归一）+ tests/test_webapp.py 端点 200/400；全量 pytest 绿。
