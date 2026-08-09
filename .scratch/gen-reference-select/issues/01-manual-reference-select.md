# 01 — 生成时手动选参考资料（手动 = 全文直读，锚定 = 两级照旧）

**What to build:** 现状生成时参考资料注入完全后端自动（锚定过滤 + 两级注入），前端零展示零干预；6 批里 4 批锚定 `none`（视觉 / 真题 / k230 / MSPM0_MOTOR），生成时永远进不了上下文，用户想用也用不上。本工单在生成流程加一步"手动选参考资料"：用户勾选批次 → 手动选条目**直接全文**喂进第一轮 prompt（强制），锚定命中的仍走两级（清单 → 模型点名 → 回读）。追加语义：锚定命中照旧自动进，手动选是补充；用户不碰 = 现状零变化。

**Blocked by:** 无

**Status:** resolved

## 现状事实（实施前必读）

- 两级注入链路：`selection.associated_references`（selection.py:176，锚定判据 = topic_key ∪ `manifest.collect_kits` 词表）→ `reference_suggestions`（selection.py:201，每条 id + 标题 + 一句话简介）→ 装配 `generator.resolve_topic_context`（generator.py:140-195，TopicContext :117-137 含 suggestions / read_fulltext 闭包 / problem_text）→ 清单段进 `_selection_user_prompt`（llm.py:1254-1298，清单行 :1265-1274）→ 模型输出 `references: [id]` → `_parse_reference_ids` 严格校验（selection.py:515-533，清单外 id = 幻觉大声失败）→ `read_fulltext` 回读点名条目全文（reference_library.py:276-300）→ 带全文再调一轮 `select_modules`（llm.py:664-666，全文嵌入 :1275-1285）。单条全文截断 `EMBEDDED_CONTENT_CAP = 4000`（llm.py:187，`_truncate_content` :216-230）。
- no-topic 形：`_no_topic_context`（generator.py:198-216）suggestions 恒空、read_fulltext 恒抛（零参考）。
- 路由：`POST /api/recommend`（webapp.py:455-521，SSE）→ `resolve_topic_context`（webapp.py:208-228）→ `select_modules_convergent`（selection.py:617-689，收敛上限 4 轮）。
- 库现状：`library/references/` 6 批——`topic=2026H` / `kit=最新ALX-AOA-FIT跟随套件开发资料` / 其余 4 批 `none`（已逐批核 reference.json）。
- 前端：六步卡片（index.html:168-253：1 赛题原文 / 2 目标平台 / 3 AI 推荐模块 / 4 模块清单与平台警告 / 5 main.c 骨架 / 6 输出目录并生成），无任何参考资料展示/选择入口；参考库 tab（index.html:297-350）。`GET /api/references`（webapp.py:868-881）返回 `entry.to_dict()` 全量（含 anchor 字段，按 title/type/anchor 子串过滤）——前端复用，零新接口。
- 架构意图：`docs/adr/0006-material-library.md` 记"两级 vs 全量——两级"定案；CONTEXT.md 行 22 参考文件库词条。本工单不推翻两级，是加"用户显式点名"通道。

## 需求

