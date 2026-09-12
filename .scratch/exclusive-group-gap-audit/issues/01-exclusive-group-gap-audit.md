# 01 — 全库排查「同类功能件没有同组」，补齐证据充分的功能组

**要做什么：** 推荐结果里不再出现「同一功能的两件同时进工程集」——库内所有**证据充分**的
同功能件都进同一张功能组卡（radio 可点、带 role），需求句里只留一条灰注；证据不足或组语义
有歧义的条目列成清单交给用户拍板，不自己拍板。

**被谁阻塞：** 无——可立即开始（判据与脚本先例来自已 resolved 的
`.scratch/attitude-group-jy61p/01` 与 `.scratch/group-choice-required/spec.md`）。

**状态：** resolved

- [x] 阶段一：机械筛脚本（notes 关键词 × 别的模块名 / 默认脚重叠 / 同功能多实现形态）
      产出候选池，输出落 `.scratch/exclusive-group-gap-audit/scan-output.txt`（关键词 104 条、
      默认脚重叠 stm32 27 脚 / mspm0 28 脚）。
- [x] 阶段二：逐条裁定（候选对/组、证据、判定三档：并组 / 不并 / 待用户拍板），证据引到
      `manifest` 字段 + notes 原文片段 + `pin_config.h` 行号 + `mspm0.syscfg` 实例名
      （排查表 `.scratch/exclusive-group-gap-audit/audit.md`）。
- [x] 红证（改前）：8 条载荷跑 `selection.build_module_selection` → **7 红**（4 组候选全红 +
      3 条待拍板红；对照样例姿态组绿 = 探针确实接上了收敛链路）——`red-before.txt`。
- [x] 并组 1 `distance`：us016 / ir_distance / vl53l0x / sr04 —— label 与 role 齐备。
- [x] 并组 2 `display`：lcd / oled / max7219 / ili9341 / ili9488 / st7789_para。
- [x] 并组 3 `barometer`：bmp180 / ms5611。
- [x] 并组 4 `sound-prompt`：beep / jq8900。
- [x] 并组 5 `zigbee-rx` 扩容 + 组名中性化（用户拍板第二批）：as32 / ec01g / esp01s / hc05 /
      nrf24l01 / zigbee_link / zigbee_uart（label「Zigbee 无线链路（接收侧）」→「无线链路 / 数传」，
      组 id 不变）。
- [x] 并组 6 `positioning`（新开）：uwb_uart / neo_6m（label「定位 / 位置测量」）。
- [x] 「不并」逐条留证（37 条，防下一轮重复产出同一批候选）；无线族以外的语义歧义项已全部
      裁定（语音两件、温湿度族等）——**无遗留待拍板项**。
- [x] 绿证（改后）：9 条载荷**全绿**（每组只剩一件 + 另一件进 `dropped_exclusive_members`）
      ——`green-after.txt`。
- [x] 同步测试基准：`tests/test_module_universality.py` 真库断言（组 id 集合 3 → 8 + 每组
      label/成员逐字）+ 新 `tests/test_exclusive_group_gap_audit.py`（13 例：形状 + role +
      每平台投影 ≥2 成员 + 库内自证片段 + 同载荷收敛）+ `tests/test_selection.py` 的
      `zigbee-rx` 真库出卡用例（成员清单按平台投影更新，**判据未改**）。
- [x] 端到端：`python .scratch/group-choice-required/make-payload.py` 重跑，
      组卡 `recommended` 每组 ≤1，两份 fixture 逐字节未变。
- [x] 全量回归：`pytest` **4036 passed**（改前 collect 4023，+13 新用例）、
      `node --test tests/js/*.test.mjs` **1467 pass / 0 fail**、
      `mypy src/contest_generator/selection.py` **干净**；数值写进排查表与 tracker-audit 收口段。
- [x] 每条改动一次中文 git 提交（不 push）；`.scratch/tracker-audit/2026-09-09-在途盘点.md`
      追加收口段。

## 实施记录（2026-09-13）

**改动清单（每条一次提交，均中文）**：

| 提交 | 内容 |
|---|---|
| `库：beep 与 jq8900 并入功能组「提示输出 / 声」（1/4）` | `library/modules/{beep,jq8900}/manifest.json` |
| `库：bmp180 与 ms5611 并入功能组「气压 / 海拔传感器」（2/4）` | `library/modules/{bmp180,ms5611}/manifest.json` |
| `库：us016/ir_distance/vl53l0x/sr04 并入功能组「距离测量 / 测距传感器」（3/4）` | 4 个 manifest |
| `库：lcd/oled/max7219/ili9341/ili9488/st7789_para 并入功能组「显示 / 屏幕」（4/4）` | 6 个 manifest |
| `test(库): 功能组缺口排查的真库基准与四组结构守卫` | `tests/test_module_universality.py` + 新 `tests/test_exclusive_group_gap_audit.py` |
| 第二批（用户拍板）`库：无线链路族并入 zigbee-rx 并改中性组名 + 新开定位组` | `as32`/`ec01g`/`esp01s`/`hc05`/`nrf24l01`/`zigbee_link`/`zigbee_uart`/`uwb_uart`/`neo_6m` 九个 manifest |
| 第二批基准 `test(库): zigbee-rx 扩容与定位组入基准` | `test_module_universality.py`/`test_exclusive_group_gap_audit.py`/`test_selection.py` |

**只动 `exclusive_group` 一个字段**（未动引脚/notes/其它字段）；库内功能组从 3 组 / 8 个模块
→ **8 组 / 29 个成员位**（stm32 侧 6 组 / 22 位、mspm0 侧 7 组 / 20 位）。

**红证/绿证口径**：载荷 = 两条需求句各推同组一件（模拟「AI 把同一功能的两件分别挂到两句上」），
跑真实 `build_module_selection`（真库 manifest + 真摘要，零额度）。红 = 两件同时在顶层
`modules`；绿 = 只剩一件 + 另一件进 `dropped_exclusive_members`。改前 7/8 红 → 改后 9 条全绿。

**复核两次、改了两处口径**（见排查表 §2.2「改主意原因」）：`ec01g`（NB-IoT）与
`hc05`/`esp01s`（蓝牙×WiFi）首轮判「不并」，复核发现与 LoRa 那条**判据不一致**（同一路 UART
只能挂一个驱动、notes 都明写「互替件/二选一接入」）→ 一律并入。组 id `zigbee-rx` 保持不变
（id 不是用户可见词；改名会牵动赛题 `hint_module_groups` 存量值，留作后续迁移单）。

**留口**：① `beep` 的 mspm0 条目是占位实现（要在 mspm0 用蜂鸣器需先接线）；② `vl53l0x` ×
`tcs34725` stm32 同址 0x29 属同址冲突非同类功能，按原样留；③ `sr04` 收进 `distance` 是口径
推断而非库内直证；④ 跨组同脚（`uwb_uart`×`hc05` 在 mspm0 同 UART2、`hc05`/`esp01s`×
`digit_uart` 在 stm32 同 UART_1）由引脚绑定消解，不并组（一个模块只能属一个组）。
