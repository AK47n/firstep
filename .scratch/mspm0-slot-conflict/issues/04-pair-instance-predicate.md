# 04 — 全库累积态相收口：uart/i2c 成对实例补跨角色谓词 + 谓词改「并列全成立」

**要做什么：** 把工单 03「不做」里记的那条线索结清——全库（93 模块 / mspm0 176 角色 +
stm32 201 角色）累积态枚举暴露的 **188 条（mspm0）+ 52 条（stm32）**「板图显示可绑、
生成必 400」全部收口；顺带修掉测量中新暴露的 **37 条**同型缝（多条门禁并存时
单条 `constraint` 字段装不下）。

**被谁阻塞：** 无（工单 03 已 resolved；本单是它「不做」条目的后续）。

**状态：** resolved（2026-09-12；`tests/test_bindings_matrix.py` 30 条全绿；
`python -m pytest -q` = 4191 passed；`node --test tests/js/*.test.mjs` = 1519 passed）

## 背景（工单 03 留下的线索，逐字核实）

工单 03「不做」：

> 未开全库累积态相：全库（84 模块 / 176 角色）枚举已实测暴露 **188 条 `pair` 类既有
> 分歧**（`as32` / `debug_uart` / `hc05` / zigbee 族的 UART TX/RX 跨角色成对）——
> 那是工单 04 当年**有意**不动的一类（「uart/i2c 成对不叠谓词」）……若将来要开全库相，
> 先决定要不要给 uart 成对补跨角色谓词，否则那 188 条会当场变红。

用户 2026-09-12 拍板：**补谓词，口径 = 严格镜像 `_check_paired_role_instances`，两平台一起收。**

## 复现与定量（`.scratch/mspm0-slot-conflict/probe_full_library_accumulated.py`）

口径与 `tests/test_bindings_matrix.py` 的累积态相逐字一致（模型放行的一步改绑 → 并入
累积 bindings → **整份**回验 `resolve_bindings`）：

| 平台 | 种子 | 样本 | 修前假绿 | 分类 |
|---|---|---|---|---|
| mspm0 | 空 | 4405 | **188** | 188/188 = `_check_paired_role_instances` |
| mspm0 | 默认脚 | 4229 | 19 | 18 pair + 1 slot（后者判据不是槽位谓词，见下） |
| stm32 | 空 | 5082 | **52** | 52/52 同门禁（当年没记进工单） |
| stm32 | 默认脚 | 4882 | 0 | — |

涉及的模块正是线索里点的族：`as32` / `debug_uart` / `hc05` / `imu_uart` / `uwb_uart` /
`fingerprint` / `zigbee_link` / `zigbee_uart` / `zigbee_uart_key` / `coord_detect` /
`digit_uart` / `open_mv4` / `esp01s` / `neo_6m` / `ec01g` 等。

## 根因（两层，第二层是新发现）

1. **模型缺成对实例谓词**（工单 gen-chain-audit/04 实现期修正④「uart/i2c 成对不叠谓词」）：
   它当年判断「脚自带的实例集够了」——那只在**同一模块内**成立。跨角色看，能力层
   `selectable` 对 uart 是**类型级**（有 uart token 即可），说不出「必须与对脚同实例」。
   实测：`as32.AS32_UART_TX → PA0`（UART0）看着能点，而 `AS32_UART_RX` 默认 PA25 走
   UART3 → 交集空 → 整份 400。
2. **`_role_pair_mate` 找不到 uart/i2c 的对脚**（隐藏原因，没人记过）：它按「同类型」
   配对，pwm 的 C0/C1 同为 `pwm` 能配上；uart 的 TX 是 `uart_tx`、RX 是 `uart_rx`
   → **恒返回 `None`**。也就是说这条缝即使有人想补也补不上（谓词接不上对脚）。
   本次把配对表 `_PAIRED_ROLE_KINDS` 抽成**单源**，`_check_paired_role_instances`
   与 `_role_pair_mate` 同吃它，并加了导入期自洽断言（对脚条目必须回指本类型）。

## 交付（实现后的实际形状）

- `_PAIRED_ROLE_KINDS`（`pin_bindings.py` 顶部）：`<本脚类型> → (对脚类型, 本尾, 对尾,
  本名, 对名)`，uart_tx↔uart_rx、i2c_scl↔i2c_sda；导入期断言表对称。
- `_check_paired_role_instances` 改为遍历该表（判据一字未动，只换了配对表的出处）。
- `_role_pair_mate`：配对改为「配对类型」而非「同类型」（pwm 沿用既有 `_C0/_C1` 正则）。
- `build_bindings_matrix`：`mate_instances` 从「仅 pwm」放开到 uart/i2c；对脚无实例 →
  不给谓词（与门禁的防御性 `continue` 同守卫，避免 stm32 i2c 那类 58 条假红）。
- **谓词并列化**：端口组 / 成对实例 / 槽位三级各自判「本级有无定解」，**同时成立的全部
  产出**；单条时只发 `constraint`（形状向后兼容），多条时另发 `constraints` 数组。
