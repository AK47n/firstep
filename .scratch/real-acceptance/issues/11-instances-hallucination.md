# 11 — instances 幻觉：非多实例模块被输出实例数组，靠一次重试自愈仍会烧调用

**要做什么：** 让「模型给**不支持多实例**的模块输出 `instances`」不再消耗一次重试调用
（当前靠 `DOMAIN_RETRY_LIMIT=1` 带理由重出一次自愈），并在重试也用尽时给出**可操作**的
终态指引（而不是只报「模块 X 不支持多实例」这一句内部事实）。

**被谁阻塞：** 无（前置 = 单 03 已 resolved：domain 分流 + 带理由重试机制已就位）。

**状态：** resolved

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
     **【实施会话取证结论：前提被推翻——真违规是空数组，见下「实施记录 ①」】**
2. **确定性兜底（首选，与单 08 的 B1 同款思路：能做确定性对齐就不加模糊判断）**：
   在 `_parse_model_instances` 里，对**非多实例模块**的 `instances`：
   - **长度 = 1** 且该模块本就是单实例 → **确定性降级**为「无实例（默认单实例）」，
     并让调用方能拿到一条**可见的降级标注**（照 `OutOfLibrarySuggestion.degraded`
     先例：载荷带 `instances_degraded` / 或经 reason 文案点明）——语义上
     「1 个实例 = 默认单实例」是**等价**的，丢的不是信息，是一次无谓的拒绝；
   - **长度 ≥ 2** → 仍是真幻觉（用户真要多实例，而该模块没有能力），**保持拒收**
     并走现有带理由重试（`DOMAIN_FEEDBACK_SEGMENT` 已能接住）。
   判据口径与「宁严勿假绿」不冲突：单实例化是**恒等变换**，多实例化是**不可能的诉求**。
   **【实施会话收窄：判据由「长度 = 1」放宽为「长度 ≤ 1」——现场 4/4 违规是 `[]`，
   见「实施记录 ②」；≥2 仍拒收不变】**
3. **重试反馈更具体（可与 ② 并行）**：`DOMAIN_FEEDBACK_SEGMENT` 现在带的是
   `SelectionError` 原文（「模块 oled 不支持多实例」）。若 ② 落地，剩下的违规天然只剩
   「要 2 个以上但没能力」这类，反馈段可点明**可选的替代**（如「删掉 instances 用默认
   单实例，或改选支持多实例的模块」），把「一句内部事实」变成「怎么改」。
4. **提示词不动（本轮默认）**：多实例规则段已含硬约束与反例（`digit_uart` 整轮失败），
   再加字数的收益已被现场否定；若要动，须先证 ② 落地后仍有残余违规。
   **【实施会话遵守：`llm.py` 多实例规则段逐字节未改】**

## 实施记录（本轮落地）

### ① 诊断：现场违规形态 = **空数组 `[]`**（前提被推翻）

探针 `.scratch/recommend-domain-reject/probe-22-instances-shape.py`（复用 probe-16 装配，
多注入一处：域拒绝时把**当轮模型原始输出**整份落盘）跑 2026H / mspm0 三次真实推荐，
抓到 **4 条违规现场 / 15 个 instances 形态**（落盘
`instances-shape-22.txt`、日志 `verify-22-instances-shape.txt`）：

- **4/4 条违规都是 `"instances": []`（元素 0 个）**：违规模块 = `oled`（1 条）、
  `k230`（3 条），原右侧形态一律 `[]`；模型把空数组当「无实例」的默认写法，
  几乎给**每个**非多实例模块条目都补上（同批里 xunji / pid / huidu / motor /
  step_motor / ir_beam / coord_detect / lcd / imu_uart / ml_mpu6050 都是 `[]`）；
- 同批里**唯一的非空形态**出现在真多实例模块 `key` 上
  （`[{"name": "启动按键", "variant": "start"}]`，len=1，合法、不违规）；
- 也就是说：**现场一条「非多实例模块带非空数组」都没有**，工单原文「真违规的是非空
  数组」是未取证的初判。若严格按原判据（只降级 len=1），现场违规**一条不减**、
  本次修复的目标（不再白花一次分钟级调用）与验收项（域拒绝里不再出现「不支持
  多实例」）都落空。

### ② 落地判据：长度 **≤ 1** 降级，≥2 仍拒收（用户现场裁决：覆盖空数组）

