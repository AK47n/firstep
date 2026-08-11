# 01 — 模块源读路径单源（read_module_sources + is_header_path，编码策略统一）

**What to build:** 同一批模块文件的读盘在两条路径上各实现一份且容错分歧——skeleton.build_skeleton_interfaces 严格 UTF-8 读（非 UTF-8 头文件直接 UnicodeDecodeError 崩），generator.build_module_corpus 对同批文件 errors="replace" 静默替换；头部判定 `skeleton._is_header_path`（`.h` endswith 大小写不敏感）与 generator.kind 分类的 `.h` 分支语义完全相同却两处推导；读盘循环同构 ~15 行 ×2。另有 `skeleton.verify_main_c` 盘上重读版生产零调用（仅测试引用）= 死代码。本工单把模块源读盘收进单原语，编码策略与头部判定单源，死代码随迁。

**Blocked by:** 无

**Status:** resolved（2026-08-09 已合 main PR #32，920 绿 + mypy 干净）

## 需求

1. **skeleton.py 增共享原语**（骨架/接口读取域，generator 已 import skeleton，无环）：
   - `read_module_sources(manifests, platform, library_dir) -> tuple[list[tuple[slug, rel, text, path]], list[tuple[slug, rel]]]`：有平台条目的模块文件读盘单源——缺失不 raise（存在性由门禁报告，现状语义）、文本 `errors="replace"`（与门禁同策略）、返回 (present, missing)
   - `is_header_path(rel)`：`_is_header_path` 公开化（语义逐字：`.h` endswith 大小写不敏感），头部判定唯一出处
2. **skeleton.build_skeleton_interfaces 消费原语**：present 过滤 is_header_path → headers；缺失头文件占位块逻辑（"头文件缺失，无接口"）由 present/missing 共同推导保持；**行为变化（刻意）**：非 UTF-8 头文件从"骨架阶段 UnicodeDecodeError 崩"变"替换后继续"——与门禁对齐，编码策略单源
3. **generator.build_module_corpus 消费原语**：present → ModuleFile（kind 判定改走 is_header_path 单源：`"h" if is_header_path(rel) else ("c" if rel.lower().endswith(".c") else "other")`，语义逐字）；missing → missing_files 记录；missing_platforms 逻辑保留在 generator（平台条目存在性是语料职责，原语只做有平台条目后的文件读盘）；**行为逐字**（语料形状不变，既有用例零改动）
4. **死代码删除**：`skeleton.verify_main_c`（生产零调用，仅 tests/test_skeleton.py:307,315 引用）删除，测试迁移到 verify_main_c_interfaces 或删除
5. **结构测试**：is_header_path / read_module_sources 定义单址；skeleton 源码无 read_text（全部走原语，grep 式先例）；generator 模块文件段无裸 read_text 循环
6. **CONTEXT.md**：模块词条或架构要点补"模块源读路径单源（read_module_sources + is_header_path，errors=replace 编码策略单源，骨架与门禁同读法）"

## 文件边界

- `src/contest_generator/skeleton.py`（+read_module_sources +is_header_path；build_skeleton_interfaces 消费；删 verify_main_c）
- `src/contest_generator/generator.py`（build_module_corpus 模块段消费原语 + kind 走 is_header_path；import 行并入既有 skeleton import）
- `tests/test_skeleton.py`（既有接口块用例零改动；非 UTF-8 头不崩新增一条；verify_main_c 测试迁移/删除）
- `tests/test_generator.py`（语料构建既有用例零改动；结构测试）
- `CONTEXT.md`

## 验收

- [ ] 全量测试绿 + mypy 干净
- [ ] 既有用例零改动通过（接口块 / 语料构建行为逐字）
- [ ] 非 UTF-8 头文件骨架阶段不再崩（replace 后进接口块）——新测试红→绿（旧行为模拟下红）
- [ ] 结构自证：is_header_path / read_module_sources 单址；skeleton 无 read_text；generator 模块文件段无裸 read_text
- [ ] verify_main_c 删除后 grep 全仓零残留
- [ ] CONTEXT.md 更新
- [ ] 独立 worktree + 独立 commit

## Comments

- 2026-08-09 立项（架构评审 2026-08-09 候选 5，用户授权代决）：① 共享原语落 skeleton.py（generator 已 import skeleton，反向会环——build_module_corpus 的母版头读留在 generator，原语只做模块文件段）；② 编码策略 = errors="replace" 单源（骨架从崩变不崩 = 刻意行为变化，与门禁对齐——"同一语义两种容错"的分歧消失）；③ is_header_path 公开化（kind 的 .h 分支改走它，语义逐字）；④ verify_main_c 死代码删除（生产零调用，仅测试）；⑤ API 边界使"物理读盘一次"不可能（骨架/生成两个独立请求），单源的是读法而非读次；⑥ missing_platforms（平台条目存在性）留 generator——原语只做"有平台条目后的文件读盘"，职责边界不模糊
- 2026-08-09 实施提示词已交付聊天（含文件边界 / 红绿步骤 / 验收 grep / worktree 命令），待新会话执行；设计已在立项 comment 敲定，执行会话按提示词即可，不再开会
- 2026-08-10 已合 main PR #32（4cb7eeb，920 绿 + mypy 干净），Status 补勾 resolved