- 前端 `fx/pin-model.js`：新增 `pinModelConstraints`（读取口径单源）与
  `pinConstraintHolds`（单条谓词求值），`pinModelVerdict` = **全部成立**，
  `pinModelMissReason` = 第一条不成立的原因。
- webapp `/api/bindings/matrix` 端点文档串同步契约。

## 为什么必须并列（37 条新缝，测量中新暴露）

第 1/2 级成立**不能**把第 3 级吞掉：`as32.AS32_UART_TX` 既有 uart 对脚（第 2 级），
又与 `zigbee_link.ZIGBEE_UART_TX` 默认同 PA26、同 syscfg 落点（第 3 级同槽位）。
只发第 2 级 → 槽位那条丢失 → 默认脚种子相实测 **37 条**同型假绿
（`as32.AS32_UART_TX → PB2`、`coord_detect.COORD_DETECT_UART_TX → PB6` …）。
反向验证：退回「只发第一条」→ 37 条当场回来。

## 验收（全部达成）

- [x] 全库两平台 × 两相（空种子 / 默认脚种子）累积态对拍：**假绿 0 / 假红 0**
      （样本 4405 / 4229 / 5082 / 4882）。
- [x] 新用例（`tests/test_bindings_matrix.py`，30 条）：
      - `test_uart_pair_instance_predicate_mirrors_gate`（形状 + 随观测变 + 整对可搬）；
      - `test_uart_pair_predicate_none_when_peer_has_no_instances`（stm32 i2c 不发谓词）；
      - `test_uart_pair_predicate_blocks_single_foot_move_with_peer_bound`（累积态回归锚，
        mspm0 `as32` + `debug_uart` 同选同绑 = 188 条的真实形状）；
      - `test_full_library_accumulated_state_has_no_divergence[mspm0|stm32]`（全库两相）；
      - `test_full_library_default_seed_has_no_divergence`（含 37 条那相）；
      - 旧用例 `test_uart_type_level_pair_has_no_cross_role_constraint` 已按新契约改写
        （它钉的正是本轮改掉的旧口径，逐字留档在 docstring 里）。
      - JS 侧：`constraints` 数组「全部成立才可绑」+ 原因取第一条 + 读取口径单源。
- [x] **反向验证**：`.scratch/mspm0-slot-conflict/reverse_verify_pair_predicate.py` →
      停用成对实例谓词 = 188（mspm0 空种子）/ 52（stm32）/ 224（mspm0 默认脚种子，
      因为默认种子下成对谓词还顺带挡了 37 条中的一部分）；只发第一条 = 37。
      证据 `.scratch/mspm0-slot-conflict/reverse-verify-pair-predicate.txt`。
- [x] 全量回归：`python -m pytest -q` = 4191 passed（修前 4186）；
      `node --test tests/js/*.test.mjs` = 1519 passed。
- [x] 性能：全库矩阵仍 < 1s（用例 `test_matrix_is_cheap_enough_for_every_render`）。

## 实现期事故（记下来防重犯）

**用 PowerShell 5.1 的 `Get-Content -Raw` + `Set-Content -Encoding utf8` 做批量改写，
把 `tests/test_bindings_matrix.py` 的中文注释全变成乱码**（该文件当时是**未入库**的新文件，
没有 git 可回滚）：PS 5.1 读无 BOM 的 UTF-8 文件时按系统 ANSI(GBK) 解码 → 文本已损坏 →
重写时还加了 BOM。事后尝试「按 GBK 回编 → UTF-8 解码」逆变换失败（该往返对
`0x80`/`0xA0` 区间的字节不可逆，6627 个字符回不去），最终按早前读到的内容**整份重写**。
两条规矩写在这里：① 改源码一律用编辑工具（`edit` / `write`），不用 PowerShell 做文本往返；
② 动手前先确认目标文件是否已入库（未入库 = 没有后悔药）。

## 不做 / 记账

- **成对角色在界面上搬不动**（本单的直接后果，**不是 bug 而是交互缺口**）：后端门禁的
  语义是「TX/RX 一起换实例才合法」，而界面是**单角色绑一脚**（`bindRole` 一次写一个 key），
  于是 `debug_uart.TX → PA28`（异实例）在后端本来就 400（实测），模型严格镜像后也必须挡
  ——「不假绿」与「可搬家」在单角色交互下不可兼得。逃生门也不管这事：`auto_assign_bindings`
  遇到 `{TX: PA28}` 的解法是把 TX **退回默认 PA23**，不是把对搬过去。
  量表：mspm0 全库 14 个 uart/i2c 对**全部**在默认实例里还有第二个位（可搬，但必须一起搬），
  stm32 13 个 uart 对每实例只有一对脚（原地即唯一解，无可搬）。→ 新工单 **05**。
- 单条 `constraint` 字段的语义现在是「第一条（优先级最高）」，历史消费者只读它不会坏，
  但**真要判可绑必须读 `constraints`**（前端已单源收敛）。
- 真机审计（`node tests/browser/gen-chain-audit.mjs P`）本轮**未重跑**（需浏览器）；
  它的 P1 节直接求值前端真函数 `pinModelVerdict`，契约变化已被 JS 用例覆盖，但
  新产物（`audit-P-after.txt`）待补。
