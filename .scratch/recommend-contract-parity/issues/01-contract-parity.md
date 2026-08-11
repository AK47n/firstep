# 01 — 推荐请求契约双客户端对偶（CLI 补 reference_ids + 对偶测试）

**What to build:** /api/recommend 请求契约的浏览器前端与 CLI 验收脚本当前已漂移——reference_ids 前端发、CLI 不发（35ed61e platform 漂移的同款机制，那次是真机流程从未触发平台过滤的根因）。给 CLI 补 reference_ids 支持、payload 组装提成纯函数，加对偶测试强制字段集与事件词表一致，真机验收覆盖参考注入路径。

**Status:** drafted（2026-08-11，主会话已核实现状，待用户开新终端执行）

## 现状（已核实）

- 契约（webapp.py:575-582）：problem_text（必填）/ topic_id（可选）/ reference_ids（可选 list[str]，缺省空 = 现状兼容，手动准入经 selection.manual_reference_admission，幻觉 / 重复 id 大声失败）/ platform（可选，空 = 不过滤）/ clarifications（可选 [{question, answer}]）。
- 前端 index.html:916 发全部 5 字段（selectedReferenceIds 恒发）；CLI generate_check.py:261-265 只发 problem_text + platform（恒发）+ 条件 topic_id（topic 模式）/ clarifications（非空）——**无 reference_ids**，真机验收永不覆盖参考注入路径（锚定命中 / 手动选 / 两级注入 / done 的 references 透明闭环）。
- CLI 事件处理（:196-230）：round / converged / done / question / error 五事件；events.py:28-37 EVENT_* 是 Python 侧词表单源；JS 侧 index.html:851-852 有"词表镜像 events.py 改词表须同步"注释，CLI 是第三份静默拷贝、无任何注释与测试。
- generate_check.py 位置：.scratch/real-run/（gitignore 内但被 force-tracked）；tests/ 无任何测试 import 它。
- 35ed61e 实证：platform 字段前端先有、CLI 后补，补丁同时改 index.html + generate_check.py——加字段要手同步 3 处（webapp 校验 + 前端 + CLI）且无强制，本次把强制补上。

## 实施

1. **generate_check.py**：
   a. payload 组装提成纯函数 `build_recommend_payload(problem_text, *, platform=PLATFORM, topic_id=None, clarify_hist=(), reference_ids=()) -> dict`——字段规则与现状一致（topic_id 仅 topic 模式、clarifications 非空才发、reference_ids 非空才发）；check_topic 内循环（:261-265）改用之。
   b. CLI 加 `--reference-ids <id1,id2,...>`（逗号分隔），透传进 build_recommend_payload；help 文案注明"参考注入真机验证（前端同款语义：锚定命中 ∪ 手动选）"。
   c. 事件分支（:218-227）补镜像注释：events.py 词表单源，改词表须同步（JS 侧同款）。
2. **新测试 tests/test_generate_check_contract.py**（importlib 从 .scratch/real-run/generate_check.py 加载模块）：
   a. 全字段对偶：全输入（topic_id + clarify_hist + reference_ids 都传）时 payload 键 == {problem_text, topic_id, reference_ids, platform, clarifications} 恰五字段（新增契约字段时此处红，注释指向 webapp.py:575-582）；缺省输入 = 现状两键（problem_text + platform，向后兼容语义不变）。
   b. 事件词表对偶：generate_check 处理的 event 名集合 == {EVENT_ROUND, EVENT_CONVERGED, EVENT_DONE, EVENT_QUESTION, EVENT_ERROR}（import events.py 断言，改词表忘改 CLI 即红）。
   c. 注释常量：测试文件顶部写契约五字段清单常量 + 指向 webapp.py:575-582 的同步注释。
3. index.html 不动（已在正确状态）。

## 验收

- `python -m pytest` 全绿 + `mypy src` 干净（generate_check 在 mypy 范围外则注明）。
- 对偶测试可证伪：临时删掉 CLI 的 reference_ids 透传 → 测试红。
- 真机：8001 起服务，`python .scratch/real-run/generate_check.py --topic-file <题面.md> --reference-ids <真实条目id>` 跑通，done payload 带 references（auto/manual 标注与 platform）；`--platform mspm0` 与既有 --clarify / --drop / --add 路径照旧。

## 文件边界

`.scratch/real-run/generate_check.py`、`tests/test_generate_check_contract.py`

**明确不动的：** webapp.py（契约本工单不改，只加 CLI 侧能力 + 测试强制）；index.html；events.py 语义；generate_check 的产物检查 / 编译校验 / 门禁逻辑；模块库与磁盘内容。
