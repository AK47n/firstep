# 03 — 生成接线：历史赛题入口 + 参考文件两级注入

**What to build:** 生成接线：生成入口支持选历史赛题编号（带出题面 + 关联素材 + 该题专用模块）；粘贴题面中出现编号时同样可认（AI 理解编号）。选模块阶段两级注入参考文件：候选清单带"该赛题/套件关联的参考文件（标题 + 一句话简介）" → LLM 判断需要时取全文；长 PDF 题面全文只在选了该赛题时进上下文。骨架生成阶段暂不注入参考文件（等真实用例再评估）。

**Blocked by:** 01 — 赛题库录入；02 — 参考文件库；04 — LLM 赛题→模块选择

**Status:** resolved

## Comments

- 2026-08-08: 工单 03 完成（后端接线；端到端 UI 由生成流程工单统一装配，spec Out of Scope，不假装完成）。
- 四处边界落地（消费接口只读，库本体未触碰）：
  - `selection.py`：`associated_references`（候选清单的参考段——锚定赛题编号或**候选模块 kit 词表**，id 去重排序；候选 = 模块库全量，该题没有专用模块时套件锚定的参考文件仍进清单——规格轴评审 c2 修复）+ `reference_suggestions`（清单段形状：标题 + 一句话简介）+ `read_reference_fulltext`（两级注入第二级素材：带文件名标注拼接；二进制素材跳过并标注、缺失 / 越界路径大声失败——宁可大声失败也不带病进上下文）。
  - `llm.py`：选模块 prompt 扩展——两级注入协议：先清单，LLM 在输出 `references` 数组点名想读全文的，系统取全文后带全文重选定稿（**恰好两级**：第二级仍点名不再注入——两级即协议全部）；全文走统一截断（TRUNCATION_NOTICE）；`references` 输出严格解析（清单外 / 重复 / 没给清单却报 = 幻觉，大声失败）；`select_modules` 协议扩参（references / reference_fulltexts 缺省——无清单时提示词与输出契约与既有完全一致，fakes.py 只读兼容，`select_modules_two_level` 无清单按旧签名调用）。
  - `generator.py`：`TopicContext` + `resolve_topic_context`（生成入口素材装配：显式 topic_key 查无此条大声报错 vs 粘贴题面 AI 自动识别尽力而为；长 PDF 题面全文只在选了该题时进上下文）；`generate_project` 带 topic_key 自动并入该题专用模块（复用"XX 题专用"标注自动发现，生成物与手选等价）；查库 + 关联发现抽 `_resolve_topic_entry`、专用模块并入抽 `prepend_related_modules`（标准轴评审去重，两处调用同款）。
  - `webapp.py`：生成请求加 topic_id 参数——recommend / skeleton / generate 三端点同入口（工单要求"生成请求加"，recommend / skeleton 是题面全文进上下文的必经处，一并接上；骨架阶段不注入参考文件，spec Out of Scope）；recommend 响应带 topic_id + related_modules（UI 透传该题专用模块，合理管线扩展）。
- 测试：新增 39 例（假 LLM 子类扩展协议——TopicAwareLLM / _RecordingSelectLLM，fakes.py 只读；新假件独立成 tests/generate_wiring_fakes.py，素材区用真实入库函数构造 confirm_topics / add_reference）。全量 640 通过 + 1 已知环境失败（`test_real_projects_2026c_21f_distill_and_import`——Desktop/2026C ALX 素材污染，基线即失败，非本工单回归），mypy src 干净。
- 两轴 code review 已跑并修复：规格轴——"套件关联面偏窄（无专用模块时套件参考文件缺失）"已修复（候选模块全量 kit）；标准轴——重复合并形状抽 `prepend_related_modules`、查库 + 关联发现重复抽 `_resolve_topic_entry`、"空全文静默丢弃"改为嵌入空块（与截断契约一致）。评审期间发现测试体一度误落主检出（相对路径 + 工作目录在主检出），已还原主检出（git diff 验证与 HEAD 一致）并将测试体落回 worktree——修正前误跑的"绿"不含新测试，修正后 640 通过为真实全量。
- **验收项如实说明**：
  - 自动识别查无此条**静默降级**为刻意取舍：spec"查无此条时明确报错"针对编号解析服务（resolve_number，显式路径已遵守）；入口自动识别是尽力而为，硬失败会阻断纯粘贴题面主流程——取舍已在此留痕，若产品上要"识别到但库里没有就提示"，改 `resolve_topic_context` 自动分支一处即可。
  - 套件关联面 = 候选模块 kit 词表（模块库全量），宽于"该题专用模块"——spec"该赛题/套件关联"，相关性由 AI 在两级注入第一级判断。
  - LLM 实现没有 `topic_extract_number` 职责（既有假件）时自动识别跳过（getattr 探测），与 fakes.py 只读约定叠加的协议错位已文档化。
  - 粘贴题面自动识别每次 recommend 多一次 AI 提取调用（显式 topic_id 时不提取）；UI 可经 recommend 响应里的 topic_id 透传后续阶段，或让各端点自行再识别（两条路等价）。
