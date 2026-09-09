# 01 — 后端保存链路：save_code_file + mtime_ns/utf8 + POST /api/code/save

**要做什么：** 让「代码」tab 具备后端保存能力（上联前端 Ctrl+S）：新增
`POST /api/code/save`（写回磁盘，UTF-8 + \n 换行 + 临时文件 os.replace 原子
写），`GET /api/code/file` 载荷新增 `mtime_ns`（st_mtime_ns）与 `utf8`（严格
解码成功与否）两字段（前端冲突检测与非 UTF-8 只读的依据）；保存冲突 = 新
错误类 `CodeViewConflictError` → 409 中文（errors.py 登记，照
GenerationBusyError 409 先例）。读面拒绝面与其余字段逐字节不变，本票不触
前端行为（读面新增字段无害）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实现笔记（据 tdd 落地）：** 依既有测试范式（tmp_path 造树 / 参数化拒绝面）追加 save 用例；`save_code_file` 原子写 = `candidate.with_name(candidate.name + ".tmp-pid")` + `os.replace`；冲突比较用 `st_mtime_ns` 精确相等；`CodeViewConflictError` 继承 CodeViewError 并登记 409。

- [x] `codeview.py` 新增 `save_code_file(root, rel_path, content, base_mtime_ns) -> {path, size_bytes, mtime_ns, outline}`：安全判定复用 `_resolve_in_root` 单源 + is_file（不存在 → 400「文件不存在」，不新建文件）；content 超 `CODE_FILE_MAX_BYTES` → 400；磁盘 `st_mtime_ns` ≠ `base_mtime_ns` → `CodeViewConflictError`（409 中文，message 说明磁盘已被外部修改）；一致 → 原子写（同目录临时文件 + `os.replace`，UTF-8、newline="\n"）；outline 仅 .c/.h（`_outline_for` 重算返回）。
- [x] `read_code_file` 返回新增 `mtime_ns` 与 `utf8` 字段（utf8 = `data.decode("utf-8", errors="strict")` 成功；二进制已在 NUL 检查前拒绝，此处只判非 UTF-8 文本）。
- [x] `errors.py` 登记 `_ErrorEntry((CodeViewConflictError,), 409, str)`；`CodeViewConflictError` 继承 CodeViewError。
- [x] `webapp.py` 注册 `POST /api/code/save`：`{dir, path, content, base_mtime_ns}` → 转调域函数；content 非字符串 / 缺 base_mtime_ns → 400 中文（既有 `_require_str` 风格）。
- [x] `tests/test_codeview.py` 追加：save 正常 roundtrip（含 \n 归一与返回字段）、outline 仅 .c/.h、路径穿越/不存在文件/超限 400、冲突 409、read 新字段断言；既有用例全绿。
- [x] 全量 pytest 绿；提交信息中文。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点；验收 checkbox 原未勾，代码事实已全部满足）：
  实现位置 `src/contest_generator/codeview.py:308 save_code_file`——content 非 str 400
  （332-333）、base_mtime_ns 接受 int/数字字符串、非数字 400（334-340）、
  `_resolve_in_root` 安全单源 + 文件必须存在（341-343）、非 UTF-8 原文拒绝（347-352）、
  超 `CODE_FILE_MAX_BYTES` 400（355-356）、`st_mtime_ns != base_mtime_ns` →
  `CodeViewConflictError`（357-361）、同目录临时文件 + `os.replace` 原子写 UTF-8/\n
  （362-371）、返回 `{path,size_bytes,mtime_ns,outline}`（373-378）。
  `read_code_file` 读面新增字段：`mtime_ns`（字符串）与 `utf8`（164-176）。
  `CodeViewConflictError` 定义 codeview.py:54（继承 CodeViewError），登记
  `src/contest_generator/errors.py:219 _ErrorEntry((CodeViewConflictError,), 409, str)`
  （注释 217-218 说明必须排在 400 大元组之前）。
  路由 `src/contest_generator/webapp.py:4457 @app.post("/api/code/save")`（dir/path
  走 `_require_str`，content 只做类型闸不走 strip，base_mtime_ns 必填）。
  测试：`tests/test_codeview.py:417/430/442/449/458/471`（写盘归一/字符串基准/
  非数字/outline 分支/冲突 409/重写后新基准可再存）、`:496/503/510/519/524/532/539`
  （穿越/缺文件/超限/缺根/非文本/缺基准/非 UTF-8 拒绝）、`:385/396/402`
  （mtime_ns 字符串与 utf8 标志）；端点 `tests/test_webapp.py:8421/8445/8458/8464/8476`。
  验收逐条对照：① save_code_file 全部写前约束 + 原子写 ✓ ② read_code_file 新字段 ✓
  ③ errors.py 409 登记 ✓ ④ webapp 路由 ✓ ⑤ 测试覆盖 ✓ ⑥ pytest 绿（见盘点表）✓。

## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
