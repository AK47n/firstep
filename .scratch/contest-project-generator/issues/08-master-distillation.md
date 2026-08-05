# 08 — 母版提炼 + 设置页 UI

**What to build:** 用户导入多个同平台旧工程，AI 提炼出综合母版：先出报告（保留 / 合并 / 剔除清单），用户确认后才生成母版入库；每个平台一个母版，设置页统一管理。

**Blocked by:** 01 — 生成器核心骨架 + fixture 测试基座；04 — LLM 赛题→模块选择 + 依赖解析 + 配置

**Status:** done

- [x] 导入多个同平台工程 → 结构对比 + 配置对比 → AI 判定公共骨架与项目残留
- [x] 提炼报告（保留 / 合并 / 剔除清单）展示给用户，确认后才生成母版
- [x] 每平台独立母版；入库时做结构分析；可更换、删除
- [x] 设置页：母版管理 + AI API 配置界面
- [x] 假 LLM 下测试全绿：报告结构、确认流程

## Comments

- 2026-08-05: 工单 08 完成（**纯后端核心**——与工单 07 同约定：设置页 UI 由 09 端到端装配统一做，本工单以母版库服务 + 既有 AI API 配置（工单 04 的 config.py）兑现核心行为，UI 层未做、不假装完成）。
- 新增 `src/contest_generator/master.py`：
  - 导入与对比：`scan_project`（平台检测：.uvprojx → stm32 / .cproject → mspm0，含糊或缺失明确报错；文件清单含内容哈希，.git / Debug / Release 顶级目录不进清单；设备 / include path / 编译宏配置摘要喂给 AI）、`compare_projects`（公共 / 冲突 / 独有三类 + by_path 来源记录；平台必须一致、工程名不得重复）。
  - AI 提炼：`distill_master` → `assemble_report`（公共文件确定保留，冲突 + 独有文件交给 LLM 逐条判定；**冲突文件必须 merge 指定来源工程**——keep 没有"取哪份内容"的信息，选了 keep 会在落盘时静默取第一个工程；merge 来源必须是导入工程且真实含该文件。这些在确认前就拦住，兑现"不带病进入确认流程"）。LLM 输出经 `parse_distillation_report` 严格校验（action 词表 / merge 来源 / 路径重复，畸形抛 LLMError）。
  - 确认流程：`apply_distillation`（按报告落盘母版候选：keep 取第一个含该文件的工程、merge 取指定来源、exclude 跳过；报告必须恰好覆盖判定范围，传错对比结果直接拒绝；落盘中途失败不留半成品）。
  - 母版库：每平台一个母版。`import_master`（先结构分析——平台配置文件缺失拒绝入库，构建产物目录进警告；旧母版先挪备份再原子换入，任意失败点回滚，既有母版完好）、`list_masters` / `get_master` / `delete_master`（可更换、删除；元数据 `<platform>.json` 放母版目录外平级——母版目录会被生成器整体复制，内部带 json 会污染生成的工程）。所有拼路径操作先过平台名合法性校验，杜绝路径穿越。
- `llm.py` 协议补齐第四职责"母版提炼判定"：`distill_master`（DeepSeek json_mode 实现）+ `FileDecision` + `parse_distillation_report`。
- 测试：新增 tests/test_master.py（50 例：扫描 / 对比 / 报告结构 / 确认流程 / 结构分析 / 库生命周期 / 端到端），test_llm.py 补提炼判定用例（共 36 例）；全量 247 通过，mypy 干净。
- 两轴 code review 已跑：修复了规格轴的"冲突文件静默取第一个工程"（强制 merge）、"merge 来源在确认后才校验"（提前到报告拼装）、"import 非原子"（备份换入 + 回滚），以及标准轴的工程名重复静默合并、FileDecision/FileDisposition 同形双类型、忽略词表重复、命名问题。
- 验收点（RUNBOOK）：提炼出的母版首次生成后，需在 IDE 里编译一次（flash 配置等细节）——手工验证，AI 替不了。
