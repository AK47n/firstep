# 07 — 模块库管理（AI 录入/校验 + 模块页 UI）

**What to build:** 用户打开模块库页面：浏览全部模块；新建模块——拖入 `.c/.h`，AI 通读代码生成简介草稿，用户补充，AI 校验描述与实际代码一致、不一致时提示纠正；可编辑、删除；一个模块可维护多个平台的代码版本。

**Blocked by:** 01 — 生成器核心骨架 + fixture 测试基座；04 — LLM 赛题→模块选择 + 依赖解析 + 配置

**Status:** done

- [x] 模块列表页：浏览、编辑、删除，即时生效
- [x] 添加模块：拖入文件 → AI 生成简介草稿 → 用户可改 → AI 一致性校验 → 不一致时明确提示，纠正后才允许入库
- [x] 多平台版本：同一模块增删各平台版本文件及 manifest 条目
- [x] 入库落盘为库目录结构（模块文件夹 + manifest），删除即移除
- [x] 假 LLM 下测试全绿：校验流程（一致 / 不一致）两条路径

## Comments

- 2026-08-05: 工单 07 完成（**纯后端核心**——用户确认：页面 / 拖放交互由 09 端到端装配统一做，与本批 08 的设置页同理；上面前两项的"列表页 / 拖入"在本工单以模块库服务兑现核心行为，UI 层未做、不假装完成）。
- 新增 `src/contest_generator/library.py`：
  - 浏览/编辑/删除即时落盘生效：`list_modules` / `get_module` / `delete_module` / `save_manifest`（结构字段编辑；简介编辑走 `update_module_description`）；
  - AI 录入流程：`draft_description`（草稿）→ 用户修改 → `validate_description` / `add_module`（一致性校验通过才入库；不一致抛 `LibraryError` 带差异说明，且不落盘）；
  - `update_module_description`：编辑简介先经 AI 校验再写回（校验视角 = 模块全部平台版本引用的文件），兑现 spec US 15"库的说明保持可信"；
  - 多平台版本：`add_platform_files` / `remove_platform_files`（最后一个文件删除后平台条目移除；双平台共享文件内容一致只写一份、内容冲突拒绝、删除时仍被其他平台引用的文件保留——假库 dht11 就是共享头文件结构，不加这套就没法正确加第二平台版本）。
- `llm.py` 协议补齐第三职责"简介生成与校验"：`validate_module_description`（DeepSeek json_mode 实现）+ `ValidationResult` + 严格解析 `parse_validation_result`（畸形输出抛 `LLMError`，宁可不放行也不带病入库）。
- 安全与原子性：所有从 slug 拼路径的操作先过 `_validate_slug`，杜绝 `../` 路径穿越逃出库目录（spec"磁盘目录即数据库"）；加版本前预检内容冲突再写盘、删除先改 manifest 再删实体，不留半成品。
- `FakeLLM` 增加 summary / validation 构造参数与调用记录（沿用 main_skeleton 的注入模式），既有用例不受影响。
- 测试：新增 tests/test_library.py（47 例），test_llm.py 补校验用例（共 25 例）；全量 192 通过，mypy 干净。
- 两轴 code review 已跑：修复了规格轴指出的"编辑简介绕过 AI 校验"（新增 update_module_description）与"slug 路径穿越"，以及标准轴的错误契约、重复代码、fixture 复用问题。
