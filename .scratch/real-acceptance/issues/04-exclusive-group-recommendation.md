# 04 — 推荐层互斥组：同组多成员被同时推荐，生成才 400

**要做什么：** 让「功能组（同组互斥）」在**推荐阶段**就收敛到「组内只选一个」——
现状是提示词已写「只推荐一个」，但载荷 `exclusive_groups[].recommended` 里仍可能
两个成员都在，一路走到生成门禁才 400，用户拿着一个「推荐成功」的结果点生成却报错。

**被谁阻塞：** 无（`recommend-exclusive-groups/01-03` 已交付组声明 / 选择卡 / 提示词段）。

**状态：** resolved（2026-09-11 收口；验收证据见文末「收口」段）

## 真机现场（2026-09-10 第十六轮 A8/A9 实跑）

2026C / stm32 真机推荐（`.scratch/real-run/verify-16-A8-stm32-2026C.txt`、
缓存载荷 `.scratch/real-run/cache/recommend_2026C.json`）：

```
模块(9): zigbee_uart_key, zigbee_link, zigbee_uart, uwb_uart, oled, led_beep, led, relay, key
...
exclusive_groups[0] = {
  "id": "zigbee-rx", "label": "Zigbee 无线链路（接收侧）",
  "members":     [zigbee_link, zigbee_uart],
  "recommended": [zigbee_link, zigbee_uart]      ← 两个都推荐了
}
```

生成阶段：

```
HTTP 400 /api/generate:
{"detail":"模块 zigbee_uart 与 zigbee_link 互斥：同一路 ZIGBEE_UART 接收只能选一个驱动
（固定 ID 帧与通用帧收发），请二选一。"}
```

本轮按既有先例 `--drop zigbee_link` 收口（`generate_check.py` 的 `--drop` 就是
「前端同款手动增删语义」），验收照跑；但**「用户点一次就能用的推荐结果」这个承诺被破坏了**。

## 为什么算缺陷（不是「模型不听话」就算了）

1. **提示词已写硬约束**（`recommend-exclusive-groups/03`）：`_selection_user_prompt` 的
   「同组互斥（硬约束）」段明确「同一题内**只推荐一个**」——模型没遵守，而解析层
   （`build_module_selection`）对同组多成员**不校验**，于是错误一路穿到生成期。
2. **代价落在最贵的一步**：识别到冲突的地方是生成门禁（要用户已经点过「生成」），
   而推荐层本来就知道这组里有哪些成员、哪个更贴题面（`members[].role` 已带语义）。
3. **同族先例可循**：`HARD_EXCLUSIVE_PAIRS` 走的是「硬互斥对 + 门禁兜底双保险」，
   推荐层缺的正是第一道保险。

## 修复方向（实施会话定措辞，红证先行）

1. **解析层确定性收敛**（首选，零额外额度）：`build_module_selection` 收到同组多成员时，
   按模型给的 `reason` / `requirements` 引用计数或清单顺序保留一个、其余剔到
   「同组候选（未选中）」并落进 done 载荷的新字段（前端选择卡已能展示成员与推荐标记
   ——`_group_card` 的 `recommended` 字段就是这条链路）；**不做静默丢弃**，剔掉的要可见。
2. **或**给域拒绝加一次「组内二选一」的重问（依赖新单 03 的「域拒绝带理由重试」能力，
   有额度成本，次选）。
3. **载荷契约**：`exclusive_groups[].recommended` 保持数组（旧前端兼容），但语义收紧为
   「组内 ≤1」；`tests/js` 选择卡渲染与 `tests/test_selection*.py` 补断言。

## 验收标准

- [x] 红证：把 2026C 那份真实缓存载荷（或等价 fixture）喂解析层 → 现状同组两成员都进
      `selected`；实施后只留一个 + 另一个出现在「未选中候选」
      （`tests/test_selection.py::test_build_selection_real_2026c_payload_converges_zigbee_rx`，
      fixture = `.scratch/real-run/cache/recommend_2026C.json` 原文，不抄副本）
