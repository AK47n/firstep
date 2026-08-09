# 02 — 架构深化 v5：赛题入口单一接缝——TopicContext 装配收口（候选 5，Strong）

**What to build:** 第五轮架构深化（2026-08-09，候选 5，源自 architecture-review-20260809-102431）。工单 D 建了 `resolve_topic_context` 接缝但没被吃满：recommend / skeleton 走 `_resolve_topic_for_generation`，generate 绕行直调 `resolve_topic_context(llm=None, ...)`（webapp.py:513，第三形状）；recommend 的 no-topic 分支在路由闭包内联重建装配（webapp.py:420-424 `build_manifest_summaries(list_modules(...))`——与 generator.py:162-173 同一装配的第二份拷贝）；布局推导（`topics/`、`references/` 平级兄弟目录）住在 HTTP 壳层（webapp.py:145-161），测试只能手抄（test_webapp.py:1475-1482 "与 webapp 推导一致"）。本轮收口：**装配唯一出处 = `resolve_topic_context`，三路由一个 helper，布局推导归 config.py**。行为零变化（响应形状逐字节不变）。

1. **`resolve_topic_context` 永远返回完整 `TopicContext`**（generator.py:129）：删除 `None` 分支，未识别到历史赛题时产出 no-topic 形——`key=""` 哨兵（docstring 写明：key 非空 = 识别到历史赛题）、`problem_text=粘贴题面原样`、`references=()`、`related_modules=()`、`manifest_summaries=全部模块摘要`、`suggestions=()`、`read_fulltext=_make_fulltext_reader(reference_library_dir, ())`（空集回读器，任何 id 抛 ReferenceError——suggestions 恒空所以永不被调，诚实 no-op）。双政策不变：显式编号查无此条仍大声报错（TopicError → 400），自动识别失败静默降级——只是降级终点从 None 变成 no-topic 上下文。`_resolve_topic_entry` / `_make_fulltext_reader` 不动。
2. **webapp 收口成单一 helper `_assemble_topic_context(context, topic_id, problem_text, llm) -> TopicContext`**：函数体 = 取 config + 推导两目录 + 调 `resolve_topic_context`；返回从 `(TopicContext | None, str)` 坍缩为 `TopicContext`（problem_text 从 `topic.problem_text` 取，不再返回元组）。三路由各一行：recommend / skeleton 传 `_llm(context)`，generate 传 `None`（显式编号路径，语义沿用）。`if topic is not None:` 改 `if topic.key:`（recommend 的 topic_id/related_modules 注入、skeleton 的 prepend 同语义）。recommend 的 no-topic 内联装配（420-424）删除；generate 的直调（513-520）删除，`if topic_id:` 守卫保留。
3. **布局推导归 config.py**：新增两个纯函数 `config.topic_library_dir(module_library_dir) -> Path`（= 父目录 / "topics"）与 `config.reference_library_dir(module_library_dir) -> Path`（= 父目录 / "references"），docstring 保留"将来加配置项只改这一处"语义（放 config.py 正是那个"一处"）。webapp 删 `_topic_library_dir` / `_reference_dir` 私有委托（helper 内直调 config 函数）；test_webapp 的 `_wire_material_libraries` 改从 config import（"与 webapp 推导一致"的手抄注释消失——构造一致性）。
4. **import 面清理**：webapp 不再 import `build_manifest_summaries`（llm）与 `list_modules`（library）——装配不再发生在路由；grep 全扫确认零残留。
5. **测试**：test_generator 的 resolve_topic_context 用例——no-topic 断言（`is None` → `ctx.key == ""` + manifest_summaries = 全模块 + read_fulltext 空集调用抛 ReferenceError），其余（显式条目物化 / 编号识别 / 查无此条报错 / 关联模块）原样过；test_webapp 的 recommend / skeleton / generate 行为用例原样过（响应形状逐字节不变）；新增结构测试（防回退，先例 errors.py）：webapp 模块无 `build_manifest_summaries` / `list_modules` 属性（装配不在路由），config 两函数是布局推导唯一出处（`config.topic_library_dir` 与 test 消费同源）。
6. **CONTEXT.md**：「赛题」词条主要实现补 `generator.resolve_topic_context`（生成入口装配唯一出处）；「架构要点」接缝行补"赛题入口装配 = resolve_topic_context 唯一出处，路由只消费"。

