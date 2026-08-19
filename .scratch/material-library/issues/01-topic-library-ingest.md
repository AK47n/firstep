# 01 — 赛题库录入：长 PDF 拆条 + 编号解析

**What to build:** 赛题库：导入历年真题长 PDF → AI 拆条（年份 / 编号 / 题面全文）→ 用户逐条校对 → 确认入库（事务，与提炼确认同风格）。磁盘目录即数据库：一条目一目录，题面落 `.md`，原 PDF 保留在条目目录（AI 拆错可查原文）。提供编号解析服务（"2026C" → 题面），供生成入口与 AI 理解使用；条目锚定该题附带的完整程序（2026C 钥匙/锁两套的存放/引用方式）与关联模块（复用简介"XX 题专用"标注自动发现，不新造链接字段）。

**Blocked by:** 04 — LLM 赛题→模块选择；07 — 模块库管理（AI 录入/校验流程复用）

**Status:** resolved

## Comments

- 2026-08-08: 工单 01 完成（**后端核心先行**——spec Out of Scope 明确 UI 本批不做，端到端 UI 由生成流程工单统一装配，不假装完成）。
- 新增 `src/contest_generator/topic_library.py`：
  - 确认入库事务 `confirm_topics`：一条目一目录（目录名 = 编号），题面全文落 `topic.md`、原 PDF 复制进条目目录（AI 拆错可查原文）、`manifest.json` 记录年份 / 编号 / 题面文件名 / 原 PDF 文件名 / 附带程序目录；全部校验（至少一道题 / 编号格式与不重复 / 题面非空 / 原 PDF 存在 / 附带程序目录存在且非空 / 编号未被占用）都在落盘前，落盘中途失败清理全部已建条目目录（monkeypatch 模拟中途写失败断言回滚）；
  - 编号解析 `resolve_number`："2026C" → 题面全文，查无此条明确报错（不猜测编造）；编号格式 `^\d{4}[A-Z]$`（4 位年份 + 单个大写字母）；
  - 关联模块 `discover_related_modules`：复用模块简介"XX 题专用"标注自动发现（读时计算、不新造链接字段），模块清单走 `library.list_modules`（损坏 manifest 大声失败，与模块库浏览同哲学）。
- `llm.py` 协议追加赛题库两职责（第五职责，命名前缀 `topic_*`，不改任何既有方法）：`topic_split_topics`（长 PDF 全文 → 拆条，超长走统一截断 + TRUNCATION_NOTICE——**遗留：历年真题整本 PDF 超长时只拆到截断处，分批拆条等真实用例评估**）+ `topic_extract_number`（从文本提取编号）；严格解析 `parse_topic_split` / `parse_topic_number`（畸形 / 重复 / 空拆条抛 LLMError，宁可大声失败）；`validate_topic_key` 为编号格式与文案唯一出处（拆条 / 编号提取 / 入库校验共用）。
- `webapp.py` 追加路由：`POST /api/topics/split`（上传 PDF → 抽取 → 拆条）、`POST /api/topics/confirm`（multipart：pdf + payload Form JSON）、`POST /api/topics/extract-number`、`GET /api/topics/{key}`（编号解析 + 关联模块）；`TopicError` 已登记错误映射（未登记 = 真 bug → 500 大声失败）。赛题库目录约定 = 模块库同级 `topics/`（config.py 在本工单禁止名单内、无独立配置字段；将来加配置项只改 `_topic_library_dir` 一处）。
- 测试：新增 tests/test_topic_library.py（52 例；FakeLLM 子类 FakeTopicLLM 补 topic_* 职责，fakes.py 只读）；全量 544 通过（`test_real_projects_2026c_21f_distill_and_import` 为基线既有环境失败：真实 Desktop 工程 .uvprojx 引用 67 个磁盘上不存在的源文件，main 上同样失败，与本次无关），mypy src 干净。
- 两轴 code review 已跑，修复：规格轴——"空拆条放行"改大声失败、"TOPIC_KEY_PATTERN 过宽"收紧为单大写字母（大小写不敏感文件系统上多字母 / 小写编号跨平台行为不一致）、"中途失败回滚零测试"补用例、"program_dirs 空串"拒绝；标准轴——"编号校验文案 4 处复制"抽 `validate_topic_key`、"直通包装"删除（split_topics / extract_topic_number / get_topic，webapp 直调 LLM 与 select_modules 同款）、"模块库遍历"改走 `list_modules`、"临时文件样板重复"抽 `_save_upload`。规格轴另指出 GET /api/topics 浏览端点越界（spec 的"浏览 / 搜索"属参考文件库段）——已删除，赛题库浏览待 UI 装配工单按参考库同款实现。
- **CONTEXT.md 词表未登记赛题库概念**（赛题库 / 编号解析 / TopicEntry / 附带程序）：CONTEXT.md 在本工单禁止触碰名单内，未改，建议主会话或后续工单补登记。
- spec.md / ADR 0006 未随本 PR 提交（主检出未跟踪文件、禁止触碰名单）——代码引用为文档指针，需随主会话或后续提交落盘。
- 附带程序的存放 / 引用方式本批采用引用（manifest 存绝对路径，不复制）；若真实使用发现源工程删除导致锚定悬空，再评估改复制入库（与参考文件库归档同款"内容自持"）。