`selection._parse_model_instances`：非多实例模块的 `instances` 是数组且长度 ≤ 1 →
**确定性降级**为「无实例（默认单实例）」并记一条可见标注
`INSTANCES_DEGRADED_NOTE = "（不支持多实例，已按默认单实例处理）"`；长度 ≥ 2 → 照旧
抛 `SelectionError`（原文不变）走带理由重试；`null` / 缺省现状不变（本来就返回空）。

**为什么不违反「宁严勿假绿」（恒等变换论证）**：该模块只能出单默认实例，生成侧
`expand_instances` 对非多实例模块的非空清单本来就大声抛错 → 丢弃这 0/1 个实例后走的
正是它**唯一可能成功的路径**，产物逐字节不变。0 元素（`[]`）比单元素更彻底地是恒等
变换（`[]` 与 `null` / 缺省同义，都是「无实例」）。而 ≥2 元素是**不可能的诉求**（用户
真要两套硬件而模块没有能力），静默忽略会改变用户要的硬件 → 仍拒收。判据只有「长度」
这一条确定性线，无模糊匹配、无猜测意图。

**降级标注的两个可见出口**（前端零改动）：
- 模块 `reason` 追加标注 → 推荐卡 chip 副标题就是 reason（既有文案通道，用户可见）；
- done 载荷带 `instances_degraded`（slug → 标注，机器可见；**非空才落键**，
  零降级载荷逐字节不变）。域对象 `ModuleSelection.instances_degraded` 是标注单源。

### ③ 重试反馈：从「一句内部事实」变「怎么改」

`DOMAIN_FEEDBACK_SEGMENT` 增一段可操作改法（先删后换）：删掉系统不认的字段
（如 instances）后按默认单实例使用 / 确实要多个同类器件时改选清单里带「多实例」
标注的模块 / 库外硬件名降级为词表内类别名。三类域拒绝（instances / 幻觉 slug /
词表外名）用同一句覆盖，**不按理由串做分支**。

### 红证（工单验收第 1 条）与绿证对照

`probe-22-red-first.py` 把现场落盘的 **61 个 instances 形态逐个重放**进
`build_module_selection`（多实例能力清单取真实库 = `key, led`，与生产同源）：

| 侧 | 命令 | 结果 |
|---|---|---|
| 红（HEAD，`git stash` 掉本轮 selection 改动） | `probe-22-red-first.py` | **拒收 57 / 通过 4** → `verify-22-red-first-before.txt`（57 条全是「模块 X 不支持多实例，不能带 instances」，4 条通过 = `key` 的合法多实例形态） |
| 绿（本轮修复） | 同上 | **拒收 0 / 通过 61** → `verify-22-red-first-after.txt`（非多实例模块的 `[]`/单元素全部降级，`key` 的真实例清单原样保留） |

红证对应用例：`tests/test_selection.py::test_build_selection_empty_instance_array_on_single_instance_module_degrades`
（现场主形态）与 `…single_instance_on_single_instance_module_degrades`（单元素）；
对照用例 `…two_instances_on_single_instance_module_still_rejected`（k230 带 2 个实例仍拒收）。
`null` 与字段缺省现状不变：`…instances_null_and_absent_are_untouched`。

### 真机验收（2026H / mspm0，四次真实推荐）

| 跑 | 命令 | 结果 |
|---|---|---|
| 1 | `probe-16-recommend-live.py --topic 2026H --platform mspm0 --attempts 2 --out-prefix done-22`（工单原命令） | 终态 **done**（4 轮收敛），`[PROBE16][域拒绝]` **零**「不支持多实例」 → `verify-22-recommend-2026H-mspm0.txt`、`done-22-2026H-mspm0-run1.json` |
| 2 | 同上 `--attempts 3` | 第 1 次走澄清门收尾 question（域拒绝只有词表外硬件名 `PAD/笔记本电脑`，与 instances 无关） → `…-run2.txt` |
| 3 | 同上 + `--clarify-answers clarify-answers-18-2026H.json` | 终态 **done**（4 轮收敛）、零域拒绝 → `…-run3.txt`；另跑 `probe-22-degrade-live.py` 监听降级路径：run1 接住 `k230`，run2 接住 `k230 / ntb_time / oled / huidu / motor / step_motor / coord_detect` 共 7 个模块，两跑都 done → `verify-22-degrade-live.txt`、`degraded-22-live.txt` |

第 3 项是关键正证：**模型在真机上确实又犯了同一形态**（7 个单实例模块带 instances），
解析层降级接住 → 全程零域拒绝、零白花调用、终态 done；修前这些形态每条都是一次
`SelectionError` → 带理由重试 → 两次都犯即终态失败（第十六轮 9 轮里 5 轮的病根）。

