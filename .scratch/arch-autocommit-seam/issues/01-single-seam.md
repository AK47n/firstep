# 01 — 自动提交单缝（工单 01 深化：覆盖全 CRUD + 结构测试分类注册表）

**What to build:** 工单 01（lib-autocommit）只挂了 8 个调用点：模块 5 + 母版入库 + 赛题拆条 + 归档批次。「录入即进历史」对四库其余 CRUD 静默落空——4 条网页直调路径（新增/删除参考文件条目、删除赛题、删除母版）写库后从不提交；结构测试钉死 8 个函数枚举，新写函数漏挂测试仍绿。本工单把覆盖补全，并把结构测试从"枚举挂点"升级为"全公开函数分类注册表"（防漏从人工清单变结构性）。

**Blocked by:** 无

**Status:** resolved

## 需求

1. **补挂 4 个直调写函数**（消息模板照家规 `lib: <动作> <id>`）：
   - `reference_library.add_reference` → `lib: add reference <id>`（网页 /api/references 新增，webapp.py:906 直调）
   - `reference_library.delete_reference` → `lib: delete reference <id>`（webapp.py:922 直调）
   - `topic_library.delete_topic` → `lib: delete topic <key>`（webapp.py:1047 直调）
   - `master_store.delete_master` → `lib: delete master <platform>`（webapp.py:815 直调）
2. **不挂**：`archive_reference`（唯一调用方 `archive.write_archive_entries` 已批次级提交，双挂 = 双提交，webapp 不直调——已核实）；`save_manifest`（内部辅助，两个调用方 update_module_description / add_platform_files 均已挂——原工单已分类，延续）。
3. **结构测试升级**（替换 tests/test_autocommit.py 的 `test_all_write_functions_hook_autocommit`）：对 library / reference_library / topic_library / master_store / archive 五个模块的**全部公开函数**建分类注册表，每项三类之一：
   - `commit`：源码含 `commit_after_write(` 与消息片段
   - `delegated`：源码不含 `commit_after_write(`，且其调用方链最终达 commit 函数（archive_reference / save_manifest 属此类）
   - `read`：源码不含任何写原语标记（entry_transaction( / delete_entry( / write_json( / write_text( / rmtree( / copy2( / open( / mkdir( / _write_manifest( / _write_meta( / _write_files( 等）
   - **未知公开函数即红**；`read` 类含写原语即红；`delegated` 类含 `commit_after_write(` 即红。参考 errors.py 反射测试先例。
4. **批次语义不动**：confirm_topics / write_archive_entries 保持批次级单提交，不为批内条目逐条提交（批次回滚 discard_entry_dirs 后 git 历史不留孤儿提交）。
5. **暂存范围不动**：整库根 `git add`（docstring 明示设计，变更限库根子树），本工单不碰。
6. **CONTEXT.md** 库根词条补一句覆盖语义（四库全部写函数 + 结构测试强制分类 + 批次级提交）。

## 文件边界

- `src/contest_generator/reference_library.py`：import autocommit + add_reference / delete_reference 收尾各一行（archive_reference 不动）
- `src/contest_generator/topic_library.py`：delete_topic 收尾一行（confirm_topics 已有）
- `src/contest_generator/master_store.py`：delete_master 收尾一行（import_master 已有）
- `tests/test_autocommit.py`：结构测试替换 + 新增行为测试（tmp 伪 git 库：4 个新挂点各一条提交消息断言；归档批次 N 条目 = 1 提交回归）
- `CONTEXT.md`：库根词条补句
- 注意：reference_library.py 有在途未提交改动（体量字段 file_count/size_bytes + entry_stats），本工单在其上叠加或先独立提交，不混批

## 验收

- [x] 全量测试绿 + mypy 干净
- [x] 结构测试自证：临时新增一个不挂的写函数 → 红；删掉恢复绿
- [x] tmp 伪 git 库：add_reference / delete_reference / delete_topic / delete_master 各产生一条消息正确提交（另含清单外 update_platform_identity）
- [x] 归档批次回归：N 条目 = 1 提交（无双提交）
- [x] CONTEXT.md 库根词条更新
- [x] 独立 worktree + 独立 commit，工作区其他未提交修改不混入

## Comments

- 2026-08-09 立项（架构评审 2026-08-09 候选 #1，grilling 决策树，用户授权代决）：四问全按推荐——① 接缝形状 A：机制不变，结构测试升级为分类注册表（entry_store 事务出口方案被事实否决：entry_transaction 只覆盖建目录类 4/13 路径，in-place 写入与删除都不走它，且掺 git 知识破坏原语纯净）；② 覆盖 = 补挂 4 直调（archive_reference 仅批次调用已核实）；③ 批次级单提交保持（孤儿提交论证）；④ 整库根 add 保持（docstring 明示设计，漏路径 = 静默丢变更与"绝不抛"精神冲突）
- 2026-08-09 实施（worktree-autocommit-seam-01 @ c98d7f8，独立提交，在途体量字段改动未混入）：**补挂 5 个而非 4 个**——webapp.py:674 直调 update_platform_identity（写经 save_manifest，save_manifest 是内部辅助不自提，链上无任何提交，与"覆盖全 CRUD"同类漏洞），工单清单漏列，结构测试注册表逼迫显形后一并补挂，消息 `lib: update platform identity <slug> <platform>`；4 工单挂点消息照家规 `lib: add/delete reference <id>` / `lib: delete topic <key>` / `lib: delete master <platform>`。结构测试替换枚举为五模块（library/reference_library/topic_library/master_store/archive）公开函数分类注册表（commit 须含 commit_after_write( + 消息片段 / delegated 不含且调用方链 BFS 达 commit / read 不含写原语标记），未知即红。自证通过：注入不挂写函数 → 红，删除 → 绿。归档批次 N 条目 = 1 提交回归通过。验收全勾，868 绿 + mypy 干净。备注：注册表预登记 entry_stats（在途体量字段工单的读函数），两支先后合 main 都不红；git worktree 首次检出报 Filename too long（sources/materials 深路径），已设 core.longpaths=true（仅 .git/config）
