# 11 — instances 幻觉：非多实例模块被输出实例数组，靠一次重试自愈仍会烧调用

**要做什么：** 让「模型给**不支持多实例**的模块输出 `instances`」不再消耗一次重试调用
（当前靠 `DOMAIN_RETRY_LIMIT=1` 带理由重出一次自愈），并在重试也用尽时给出**可操作**的
终态指引（而不是只报「模块 X 不支持多实例」这一句内部事实）。

**被谁阻塞：** 无（前置 = 单 03 已 resolved：domain 分流 + 带理由重试机制已就位）。

**状态：** ready-for-agent

## 真机现场（两轮累计，逐字来自探针日志）

| 轮次 | 题 / 平台 | 现场 | 结局 |
|---|---|---|---|
| 第十七轮（单 03 真机验收） | 2026H / mspm0 | **3 条**：`模块 k230 不支持多实例，不能带 instances`（另有 xunji / ntb_time 同类） | 由 `DOMAIN_RETRY_LIMIT=1` 带理由重试**接住** → done |
| 第十七轮（单 03 真机验收） | 2022C / stm32 | **1 条**：`模块 pid 不支持多实例，不能带 instances` | 同上，接住 → done |
| 第十六轮（A8/C5 现场，单 03 工单表） | 2026H / mspm0 | `huidu` / `oled` 各 1 条 | 当时无重试 → 终态失败（该批 9 轮占 5 轮） |
| 第十六轮 | 2026C / stm32 | `k230` 1 条 | 同上 |
| 第十六轮 | 2026F / stm32 | `adc` 1 条 | 同上 |

累计出现过的违规模块：**k230 / xunji / ntb_time / huidu / oled / adc / pid**（全是
**单实例**模块）。证据：`.scratch/recommend-domain-reject/verify-17-recommend-*.txt`
的 `[PROBE16][域拒绝]` 行、`.scratch/real-run/verify-16-recent-workflows.json`
（`error_kind=domain` / `attempts=1`）。

## 根因（提示词已写硬约束，模型照样犯）

1. **校验点**：`selection._parse_model_instances`（`selection.py:1002`）——
   `if slug not in multi_instance: raise SelectionError(f"模块 {slug} 不支持多实例，不能带 instances")`。
   这是**唯一**拦截点，`multi_instance` 集合来自 `ManifestSummary`（同源能力清单）。
2. **提示词有约束但无效**：`llm._selection_user_prompt` 的多实例规则段（`llm.py:5351`）
   原文已写「instances 字段**只允许**出现在清单带「多实例」标注的模块条目上……未标注的
   模块输出 instances 会被系统**直接拒绝整轮结果**（模块 digit_uart 曾因此整轮失败）」
   ——**模型仍然犯**，说明「加一句警告」这条路已经走到头了，本单不能只是把语气加重。
3. **代价可量化**：一次违规 = 一次**分钟级**调用白花 + 一次重试（`DOMAIN_RETRY_LIMIT=1`
   已在单 03 计入预算口径）；两次都犯 = 终态失败，用户只看到「模块 X 不支持多实例」。

## 修复方向（实施会话定措辞，红证先行；**方向 ②③ 需先证 ①② 无效再动**）

1. **先说清"为什么"（诊断，不是改动）**：先复现模型到底输出了什么——
   - `{"instances": null}` 已在解析层归一为「无实例」（`_parse_model_instances` 注释：
     DeepSeek 常对非多实例模块补显式 `null`），**这条不算违规**；
   - 真违规的是**非空数组**（哪怕只有 1 个元素）。实施时先用探针把现场抓到的原始
     输出形态落盘（是 `[{...}]` 还是 `[]`？元素几个？）——**这是选方向的前提**：
     若现场全是「单元素数组」，则方向 ② 的成本几乎为零；若是多元素，方向 ② 需要更
     保守的收窄。