## 文件边界

- `src/contest_generator/selection.py`（`_parse_model_instances` 判决 + 降级标注透传）
- `src/contest_generator/llm.py`（**仅**当采纳方向 ③：`DOMAIN_FEEDBACK_SEGMENT` 文案）
- `tests/test_selection.py`（解析判决：单元素降级 / 多元素仍拒收 / `null` 与 `[]` 现状不变）
- `tests/test_llm.py`（若动反馈段：带理由重试仍成立）
- 前端**不改**（降级标注若需要展示，走既有 `degraded` 文案通道，不新开 UI 分支）
- 只读探针落 `.scratch/recommend-domain-reject/`（形态取证）

## 验收标准

- [x] 红证：用现场原始输出形态（探针落盘的那份）直测 `_parse_model_instances`／
      `build_module_selection` → 现状抛 `SelectionError`「模块 X 不支持多实例」
      —— `probe-22-red-first.py` 把现场 61 个形态逐个重放：**修前拒收 57 / 通过 4**
      （`verify-22-red-first-before.txt`），修复后 **拒收 0 / 通过 61**
      （`verify-22-red-first-after.txt`）
- [x] 方向 ② 落地后：**长度 ≤ 1** 的非法 instances → **不抛**，产出「无实例（默认单实例）」+
      可见降级标注；**≥2 元素**仍抛（对照用例：`k230` 带 2 个实例必须仍拒收）
- [x] `{"instances": null}` 现状**逐字节不变**（用例 `…instances_null_and_absent_are_untouched`）；
      **`[]` 一项按现场取证 + 用户现场裁决放弃原 pin**：现场 4/4 违规就是 `[]`
      （工单原文的「真违规 = 非空数组」是未取证初判），只降级单元素 = 现场违规一条
      不减、验收第 4 条与本次修复目标一起落空 → 判据收窄为「长度 ≤ 1」，
      理由与恒等变换论证见「实施记录 ②」
- [x] 真机：`probe-16-recommend-live.py --topic 2026H --platform mspm0 --attempts 2
      --out-prefix done-22`（跑前 `$env:PYTHONIOENCODING='utf-8'`）——
      `[PROBE16][域拒绝]` 行里**零**「不支持多实例」（两跑皆 done，见
      `verify-22-recommend-2026H-mspm0.txt` / `…-run3.txt`；`…-run2.txt` 那跑唯一的
      域拒绝是词表外硬件名 `PAD/笔记本电脑`，与 instances 无关）；**另附降级路径
      正证** `probe-22-degrade-live.py`：现场确实又犯了同一形态，被降级接住而不再拒收
      （`verify-22-degrade-live.txt`：run1 接住 `k230`；run2 接住 `k230, ntb_time,
      oled, huidu, motor, step_motor, coord_detect` 共 7 个模块，两跑终态都 done）
- [x] 全量 `pytest`（3981 passed）+ `node --test tests/js/*.test.mjs`（1444 pass）绿
- [x] 若采纳「单实例降级」，在工单里写清**为什么这不违反「宁严勿假绿」**（恒等变换论证）
      —— 见「实施记录 ②」

## 不做什么（明确范围外）

- 不加宽 `multi_instance` 能力清单（模块能力是 manifest 事实，不因模型幻觉而改）。
- 不做模糊匹配 / 猜测模型意图（判据只有「长度 ≤ 1 / ≥ 2」这一条确定性线）。
- 不把 `instances` 非法一律降级为「忽略」（≥2 元素是真诉求，忽略 = 静默改变用户要的硬件）。
- 不改前端（降级标注走既有 reason 通道 + 载荷字段，不新开 UI 分支）。

## 已知坑

- 探针在 GBK 控制台会因 `⚠`（U+26A0）崩溃 → 必须 `$env:PYTHONIOENCODING='utf-8'`；
  探针第三处锚点（「超长守卫」）已失配，会打印「锚点命中 0 处」后继续，不影响其余两处。
- 探针打印的是**异常本体**（`str(exc)`），不是用户可见文案——文案链路的证据要用
  `tests/test_errors.py` 的端到端用例（单 03 先例）。
- 提交信息别用 PowerShell 的 `Out-File -Encoding utf8` 生成 `-F` 消息文件（带 BOM 会打穿
  CHANGELOG 跳过清单，见盘点「新发现」第 6 条）。
