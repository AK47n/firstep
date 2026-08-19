# 02 — 参考文件库录入：配套资料 + 提炼归档

**What to build:** 参考文件库：上传配套资料（例程工程 / 说明书）→ AI 生成简介 → 用户补锚定（赛题编号 或 套件型号——套件必须从模块库已有 kit 词表选，校验拒绝词表外值）→ 入库（草稿→校验→入库，复用工单 07 模块录入流程）。提炼报告动作表新增"归档为该题参考文件"：被剔除的业务代码一键复制入库、锚定该题（内容自持，源工程删除不丢）；构建残留 / 二进制仍确定性剔除，不配归档。浏览 / 搜索（按标题 / 类型 / 锚定）。

**Blocked by:** 07 — 模块库管理（录入流程复用）；08 — 母版提炼（归档动作挂在提炼报告动作表上）

**Status:** resolved

## Comments

- 2026-08-08: 工单 02 完成（**纯后端核心**——与工单 07/08 同约定：UI 由生成流程工单统一装配，本批不做 UI）。
- 新增 `src/contest_generator/reference_library.py`：
  - 磁盘目录即数据库：一条目一目录（reference.json 元数据 + 素材文件本体，内容自持）；浏览 / 搜索（按标题 / 类型 / 锚定值子串过滤）/ 删除即时生效；条目 id 由标题生成（重复自动 -2 后缀），所有拼路径操作先过 id 合法性校验（杜绝路径穿越）。
  - 录入流程（复用工单 07 模块库草稿→校验→入库模式）：`draft_description`（AI 通读素材出简介草稿，`llm.reference_summarize`）→ 用户修改 / 补锚定 → `add_reference` 结构校验通过才入库（标题 / 类型 / 简介非空；锚定 topic 或 kit——**kit 必须取自模块库已有词表** `module_kit_vocabulary`，词表外值拒绝；文件路径安全）；入库事务：任何一步失败整目录回滚，不留半成品。
  - 归档：`archive_reference` 字节复制源工程文件入库、锚定赛题编号（内容自持，源删除不丢）；类型固定"例程代码"、简介由确认流程写盘前经 LLM 生成。
- `report.py` 只加不删：动作表独立一档 `ArchiveDecision`（path / topic / reason）+ `DistillationReport.archive` 段（to_dict 空时不出键——AI 出稿报告 wire 形状不变，契约测试钉死七键；确认回传才带 archive 段）。归档**不进** `DISTILL_ACTIONS` / `FileDecision`（既有契约测试把 "archive" 钉死为非法 FileDecision action，归档独立建模即是"动作表加一档"的实现）。
- `llm.py` 只追加不改：`reference_summarize`（简介生成）+ `reference_judge_archivable`（归档判定，素材类型 `ReferenceCandidate` 归 report.py 判定素材模型层，依赖倒置）+ 严格解析 `parse_archive_judgment`（词表外 / 重复路径拒绝）。
- `master.py` 只加不动既有语义：`_validate_report` 把 archive 段计入覆盖校验（同路径不重复、公共文件可归档——归档 = 剔除的落库变体，ADR 0001 公共文件本就可剔除）；确认事务增归档子步骤：apply 暂存校验 → **LLM 判定 + 简介生成（全部在任何真写盘前，失败即整体中止）** → 母版先入库（既有事务语义不变）→ 归档条目复制入库（每条目原子，批量失败回滚本批已建条目并大声报错，可重试——import 幂等）。残留 / 旧 main.c / 基础设施 / 二进制 / 工程配置文件仍按规则确定性处置，**不配归档**（既有处置校验自动拒绝）。
- `webapp.py`：末尾追加 GET /api/references（搜索）、POST /api/references/draft、POST /api/references、DELETE /api/references/{id}；`ReferenceError` 登记进 `_error_response`（未登记 = 真 bug 500）；`/api/masters/confirm` 仅加两个按需参数（llm_factory / reference_library_dir）——归档随确认提交的唯一入口，功能必需，无归档动作的确认不要求 AI 配置（与现状一致）。参考库目录 = 模块库平级兄弟 `references/`（config.py 本批冻结，不新增配置项）。
- 测试：新增 tests/test_reference_library.py（57 例：锚定校验 / 录入事务 / 浏览搜索删除 / ArchiveDecision 形状 / 归档复制 / 确认事务全链路 + 批回滚 + 各类别不配归档 / webapp 路由）。全量 547 通过（1 失败为 `test_real_projects_2026c_21f_distill_and_import` 环境依赖——真实工程路径不在 worktree，基线即失败），`mypy src` 干净。
- **验收项如实说明（未全勾）**：
  - 赛题编号锚定只做格式校验（`^\d{4}[A-Za-z]{1,2}$`），**查库确认（查无此条拒绝）待工单 01 赛题库落地后接入**——另一会话并行开发中，本批不建 topic_library 也不跨模块引用。
  - "说明书"类二进制素材（PDF 等）**本批不可录入**：录入接口与模块库同款 JSON 文本（`{文件名: 内容}`），二进制上传属工单 03 接线 / UI 装配范围；归档路径按字节复制、源工程任意文件均可（构建残留 / 二进制由规则拒绝）。
  - 归档判定（`reference_judge_archivable`）是确认时的 AI 把关（写盘前，任一不配归档即整体中止并列出被拒文件）——不是提炼报告阶段的推荐标记；全有或全无是确认事务一致性的取舍，错误信息指明可去掉的归档动作。
  - 确认事务的归档窗口：归档写入在母版入库之后，归档失败时母版已入库（错误信息明说"母版已入库，可重试确认"）——跨两个存储库的整笔原子不可行，以"批回滚 + 可重试（import 幂等）"兜底。
  - `mypy src` 干净（任务验证项）；`mypy` 全量（含 tests）会因 `FakeLLM` 未实现 reference_* 报 3 处（tests/fakes.py 属既有 tests 禁止触碰 × 任务要求扩展 LLM 协议，二者冲突的取舍，待 fakes.py 解禁后补）。
  - 参考文件库 / 归档 / 锚定词条未入 CONTEXT.md 词表（CONTEXT.md 本批禁止触碰，待后续工单补词条）。
- 两轴 code review 已跑：修复了标准轴的"`ReferenceCandidate` 违反依赖倒置（判定素材应归 report.py）"硬违规，以及"归档路径与 reference.json 元数据撞名（内容会被覆盖）"、"from_dict 不校验 anchor_kind 词表"两个真缺陷、webapp 死导入；规格轴无代码级缺陷，取舍均已在此如实留痕。