1. **契约**：`POST /api/recommend` 请求体加可选 `reference_ids: list[str]`（缺省 / 空数组 = 现状完全兼容）。手动选条目须真实存在于参考库（不存在 / 格式非法 → 400 大声失败，对齐 `_parse_reference_ids` 严格精神；新异常类登记 errors.py `error_to_http` 表，结构测试防漏登）。
2. **准入 = 追加（并集）**：最终参考清单 = 锚定命中（现有 `associated_references` 逻辑不动）∪ 手动选条目；锚定命中照旧自动进（追加语义，覆盖与否的讨论见 Comments）。去重（同一条目既锚定命中又被手动选，只出现一次）。
3. **手动 = 全文直读（强制）**：手动选条目直接全文拼进第一轮 prompt（复用 `_truncate_content` / `EMBEDDED_CONTENT_CAP` 4000 字符/条截断，`library.file_label` 标签格式），清单段标注来源（手动 vs 自动）；锚定条目维持两级（模型点名才回读）。手动条目已全文、无需模型点名，点名机制整体不动。预算 = 手动 N×4000 + 锚定点名 ≤ 1×4000，可控。
4. **no-topic 生效**：`_no_topic_context` 接 `reference_ids`——suggestions = 手动选条目（全文直读），read_fulltext 仍恒抛（手动条目已全文，无需回读）；未选 = 现行为（零参考）。这是锚定 none 批次唯一可用场景，必须通。
5. **UI：六步卡片插新第 3 步"参考资料（可选）"**（第 2 步平台之后、AI 推荐之前）：`GET /api/references` 全量列表，每条 = 勾选框 + 标题 + 锚定标注（`赛题 2026H 关联` / `套件 xxx 关联` / `未关联`，前端本地按条目 anchor 字段标注）；说明文案"勾选 = 手动指定作学习素材注入；赛题 / 套件自动关联的批次无需勾选也会注入"；勾选结果随 recommend 请求发送。初始勾选 = 空（用户已输入赛题编号时可本地比对 topic 锚定预勾，不强求）。
6. **透明闭环**：recommend SSE 结果（最后一个事件携带完整结果）带最终参考清单（含来源标注 手动 / 自动），前端新步骤旁或模块清单步骤展示"本次注入的参考资料"。
7. **回归**：不传 `reference_ids` 时链路与 prompt 逐字节等价现状（结构测试 / 既有 prompt 形状测试不能碎）；skeleton / generate 路由不碰（骨架阶段不注入参考文件是既有定案，webapp.py:544 docstring）。
8. **CONTEXT.md**：参考文件库词条补"手动指定 = 追加准入 + 全文直读，锚定两级照旧"一句。

## 文件边界

- `src/contest_generator/selection.py`：手动准入（并集 + 存在性校验 + 去重）；`select_modules_convergent` 传参把手动条目带进 TopicContext / prompt
- `src/contest_generator/generator.py`：`resolve_topic_context` / `_no_topic_context` 接 `reference_ids`；TopicContext 增加手动条目（或强制全文标记）字段
- `src/contest_generator/llm.py`：`_selection_user_prompt` 手动全文段（复用截断与 file_label）；清单段来源标注
- `src/contest_generator/webapp.py`：`/api/recommend` 契约（解析 + 校验 reference_ids）；结果携带最终参考清单
- `src/contest_generator/errors.py`：新异常登记 `error_to_http`（结构测试反射防漏登）
- `src/contest_generator/static/index.html`：新第 3 步（勾选面板 + 锚定标注 + 结果展示）
- `tests/`：selection（并集准入 / 幻觉 id 拒绝 / 去重 / 手动全文直读标记）、generator（no-topic + 手动）、webapp（契约 / 缺省兼容）、llm（prompt 形状：手动全文段在、锚定清单行在、不传时逐字等价）
- `CONTEXT.md`：词条补句
- **注意**：webapp.py 与 index.html 有在途未提交改动（git status M 两项），实施独立 worktree、独立 commit，不混批

## 验收