2. **确定性兜底（首选，与单 08 的 B1 同款思路：能做确定性对齐就不加模糊判断）**：
   在 `_parse_model_instances` 里，对**非多实例模块**的 `instances`：
   - **长度 = 1** 且该模块本就是单实例 → **确定性降级**为「无实例（默认单实例）」，
     并让调用方能拿到一条**可见的降级标注**（照 `OutOfLibrarySuggestion.degraded`
     先例：载荷带 `instances_degraded` / 或经 reason 文案点明）——语义上
     「1 个实例 = 默认单实例」是**等价**的，丢的不是信息，是一次无谓的拒绝；
   - **长度 ≥ 2** → 仍是真幻觉（用户真要多实例，而该模块没有能力），**保持拒收**
     并走现有带理由重试（`DOMAIN_FEEDBACK_SEGMENT` 已能接住）。
   判据口径与「宁严勿假绿」不冲突：单实例化是**恒等变换**，多实例化是**不可能的诉求**。
3. **重试反馈更具体（可与 ② 并行）**：`DOMAIN_FEEDBACK_SEGMENT` 现在带的是
   `SelectionError` 原文（「模块 oled 不支持多实例」）。若 ② 落地，剩下的违规天然只剩
   「要 2 个以上但没能力」这类，反馈段可点明**可选的替代**（如「删掉 instances 用默认
   单实例，或改选支持多实例的模块」），把「一句内部事实」变成「怎么改」。
4. **提示词不动（本轮默认）**：多实例规则段已含硬约束与反例（`digit_uart` 整轮失败），
   再加字数的收益已被现场否定；若要动，须先证 ② 落地后仍有残余违规。

## 文件边界

- `src/contest_generator/selection.py`（`_parse_model_instances` 判决 + 降级标注透传）
- `src/contest_generator/llm.py`（**仅**当采纳方向 ③：`DOMAIN_FEEDBACK_SEGMENT` 文案）
- `tests/test_selection.py`（解析判决：单元素降级 / 多元素仍拒收 / `null` 与 `[]` 现状不变）
- `tests/test_llm.py`（若动反馈段：带理由重试仍成立）
- 前端**不改**（降级标注若需要展示，走既有 `degraded` 文案通道，不新开 UI 分支）
- 只读探针落 `.scratch/recommend-domain-reject/`（形态取证）

## 验收标准

- [ ] 红证：用现场原始输出形态（探针落盘的那份）直测 `_parse_model_instances`／
      `build_module_selection` → 现状抛 `SelectionError`「模块 X 不支持多实例」
- [ ] 方向 ② 落地后：**单元素**非法 instances → **不抛**，产出「无实例（默认单实例）」+
      可见降级标注；**≥2 元素**仍抛（对照用例：`k230` 带 2 个实例必须仍拒收）
- [ ] `{"instances": null}` 与 `[]` 的现状**逐字节不变**（既有用例不红）
- [ ] 真机：`probe-16-recommend-live.py --topic 2026H --platform mspm0 --attempts 2
      --out-prefix done-22`（跑前 `$env:PYTHONIOENCODING='utf-8'`）——期望
      `[PROBE16][域拒绝]` 行里**不再出现**「不支持多实例」（或仅剩 ≥2 元素形态）
- [ ] 全量 `pytest` + `node --test tests/js/*.test.mjs` 绿
- [ ] 若采纳「单元素降级」，在工单里写清**为什么这不违反「宁严勿假绿」**（恒等变换论证）

## 不做什么（明确范围外）

- 不加宽 `multi_instance` 能力清单（模块能力是 manifest 事实，不因模型幻觉而改）。
- 不做模糊匹配 / 猜测模型意图（判据只有「长度 1 / ≥2」这一条确定性线）。
- 不把 `instances` 非法一律降级为「忽略」（≥2 元素是真诉求，忽略 = 静默改变用户要的硬件）。

## 已知坑

- 探针在 GBK 控制台会因 `⚠`（U+26A0）崩溃 → 必须 `$env:PYTHONIOENCODING='utf-8'`；
  探针第三处锚点（「超长守卫」）已失配，会打印「锚点命中 0 处」后继续，不影响其余两处。
- 探针打印的是**异常本体**（`str(exc)`），不是用户可见文案——文案链路的证据要用
  `tests/test_errors.py` 的端到端用例（单 03 先例）。
- 提交信息别用 PowerShell 的 `Out-File -Encoding utf8` 生成 `-F` 消息文件（带 BOM 会打穿
  CHANGELOG 跳过清单，见盘点「新发现」第 6 条）。
