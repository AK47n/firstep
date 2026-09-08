# 01 — 后端保存链路：save_code_file + mtime_ns/utf8 + POST /api/code/save

**要做什么：** 让「代码」tab 具备后端保存能力（上联前端 Ctrl+S）：新增
`POST /api/code/save`（写回磁盘，UTF-8 + \n 换行 + 临时文件 os.replace 原子
写），`GET /api/code/file` 载荷新增 `mtime_ns`（st_mtime_ns）与 `utf8`（严格
解码成功与否）两字段（前端冲突检测与非 UTF-8 只读的依据）；保存冲突 = 新
错误类 `CodeViewConflictError` → 409 中文（errors.py 登记，照
GenerationBusyError 409 先例）。读面拒绝面与其余字段逐字节不变，本票不触
前端行为（读面新增字段无害）。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

**实现笔记（据 tdd 落地）：** 依既有测试范式（tmp_path 造树 / 参数化拒绝面）追加 save 用例；`save_code_file` 原子写 = `candidate.with_name(candidate.name + ".tmp-pid")` + `os.replace`；冲突比较用 `st_mtime_ns` 精确相等；`CodeViewConflictError` 继承 CodeViewError 并登记 409。

- [ ] `codeview.py` 新增 `save_code_file(root, rel_path, content, base_mtime_ns) -> {path, size_bytes, mtime_ns, outline}`：安全判定复用 `_resolve_in_root` 单源 + is_file（不存在 → 400「文件不存在」，不新建文件）；content 超 `CODE_FILE_MAX_BYTES` → 400；磁盘 `st_mtime_ns` ≠ `base_mtime_ns` → `CodeViewConflictError`（409 中文，message 说明磁盘已被外部修改）；一致 → 原子写（同目录临时文件 + `os.replace`，UTF-8、newline="\n"）；outline 仅 .c/.h（`_outline_for` 重算返回）。
- [ ] `read_code_file` 返回新增 `mtime_ns` 与 `utf8` 字段（utf8 = `data.decode("utf-8", errors="strict")` 成功；二进制已在 NUL 检查前拒绝，此处只判非 UTF-8 文本）。
- [ ] `errors.py` 登记 `_ErrorEntry((CodeViewConflictError,), 409, str)`；`CodeViewConflictError` 继承 CodeViewError。
- [ ] `webapp.py` 注册 `POST /api/code/save`：`{dir, path, content, base_mtime_ns}` → 转调域函数；content 非字符串 / 缺 base_mtime_ns → 400 中文（既有 `_require_str` 风格）。
- [ ] `tests/test_codeview.py` 追加：save 正常 roundtrip（含 \n 归一与返回字段）、outline 仅 .c/.h、路径穿越/不存在文件/超限 400、冲突 409、read 新字段断言；既有用例全绿。
- [ ] 全量 pytest 绿；提交信息中文。

(End of file - total 22 lines)
</content>