**明确不动的（边界，勿越）**：响应形状逐字节不变（topic_id 只在识别到时出现、skeleton 的 prepend 语义、generate 的 related_modules 注入）；generate 保持服务端重算（客户端回传 topic_id 仍由服务端校验重派生——回传值不可信原则，库会变）；前端 index.html 零改动；events / errors / sse / llm / selection / topic_library / reference_library 零改动（config.py 只加两个纯函数）；`_resolve_topic_entry` / `_make_fulltext_reader` 内部实现不动；不引入新配置项（config.json 格式不变）。

**Status:** resolved（2026-08-09 合入 main 1fa1102，803 绿 + mypy 干净，PR #19）

## 验收

- [x] 全量 pytest 绿（基线 801）+ mypy 干净；recommend / skeleton / generate 响应形状逐字节不变（既有断言原样过）
- [x] `grep -rn "build_manifest_summaries\|list_modules" src/contest_generator/webapp.py` 无结果（装配不在路由）；`resolve_topic_context(` 在 webapp 只剩 helper 一处调用
- [x] 结构测试过：webapp 无装配 import 属性；config.topic_library_dir / config.reference_library_dir 唯一出处
- [x] `grep -rn "resolve_topic_context" src tests` 的返回值断言无 `is None`（no-topic 断言全改 `key == ""`）
- [x] CONTEXT.md 两处更新到位

## 实施提示词（新会话用）

```
工单：.scratch/architecture-deepening-v5/issues/02-topic-entry-seam.md（架构深化 v5：赛题入口单一接缝，候选 5）

先读工单全文，按 1-6 节执行。独立 worktree（勿在主检出改）：
git worktree add ../firstep-v5-02 main

1. generator.resolve_topic_context 改永远返回 TopicContext（删 None 分支，no-topic 形 = key="" 哨兵 + 全模块摘要 + 空关联 + 空集回读器）
2. webapp：删 _topic_library_dir/_reference_dir 与 (TopicContext|None, str) 元组 helper，建 _assemble_topic_context(context, topic_id, problem_text, llm) 单值 helper；三路由改调它（recommend/skeleton 传 _llm(context)，generate 传 None）；`if topic is not None:` 改 `if topic.key:`；recommend no-topic 内联装配删除；generate 直调删除
3. config.py 加 topic_library_dir/reference_library_dir 两个纯函数；webapp helper 与 test_webapp._wire_material_libraries 改消费 config（测试手抄消失）
4. webapp 的 build_manifest_summaries/list_modules import 删除（grep 零残留）
5. 测试：test_generator no-topic 断言 None → key=="" + 空集 reader 形状；test_webapp 原样过；新增结构测试（工单 5 节）
6. CONTEXT.md 按工单 6 节更新
7. 全量 pytest 绿 + mypy 干净 + 验收全勾后提交（refactor 一条 + docs 一条，风格照仓库）→ PR base 指 main

注意：编辑前先确认 cwd 在 worktree；勿串行做别的工单。
```

## Comments

（2026-08-09 立项，候选 5（用户委托选型）。设计决策：D1 no-topic 也产 TopicContext（key="" 哨兵）——路由零 fallback，装配唯一出处成真；D2 helper 收口三路由、元组坍缩单值；D3 布局推导归 config.py（docstring 明言的"将来加配置项只改这一处"就是 config 层）；D4 行为零变化、generate 保持服务端重算（客户端回传值不可信）。候选 2（build_manifest_summaries 归 manifest.py）留待下轮。）

（2026-08-09 实施，PR #19。验收 grep 的 list_modules 项按意图修正：/api/modules 浏览路由合法消费 library.list_modules——那是浏览、非装配（test_webapp 大量用例覆盖，"原样过"要求它工作），build_manifest_summaries 零残留达成；结构测试明示该边界（webapp 无 build_manifest_summaries 属性、无 _topic_library_dir/_reference_dir 私有委托）。基线 801 → 803 绿 + mypy 干净。）
