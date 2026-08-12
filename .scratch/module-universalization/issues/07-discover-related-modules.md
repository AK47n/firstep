# 07 — discover_related_modules 简介词发现机制与判据④冲突（定案：移除）

**What to build:** 工单 01 遗留提示①——`topic_library` 的关联模块发现机制（赛题库词条：关联模块可复用简介的"XX 题专用"标注自动发现）依赖简介里的题绑定标注。判据④ 起补录/编辑拒题绑定，新条目不再可能有题绑定标注 → 机制只对直写 manifest 的存量/手改条目生效，随 02~06 清理完毕即完全失效。

**Status:** decided（2026-08-12 主会话审视定案 ①，实施待新终端）

## 定案记录（2026-08-12 主会话审视，未走 grilling——证据已足）

- ① **移除机制**：✅ **定案**。关联发现本就与推荐链路重复（推荐 = 功能需求层 → 模块匹配，能力方向词驱动），发现机制是劣质副本。
- ② **换能力方向匹配**：❌ 否决——等于在 topic_library 再造半个推荐链路，职责重复。
- ③ **保留现状**：❌ 否决——为"直写 manifest 手改条目"的逃逸路径留 UI 列 + API 字段不值；ADR 0009 方向即消灭题绑定。

**审视事实（代码实测，修正原认知盲区）**：

1. **恒空已实证**：匹配规则 = `简介含题号 and 含"专用"`（topic_library.py `related_module_slugs`）；06 清理后 `find_topic_word_hits` 全库零命中 → 对任何 key 恒返回空。不是"随清理逐渐失效"，是已彻底失效。
2. **使用面横跨生成链路，不只题库 UI**：`generator.py:271` 历史赛题入口并入最终模块集（`prepend_related_modules`，webapp.py:619 编排同用）；`selection.py:885` 往推荐请求体附加 `related_modules`（契约字段，对偶测试强制）；webapp 2 路由 + index.html 表格列（1554/1566）+ 取题加载提示（724-726）。
3. **恒空尸体三层成本**：UI"关联模块"列恒"—"、推荐请求体恒空列表噪声（AI 每轮收到）、审查时每次解释。
4. **原文件边界错误**：只写了 topic_library.py + tests + CONTEXT.md，实际必须动 generator / selection / webapp / index.html + 契约测试，否则悬空引用。

## 实施（定案 ① 移除）

1. **topic_library.py**：删 `related_module_slugs` + `discover_related_modules` + 相关 docstring/注释。
2. **generator.py**：删 `TopicContext.related_modules` 字段（144）与 `related_module_slugs` 调用（271）、`prepend_related_modules`（341）与调用（408）；历史题入口不再并入"题专用模块"——设计意图（普适化后无题专用模块，推荐链路 AI 按题面能力推荐承担）。
3. **selection.py**：推荐请求体/响应删 `related_modules` 字段（845/885）+ 契约注释同步。
4. **webapp.py**：删 `discover_related_modules` import（92）与 2 路由调用（1061/1149）、`prepend_related_modules` import（44）与编排调用（619）+ 相关注释。
5. **static/index.html**：删表格"关联模块"列（1554/1566）+ 取题加载提示 related_modules 段（724-726）。
6. **tests**：test_topic_library.py 4 个 discover 用例删除；契约对偶测试同步（`related_modules` 移出请求体字段集强制）；test_autocommit.py 分类注册表删 `discover_related_modules` 条目（444）。
7. **CONTEXT.md**：赛题库词条删"关联模块自动发现"表述（或注明已移除）。

## 文件边界

- src/contest_generator/topic_library.py / generator.py / selection.py / webapp.py
- src/contest_generator/static/index.html
- tests/test_topic_library.py + 契约对偶测试 + tests/test_autocommit.py
- CONTEXT.md
- **不动**：library/modules/*、推荐链路本体（AI 收敛 + 能力方向匹配照常）、生成机制其余部分

## 验收

- [x] 决策定案记录在工单（2026-08-12 主会话审视，① 移除 / ②③ 否决）。
- [ ] 按定案实施，pytest 全绿 + mypy 干净。
- [ ] 零残留引用（grep `related_module|discover_related|prepend_related` 干净）。
- [ ] CONTEXT.md 词表同步。
- [ ] Status resolved。
