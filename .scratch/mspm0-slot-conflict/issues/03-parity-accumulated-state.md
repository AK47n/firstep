# 03 — parity 用例补「累积态」相：模型放行的一步改绑，整份回验后端必须收

**要做什么：** 把对拍守卫的对照口径从「模型判定 × `resolve_bindings({单个角色: 脚})`」
（单绑定，比真实提交窄）升级为「模型放行的一步改绑 → 并入累积 bindings → **整份**回验
后端必须收」——这才是用户点下去真实发出去的那份（`collectBindings`）。

**被谁阻塞：** 02（没有 `slot` 谓词时，本用例会被现有假绿当场判红——这正是它的价值，
所以它必须在 02 之后进）。

**状态：** resolved（2026-08-xx；`tests/test_bindings_matrix.py` 新增 4 条用例
（`_stepwise_false_greens` / `_default_pin_seed` 两个辅助））

## 背景（用例自身缺陷，如实记账）

工单 06 的单绑定对拍证明「一格一格都对」，但「单绑定收、累积态拒」这类分歧照不出来：
`{huidu.R3: PA0}` 后端收，`{huidu.R3: PA0, pid.GRAY_D7: PB6}` 后端拒。本轮该洞就是这么
从守卫底下漏过去的。

`test_greedy_user_walk_…` 虽然回验累积态，但两个原因覆盖不到：

1. 用的是 P1 审计集 `["step_motor","huidu","motor","led_beep"]`——`huidu` 在、`pid` **不在**
   → 同槽位对一对都不在；
2. 只走「每角色贪心取 `selectable` 第一个可选脚」**单路径**，不做「逐步 × 全候选」枚举。

## 交付（实现后的实际形状）

- `_stepwise_false_greens(manifests, board, seed)`：种子累积态出发，**逐步 × 全候选**枚举
  「模型放行的一步改绑」，并入累积 bindings 后整份回验 `resolve_bindings`；返回
  (假绿, 假红, 样本数)；
- `_default_pin_seed(manifests, board)`：种子 = 每个角色**显式绑回自己的默认脚**
  （`repro` ② 的真实形态；`collectBindings` 只带用户动过的角色，「动过又动回默认」留下的
  就是这种 no-op 条目，既有政策明确允许保留）；
- 4 条用例：
  1. `test_accumulated_state_matches_backend_from_default_state` —— 空种子 + P1 审计集，
     假绿 = 0 / 假红 = 0（样本 586）；
  2. `test_accumulated_state_blocks_slot_conflict_with_peer_bound` —— 默认脚种子的
     `huidu`+`pid` 场景，槽位互斥的**直接回归锚**（样本 748）；用例内先断言种子是合法态、
     且 `huidu.R3` 的谓词确实下发（防「选择集/种子变了导致用例空转」而静默失效）；
  3. `test_accumulated_state_blocks_slot_conflict_without_seed` —— 只绑
     `pid.GRAY_D7 → PB6` 一个角色（`huidu.R3` 未绑）的同款守卫；
  4. `test_accumulated_state_allows_moving_whole_slot_group` —— 反向：整组未动时谓词必须是
     `None`、第一步不许灰，第二步跟到同脚后整份合法。

## 实现期修正

1. **样本规模锚**：审计集 586 / huidu+pid 748（角色 × 放行脚）。断言写成「> 400」而不是
   钉死数字——本相的价值是覆盖形状（逐步 × 全候选），钉死数字会让无关库变更天天改基线；
   单绑定相那三条 744 / 115 / 158 是真机审计锚，仍钉死不动。
2. **两成员组不存在「同伴之间不一致」相**：`huidu.R3` 的同伴只有一个，`len(effective) != 1`
   走不到。该相要用 ≥3 成员组（adc 槽 PA24 上 18 个 ADC 成员）才测得出来——已写进 02 的
   用例并在本单文档里点明，`test_slot_constraint_none_when_observed_peers_disagree` 钉住。

## 验收（全部达成）

- [x] 空种子 + P1 审计集：假绿 = 0、假红 = 0（样本 586）。
- [x] 默认脚种子（`{huidu.R3: PB6, pid.GRAY_D7: PB6}` 形态）：假绿 = 0、假红 = 0（样本 748）。
- [x] 样本规模锚（`checked > 400`）+ 种子合法性 + 谓词确实下发三重前置断言。
- [x] 用例秒级（`tests/test_bindings_matrix.py` 全 25 条 0.84s）、无浏览器、无 LLM。
- [x] 既有单绑定对拍用例（全脚枚举 / 744 / 115 / 158 锚）保留不动、仍绿。
- [x] **反向验证**：停用 `slot` 谓词 → 本单的
      `test_accumulated_state_blocks_slot_conflict_with_peer_bound` /
      `…_without_seed` 当场红，复现脚本同时红；证据
      `.scratch/mspm0-slot-conflict/reverse-verify-slot-disabled.txt`。
- [x] `python -m pytest -q` = 4186 passed。

## 不做

- 未开全库累积态相：全库（84 模块 / 176 角色）枚举已实测暴露 **188 条 `pair` 类既有分歧**
  （`as32` / `debug_uart` / `hc05` / zigbee 族的 UART TX/RX 跨角色成对）——那是工单 04
  当年**有意**不动的一类（「uart/i2c 成对不叠谓词」），与本单的槽位互斥无关、也不在本轮
  范围。**记在这里当线索**：若将来要开全库相，先决定要不要给 uart 成对补跨角色谓词，
  否则那 188 条会当场变红。

  → **已结清（2026-09-12，工单 `04-pair-instance-predicate.md`）**：用户拍板补谓词
  （口径 = 严格镜像 `_check_paired_role_instances`，两平台一起收）。核实后的实际数字是
  全库 93 模块 / mspm0 176 角色 + stm32 201 角色：空种子 **188（mspm0）+ 52（stm32）**，
  默认脚种子还有 19（18 pair + 1 slot）；修完两平台两相**全部归零**。另外发现两个当年
  没人记过的事实：① `_role_pair_mate` 只配「同类型」对脚 → uart 的 TX/RX 恒配不上，
  这条缝即使有人想补也补不上（已改为与门禁同吃一份配对表 `_PAIRED_ROLE_KINDS`）；
  ② 谓词必须并列全成立（单条 `constraint` 字段装不下两条门禁，实测 37 条同型假绿）。
  成对角色在界面上搬不动这一后果 → 工单 `05-paired-move-ui.md`。
- 未改审计脚本 `gen-chain-audit.mjs` 的判据（它按「两边结论不一致」的事实报；真机 P1
  仍 FAIL 0 / WARN 0 / PASS 15）。