- [x] 真机：2026C / stm32 推荐后**不再需要 `--drop`** 即可生成通过（`generate_check.py --reuse-recommend 2026C` 不带 `--drop` 跑绿）
- [x] 选择卡 UI：组卡仍显示两个成员、只有一个是推荐态
      （`tests/js/group-cards.test.mjs` 两条新用例：收敛卡 = 1 个「AI 推荐」+ 被剔成员标
      「同组互斥·未选中」；旧载荷无 `dropped` 零标注）
- [x] 全量 pytest + node 绿（3969 passed / 1432 pass 0 fail）

## 收口（2026-09-11）

**做法**：解析层确定性收敛（零额外额度）——`build_module_selection` 收
`manifest_summaries` 后按 `ManifestSummary.exclusive_group` 投影「组 → 候选成员」，
同组多成员只留**模型清单首个**，其余剔出顶层 `modules` 并记进
`ModuleSelection.dropped_exclusive_members`；需求层不改写（模型原始证据保留）。
`run_recommendation` 出卡前再收敛一次（直造 `ModuleSelection` 的调用方兜底），
载荷契约收紧为 `recommended` **组内 ≤1** + 新增 `candidates` / `dropped` 可见字段。
`generator.py` 的 `HARD_EXCLUSIVE_PAIRS` 门禁**不动**（最后一道）。

**真机验收输出**（不带 `--drop`）：

```
[缓存] 复用 ...\cache\recommend_2026C.json（推荐段跳过）
  → 同组互斥收敛：组 zigbee-rx 剔掉 ['zigbee_uart']（同组只留一个；被剔成员在选择卡「同组候选（未选中）」可见，无需 --drop）
  模块(8): zigbee_uart_key, zigbee_link, uwb_uart, oled, led_beep, led, relay, key
  [产物] 门禁全过（产物树语料重建，与生成同源）
  [真机] ✓ UV4 exit=0 Build Time Elapsed:  00:00:02（0 错误 0 警）
2026C: ✓ 通过
```

**对照取证**（同一台机器，一次性探针跑完即删）：原样 9 slug 喂 `/api/generate` →
`HTTP 400 {"detail":"模块 zigbee_uart 与 zigbee_link 互斥…请二选一。"}`；收敛后 8 slug →
`HTTP 200`。

**改动文件**：`src/contest_generator/selection.py`（收敛 + 出卡 + 载荷补刀）、
`src/contest_generator/llm.py`（把功能组摘要透传给解析层）、
`src/contest_generator/static/js/fx/module.js`（被剔成员标「同组互斥·未选中」）、
`.scratch/real-run/generate_check.py`（`--reuse-recommend` 路径补刀，缓存文件不改写）、
`tests/test_selection.py` + `tests/js/group-cards.test.mjs`。

**边界**：收敛保证「能生成」，不保证「选得最准」——保的是模型自己的排序，用户可在组卡
一键换选；`selection.modules`（进工程集）与 `requirements[].modules`（模型证据）收敛后
会有意不一致。详见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`「2026-09-11 收口」段。

## 实施提示词（新会话粘贴）

> 工单：`.scratch/real-acceptance/issues/04-exclusive-group-recommendation.md`（先读全文）。
> 背景：`.scratch/tracker-audit/2026-09-09-在途盘点.md`「第十六轮」④ O-1 与「③」。
> 任务：推荐层把「同组互斥」收敛到组内只选一个（解析层确定性收敛优先，零额外额度），剔掉的成员进「同组候选未选中」可见字段；生成门禁保留作兜底。
> 文件边界：`src/contest_generator/selection.py`（解析与载荷组装）+ 必要的前端选择卡（`static/js/*` 若有渲染改动）+ `tests/`；`generator.py` 的门禁不动。
> 红证先行：用 `.scratch/real-run/cache/recommend_2026C.json` 的真实载荷做 fixture。
> 真机验收：`python .scratch/real-run/generate_check.py --topics-dir library/topics --modules-dir library/modules --reuse-recommend 2026C` **不带 `--drop`** 跑绿。
