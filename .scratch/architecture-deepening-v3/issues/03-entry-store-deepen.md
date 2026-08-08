# 03 — 架构深化 v3：entry_store 深化——库族原语补全（C3）

**What to build:** 第三轮架构深化（2026-08-08 报告，候选 C3，Strong）。"目录即数据库"只收敛了一半：entry_store.py 现只有写 / 迭代 / 事务（64 行），删除 ×4 副本、JSON 读+校验 ×4 副本、键文法 ×3 套（其中 master.py:364 与 library.py:37 的 slug 正则字节相同）、kit 词表 ×3 实现、is_unsafe_path 埋在 manifest.py、一个正则 4 跳 import 链。原语做深，库变薄。

1. **entry_store.py 补原语**（保持"不持业务形状"的 docstring 哲学——键文法与领域校验仍归各库）：
   - `read_json(entry_dir, filename)`——读盘 + OSError/JSONDecodeError → 统一错误包装（各库保留自己的域错误类型，只统一"读盘 + JSON 形状"层）；
   - `delete_entry(root, name)`——目录存在校验（查无此条大声失败）→ rmtree，错误措辞统一；
   - `validate_store_key(name, pattern, what)`——目录名 = 键的校验原语（非法键大声失败，统一措辞），各库传自己的文法正则。
2. **副本归零**：
   - 删除 ×4 → `delete_entry`：library.py:80-86 / topic_library.py:200-209 / reference_library.py:206-212 / master.py:1381-1388；
   - JSON 读+校验 ×4 → `read_json` + 各库保留域解析：manifest.py:95-110（ModuleManifest.load）/ topic_library.py:435-475（_load_entry）/ reference_library.py:155-177（get_reference）/ master.py:1359-1378（get_master）；
   - `_require_str` 域侧副本（master.py:1468 / topic_library.py:478 / reference_library.py:400）随读校验一并收敛；webapp.py:349 的 HTTP 版（HTTPException 语义不同）**不在范围**；
   - kit 词表单源：`collect_kits(manifests)` 唯一实现（放 manifest.py——PlatformEntry.kit 字段所有者），reference_library.module_kit_vocabulary（126-135）/ selection.associated_references（170-176）/ llm.build_manifest_summaries（574-589 内嵌收集）三处改委托（保序去重语义以 manifest 版为准，逐一核对调用方顺序依赖）；
   - is_unsafe_path 从 manifest.py:170-177 移入 entry_store.py（路径安全属目录原语），消费方改导入。
3. **import 链 4 跳 → ≤2 跳**：master.py:59-63 `from .reference_library import validate_topic_anchor` 触发 master → reference_library → topic_library → library 链。目标：master 对 reference_library 的 import 消失（master 需要的赛题键校验直取 topic_library 的文法，或按最小改动裁——键文法属领域模块，不并入 entry_store）；顺带核对四处"查库确认/未接线"TODO 是否可随链变短而收敛（不做大改，只修 import 链）。
4. **刻意保留**（Windows 文件锁特殊性，注释已记真实 incident）：master.py import_master 的 `.importing`/`.backup`/`os.replace` 原子替换舞蹈留在 master，不收进原语。

**明确不动的（边界，勿越）**：wordlist.py、keil.py、ccs.py、events.py、webapp.py（HTTP 侧校验除外，零改动）；各库键文法正则的形状（slug / 2026C 编号 / 条目 id 语义不同，只统一执行原语，不统一正则内容）；错误类型与文案契约（逐字不变，防漂移测试原样过）。

**Status:** resolved

## 验收

- [x] 全量 pytest 绿（753）+ mypy 干净（25 文件）；防漂移测试（类别 key ↔ 字段）原样过
- [x] `grep -rn "def delete_module\|def delete_topic\|def delete_reference\|def delete_master" src` 只剩薄包装（四者都只做键校验 + delete_entry 委托 + 域错误转写）
- [x] `grep -rn "from .reference_library import\|from .topic_library import\|from .library import" src/contest_generator/master.py` 链收敛（master 不再 import reference_library——且 master 运行时闭包经实测不含任何参考库族模块：llm 导入收进 TYPE_CHECKING 后连 llm/selection 都不进闭包）
- [x] `grep -rn "is_unsafe_path\|collect_kits" src/contest_generator/*.py` 定义各只一处（is_unsafe_path = entry_store.py；collect_kits = manifest.py，三处调用方改委托）
- [x] 错误文案逐字不变（既有断言直接过）；CONTEXT.md"素材区"相关词表行已同步（归档 / 参考文件库行 + 新增条目库原语行）

## Comments

（2026-08-08 立项，架构评审 C3。与 C1 重叠：llm.py（build_manifest_summaries 内 kit 收集改委托）与 selection.py（associated_references kit 收集改委托）——C1 只动导入面与搬迁，C3 改这两个函数体，并行合入冲突按仓库惯例解决。）

（2026-08-08 实施完成，refactor 224ca85 合入 709d496，main 753 绿 / mypy 25 文件干净。实施要点与偏差记录：

- **entry_store 补原语**：read_json（StoreReadError/StoreParseError/StoreShapeError 家族，`.error` 持原始异常供域侧原样转写文案）/ delete_entry / validate_store_key / require_str；is_unsafe_path 从 manifest 移入。StoreError 家族从不直达 web 层，已按结构测试要求登记进 test_errors.py 的 500 白名单（带注释）。
- **collect_kits 单源化**：保序去重语义以 manifest 版为准（顺序 = manifests 顺序 × 平台条目插入顺序 × 首次出现）。**行为变化如实记录**：module_kit_vocabulary 由"去重排序"改为"保序去重"——webapp 错误消息"现有：{…}"里的词表顺序变为模块库浏览序，对应测试断言与命名已更新（test_reference_library.py:257）；selection.associated_references 与 llm.build_manifest_summaries 语义零变化（逐一核对：collect_kits 的保序去重与两处内嵌实现字节等价，顺序依赖无损）。
- **import 链收敛（验收偏差）**：工单原案"直取 topic_library 的文法"与验收 grep（master 不得 import 参考库族任一模块）互斥，且 master 的归档步骤还依赖 archive_reference / ProjectComparison / MasterError——reference_library 与 report.py 都放不下（selection → reference_library → master → llm → selection 环 / master ↔ report 环）。按"最小改动裁"：归档辅助 prepare_archive / write_archive_entries 迁入新模块 archive.py（直取 topic_library.validate_topic_key，文案不变），master 在 confirm_distillation 内函数级延迟导入（master ↔ archive 模块级环的唯一解）；master 的 LLM 导入（注释本就声明"仅类型引用"）收进 TYPE_CHECKING——实测 master 运行时 import 闭包 = ccs/entry_store/events/keil/platforms/projectfile/report，零参考库族模块。
- **刻意保留**：import_master 的 `.importing`/`.backup`/`os.replace` 原子替换舞蹈零改动；webapp.py / wordlist.py / keil.py / ccs.py / events.py 一字未动。
- **四处"查库确认/未接线"TODO 核对**：均为赛题库查库确认功能未实现（留待素材区接线工单），与 import 链无关，链变短不能收敛——全部原样保留（reference_library 模块文档 / validate_topic_anchor / add_reference 各一处 + archive.py 的 prepare_archive 文档一处）。
- **新测试**：test_entry_store.py（原语契约：read_json 三错误族 / delete_entry / validate_store_key / require_str / is_unsafe_path）+ test_manifest.py collect_kits 保序去重跳过空值。**未动**：webapp.py 零改动（webapp.py:349 的 HTTP 版 _require_str 不在范围）。）
