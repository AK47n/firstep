# 01 — 后端三端点（create / rename / delete）+ pytest

**要做什么：** codeview.py 新增 `create_code_entry(root, kind, rel_path)`、
`rename_code_entry(root, rel_path, new_name)`、`delete_code_entry(root, rel_path)`
三个核心函数（全部走 `_resolve_in_root` + `is_unsafe_path` 单源，失败 400
中文 CodeViewError）；webapp.py 登记 `POST /api/code/tree/create` /
`/rename` / `/delete`（dir 走 `_require_str`，与 /api/code/save 同风格）；
tests/test_webapp.py 扩展覆盖。

**被谁阻塞：** 无（依赖 code-viewer-editor/01 的 _resolve_in_root，
已落地）。

**状态：** resolved

**结论：** 已落地。codeview.py 新增 `_iter_project_dirs`（os.walk 原地剪枝
skip_project_noise 单源）、`list_code_tree` 目录条目 `{path, is_dir: True}`
（含空目录，docstring 契约更新）、`_validate_entry_name`（_CODE_NAME_ILLEGAL
集）、`create_code_entry`/`rename_code_entry`/`delete_code_entry`（全走
_resolve_in_root + is_unsafe_path 单源，失败 400 中文）；webapp.py 登记
POST /api/code/tree/create|rename|delete。评审整改：① create file 改
O_EXCL 原子创建（open O_CREAT|O_EXCL，不存在才成功——无「exists 判后
os.replace 覆盖隙间同名」TOCTOU 窗，隙间同名 → 400「已存在」）；② rename
修 os.rename 后 `src.is_file()` 恒 False 的 bug（rename 前存 was_file）；
改名回自身 = 幂等成功；③ docstring 同步原子语义。测试：tests/test_codeview.py
+25（unsafe 路径 parametrize、list 含空目录、bad_name 参数化）、
tests/test_webapp.py +14；pytest 全量 3101 全绿。验收 1-6 全部满足。
- [ ] 验收 1：create 文件——建成空文件（size 0）、父目录 mkdirs、已存在
  400 中文；返回 {path, size_bytes: 0, mtime_ns: 字符串}。
- [ ] 验收 2：create 目录——makedirs(exist_ok=False)，已存在 400；返回
  {path}；嵌套路径（如 src/kernel/）一次建出。
- [ ] 验收 3：rename——文件/目录均可改（os.rename 原子）；new_name 单段
  校验（空/含 `/ \ : * ? " < > |`/`.`/`..` → 400 中文）；源不存在 400；
  目标已存在 400；文件返回 {path, mtime_ns 字符串}，目录返回 {path}。
- [ ] 验收 4：delete——文件删除；目录仅空可删（rmdir），非空 400 中文；
  不存在 400；返回 {removed: true}。
- [ ] 验收 5：越界/非法路径（`..`、绝对路径、盘符、NUL 段）全部 400 中文
  （复用 _resolve_in_root 既有语义，无新增绕过）。
- [ ] 验收 6：webapp 路由契约错误（缺 dir / 缺 path / type 非法 / new_name
  缺失）→ 400 中文；pytest 新增用例全绿。