- [x] 全量测试绿（944）+ mypy src 干净（tests 侧回到基线 5 个存量错误，无新增）
- [x] 手动勾选 2026_06 视觉资料（锚定 none）+ 赛题 2026H：第一轮 prompt 含视觉全文段（4000 截断、file_label 标签）+ 2026H 清单行；模型点名 2026H → 第二轮回读全文（test_convergent_manual_and_anchored_fulltexts_coexist / test_select_prompt_embeds_manual_fulltexts_with_label / test_recommend_manual_reference_ids_fulltext_into_first_round）
- [x] no-topic（粘贴题面不选赛题）+ 手动勾选视觉资料：清单非空、全文直读；不勾 = 零参考（现行为）（test_resolve_topic_context_no_topic_manual_is_only_admission / test_recommend_no_topic_manual_reference_is_only_admission）
- [x] 不传 `reference_ids`：prompt 逐字节等价现状（回归测试）（test_select_prompt_without_manual_keeps_old_shape / test_recommend_without_reference_ids_keeps_old_behavior / 既有 old shape / old signature 测试不动全绿）
- [x] 幻觉 id / 不存在条目：400 大声失败（错误映射表已登记）（ManualReferenceError 入 errors.py 表 + 结构测试反射 + test_manual_reference_error_registered_as_400；webapp 装配点同步 400 起流前失败）
- [x] 同一批次既锚定命中又被手动选：清单只出现一次（test_resolve_topic_context_manual_overlapping_anchor_deduped / test_recommend_manual_overlapping_anchor_deduped）
- [x] 前端新步骤：列表全量展示、锚定标注正确、勾选随请求发送、结果展示最终参考清单（来源标注）（index.html 新第 3 步卡片，人工核对）
- [x] 独立 worktree + 独立 commit，工作区在途未提交改动不混入（worktree-reference-select 基于 main HEAD 创建）

## Comments

- 2026-08-09 立项（grilling 决策树，七问全按用户授权推荐落定）：① 动机 = A+B（让锚定 none 资料可用 + 透明可控）；② 粒度 = 条目（整批），批内文件粒度否（MOTOR 600+ C 文件不可解释）；③ 时机 = 生成前主动选（轮后确认留作将来增强，改动面大无真实用例）；④ 与锚定关系 = 追加并集（覆盖会让现有 2026H / ALX 关联退化，追加 = 用户不碰现状不变）；⑤ no-topic = 生效（锚定 none 批次唯一可用场景）；⑥ UI = 独立一步（初始勾选 = 锚定命中批次，可增删）；⑦ 全文策略 = 手动直读强制 / 锚定两级照旧（走两级模型可能不点名 → "选了怎么没用上"；N×4000 预算可控）。
- 实现细节修正：初始勾选原案"锚定命中全预勾"不可行——kit 锚定依赖候选模块（推荐后才知，时序上第 3 步在推荐前）。修正：初始勾选空（topic 锚定可本地预勾不强求），自动关联由后端追加语义保证（需求 2），透明性靠锚定标注（需求 5）+ 结果展示最终清单（需求 6）补足。取消"取消自动关联"能力，本次只做"增"（Q1-B 可控的"增"半轴）。
- 2026-08-09 实施（worktree-reference-select，944 绿 + mypy src 干净）：reference_ids 契约 = `_require_str_list` 复用（格式非法 400）；准入 = selection.manual_reference_admission（get_reference 校验，ReferenceError + StoreError 统一收口 ManualReferenceError——"幻觉 id" 含空格会先撞 _validate_entry_id 的 StoreError，单捕获 ReferenceError 会裸漏 500，实施中发现）；并集去重 = 装配点 anchored_only / manual_flagged / manual_extra 三组（重合条目标注 manual——全文已直读模型无需点名，注释修正原案"保留锚定位置标注 manual"）；手动全文 = 装配点 read_fulltext 一次读好进 TopicContext.manual_fulltexts（llm 协议第 5 参 manual_fulltexts，手动段复用 _truncate_content + file_label，每轮照带不丢）；no-topic 回读器覆盖手动条目 id（模型点名已全文条目不崩，读回同一全文无害——工单"仍恒抛"按"无两级注入"语义执行）；幻觉 400 = 装配点同步校验在起流前 → HTTP 400（非 SSE 流内 error，前端已兼容非 200 分支）；前端第 3 步卡片（勾选随请求发送，结果展示最终清单 + 来源 chip），初始勾选空。fakes.py FakeLLM 补协议第 5 参（协议契约变化时假件同步，a1ee97f 先例）。
