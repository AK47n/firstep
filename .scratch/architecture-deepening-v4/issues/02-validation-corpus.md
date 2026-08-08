# 02 — 架构深化 v4：生成校验族——ModuleCorpus 语料遍历（候选 2，Strong）

**What to build:** 第四轮架构深化（2026-08-08 grilling 共识，候选 2）。五道生成门禁（`_check_module_files` / `_check_main_calls` / `_check_module_self_include` / `_check_unresolved_includes` / `_check_macro_conflicts`，generator.py:352/370/399/460/544）各自复制"manifests → 平台条目 → entry.files → read_text(errors=replace)"编排，同一批文件读五遍；`_check_main_calls` 还经 verify_main_c 重跑 `build_skeleton_interfaces` 再读一遍全部模块头。门禁签名 5 参数起步且越长越多。深化：一次遍历产出内存语料，门禁退化为吃语料的纯谓词，测试直接构造内存语料、不再需要盘上夹具。

1. **generator.py 公开语料对象**（无下划线，测试可内存直构）：
   - `ModuleFile` dataclass——rel 路径 / 绝对路径 / 文本 / 类别（.c / .h / 其它）；
   - `ModuleCorpus` dataclass——每模块（slug / 平台条目 / 文件列表）+ main.c 文本 + 母版头文件列表（文本）；
   - `build_module_corpus(manifests, platform, library_dir, master_project_dir)`——一次读盘；文件缺失**不读**（存在性检查归 `_check_module_files`，读不到的记录为缺失，不在构建期 raise，保持门禁职责不变）。
2. **五道门改签名 `(main_c, corpus)` / `(corpus)`**：遍历编排删除，各自只剩纯谓词逻辑与错误组装；`_check_unresolved_includes` 的搜索目录集（母版 IncludePath + 各模块代码目录）从 corpus 推导；`_check_macro_conflicts` 的母版 `rglob("*.h")` 吃 corpus 里的母版头列表（一次读盘，不再每次 rglob + read）。
3. **接口块格式化纯函数拆出**：skeleton.py 的 `build_skeleton_interfaces`（读盘 + 格式化）拆为 `format_interface_blocks(headers)` 纯函数（格式化唯一实现）；骨架流程 = 读盘 + 格式化，生成门禁 = corpus 文本 + 同一格式化。`verify_main_c` 增加吃预读文本的重载（或签名改收 interfaces 块），骨架流程调用点不变。
4. **测试重构**：test_generator.py 的盘上夹具 `_add_module` 改为内存构造 ModuleCorpus 直喂门禁；保留少量盘上 end-to-end 用例（生成流程整体），其余全内存化。
5. **刻意不做（边界，勿越）**：modules 布局知识统一（MODULES_SUBDIR generator.py:42 / ccs.py:25 MODULES_SOURCE_ENTRY_NAME / keil.py:28 / patchers.py:26 五处编码）**不在本次范围**（候选 5 留后续工单）；include 门平台盲区（候选 4）不动。

**明确不动的（边界）**：webapp.py / keil.py / ccs.py 零改动；skeleton 骨架流程（generate_skeleton / build_skeleton_interfaces 对外签名）；错误类型与文案契约逐字不变。

**Status:** pending

## 验收

- [ ] 全量 pytest 绿；五道门对同一 corpus 的既有行为用例原样过（错误文案逐字不变）
- [ ] `grep -rn "read_text" src/contest_generator/generator.py` 只剩 build_module_corpus 一处读盘点（门禁内无 read_text）
- [ ] 测试有纯内存构造 ModuleCorpus 直喂门禁的用例（无盘上夹具）
- [ ] verify_main_c 门禁侧不再重读盘（skeleton 骨架流程读盘路径不变）

## Comments

（2026-08-08 立项，grilling 共识：候选 2。范围 A——只服务五道门；format_interface_blocks 纯函数共享一份格式化；布局统一与平台盲区明确不做。依赖 01（门禁用 clex 词法原语）。）
