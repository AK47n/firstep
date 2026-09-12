# 03 — 修：板图上「配得出的绑定」生成时必被拒（前端判据漏掉后端的组/pair 级门禁）

**要做什么：** mspm0 平台上，板图/菜单必须**不把「后端必拒的绑定」显示成可绑**
（灰显 + 原因），现在它显示成绿色可绑、真绑下去，生成前后 `/api/bindings/validate`
直接 400。复侦实测：这条缝有**两类**，共 115 条（84 条 gpio 同端口组 + 31 条 PWM
两通道同实例），且都是「跨角色」的组/pair 级判据。

**被谁阻塞：** 曾阻塞于「前端怎么拿到判定所需的数据」——用户 2026-08-xx 拍板**方案 B**
（后端单源下发判据），见 `../spec-matrix.md`，实现落在工单 04/05/06。

**状态：** resolved（真机 + 离线双零分歧；实现 = 工单 04/05/06）

## 修后结论（双证）

- **真机**：`node tests/browser/gen-chain-audit.mjs P` → mspm0 744 条候选
  **FAIL 0 / WARN 0**（15 PASS；UI 说行 586 条后端全收、UI 说不行 158 条后端全拒），
  stm32 600 条同样零分歧（证据 `.scratch/gen-chain-audit/audit-P-after.txt`）。
- **离线对拍**：`tests/test_bindings_matrix.py` 全脚枚举（24 角色 × 31 脚 = 744）逐条
  比「模型判定 × 真 `resolve_bindings`」：假绿 0、假红 0；另钉「旧口径 115 条分歧全
  被挡住」「候选 744 / 后端拒 158」两个锚。
- 修法：判据单源 = 后端 `/api/bindings/matrix` 下发「角色 × 可选脚 + 跨角色谓词」，
  前端 `fx/pin-model.js` 只求值（不再镜像规则）。审计脚本 P1 节也从「照抄镜像」改为
  直接求值前端真函数——否则前端修好了它还会报 115 条（本轮真踩过）。

## 复侦（离线探针，无浏览器 / 无 LLM；探针脚本已随工单收尾删除，判据落在 pytest）

把 P1 节的对拍搬成纯 Python（前端判据 = `pinCanHost` 逐行镜像；后端判据 = 真
`resolve_bindings` + 真板定义 + 真 `resolve_selection` 展开），逐条复现并**定量**：

```
模块集 [step_motor, huidu, motor, led, beep, delay, led_beep]（真展开）
IO 脚 31；候选 744 条；UI 说行 701 / UI 说不行 43
UI 放行但后端拒收：115 条
  · gpio 同端口组：84      ← 本单原判（step_motor 4 个 gpio_out × A 口 21 脚）
  · 成对/通道同实例：31    ← 本单**漏了**的同族缺口（motor.PWMAB_C0/C1 两通道）
修法候选（端口组 + 成对/通道两层补齐）：UI 放行但后端拒收 0 条；假红 0 条
```

三条新事实（都改了本单的结论）：

1. **115 = 两类缺口，不是一类**：84 条是 `_check_mspm0_gpio_port_groups`（单端口宏
   组），另 **31 条是 `_check_mspm0_pwm_channel_pairs`**（PWMAB 两通道同实例）。
   本单原来只记了前者 → 只补端口组的话，板图上仍剩 20 条「可配但必 400」。
   同族的还有 `_check_paired_role_instances`（uart TX/RX、i2c SCL/SDA）与
   `_check_slot_conflicts`——**同一个「前端判据 ≠ 后端判据」的类**，不是单条约束。
2. **缺口的形状是「组/pair 级」，不是「单脚级」**：后端两条门禁都跨角色（同模块同类型
   的端口组、同 pair 的两脚），判据单脚算不出来 → 这决定了修法（下发什么数据）
   而不是「照抄一段 if」。
3. **补法已验证可行**：把端口组（默认同端口 → 锁该端口）与成对/通道（绑定脚实例集 ×
   对脚**有效**实例集非空，对脚未绑 = 其默认）两层补进镜像后，744 条候选
   **分歧 115 → 0，且零假红**。所以修法不是「能不能」，只是「数据从哪来」。

**为什么 `pinCanHost` 稳放行**：mspm0 板定义给**每个** io 脚都标了无实例 token
（`gpio_out` / `gpio_in` / `enc` 各 31/31），而 `pinCanHost` 对无实例类型只查
`pin_supports(pin, type, "")` → step_motor 的 4 个 gpio_out 角色在 **31 个脚上全绿**
（其中 A 口 21 个必 400）。

- [x] **真机复现（现成）**：审计脚本 P1 节 —— mspm0 平台、选中
      `step_motor + huidu + motor + led_beep`，对**每一对（角色 × 板图 IO 脚）**跑前端
      镜像判据 `pinCanHost` 与真 `/api/bindings/validate` 对拍：

      ```
      mspm0：候选 (角色×脚) 744 条；实测 744 条；UI 说行 701 / UI 说不行 43
      [FAIL] P1 mspm0 UI 放行但后端拒收：115 条
        例 step_motor.STEP_MOTOR_RST2(gpio_out) → PA0
        后端：「绑定冲突：step_motor 的 4 个 gpio_out 角色（STEP_MOTOR_RST2、
        STEP_MOTOR_SLP2、STEP_MOTOR_DIR2、STEP_MOTOR_DCY2）必须绑到同一端口
        （当前 A、B）——该组角色走单端口宏（如 STEP_MOTOR_PORT），混端口编译绿运行坏」
      ```

      对照组：**stm32 600 条 UI 可配绑定全部被后端接受**（0 条误放行）；mspm0 的
      43 条「UI 说不行」也**全部**与后端一致拒收 —— 说明不是判据方向反了，而是
      mspm0 的一条**具体约束**前端没实现。
- [x] **根因（源码确认）**：后端 `pin_bindings.resolve_bindings` 在 mspm0 分支调
      `_check_mspm0_gpio_port_groups`：同一模块同类型的 gpio 角色若**默认全在同一端口**，
      则生效引脚（绑定值或默认值）必须同端口，否则 400。前端
      `ui/generate-pins.js` 的 `pinCanHost` 只镜像了「类型级 / 通道 / 实例」三层，
      **没有这一层端口组约束**（模块头注释列的口径里也没有它）。
      `step_motor` 的四个 gpio_out 默认 PB24/PB6/PB7/PB8（全 B 口）→ 后端单端口宏
      `STEP_MOTOR_PORT`；前端只看「这脚有没有 gpio_out 能力」，PA0 有 → 放行。
- [x] 判据为什么可信（三步自检）：
      1. 现象不是判据造出来的 —— 后端返回的是**逐字的中文 400 文案**，且与
         `_check_mspm0_gpio_port_groups` 的 `f"绑定冲突：{slug} 的 {n} 个 {type} 角色…"`
         模板一致；
      2. 前端判据是**照抄** `pinCanHost` 的实现（含 `pinIsTypeLevel` / `roleInstances`
         / `mspm0PwmAllowed` 三段），不是我自己编的「应该怎样」；
      3. 反向对照组（stm32 600 条全对、mspm0 UI 说不行那 43 条全对）证明判据没有
         系统性偏差。
- [x] 真机复现脚本：`tests/browser/gen-chain-audit.mjs` P 节（`node ... P`）。
- [x] **离线复现（更快、零依赖，复侦新增）**：`.scratch/gen-chain-audit/probe_port_group.py`
      —— `python .scratch/gen-chain-audit/probe_port_group.py`，秒级出「候选 / UI 说行 /
      分歧 / 按门禁分类 / 候选修法残余」，不用起服务、不用浏览器。

## 实现决策（已拍板：**方案 B**，范围 = 端口组 + 成对/通道）

用户 2026-08-xx 选定 B（后端新端点单源答「某角色此刻能绑哪些脚」），范围 = 覆盖
端口组 + 成对/通道两类（115 条归零），槽位互斥本轮不进（parity 用例实测 0 分歧）。
落地形状与代价见 `../spec-matrix.md` 与工单 04——实现中三处与原草案的差异
（`selectable` 含能力层全部三条判据 / 端口组限 mspm0 / pwm 通道过滤与对脚通道
不可省）都记在工单 04 的「实现期修正」。

**当初的三个选项（留档）**：

**A. 后端预计算，随 expand 下发**：改动最小，但约束语义仍要前后端共同理解。

**B. 新端点：后端直接答「某角色能绑哪些脚」**（选定）：前端零约束逻辑，
漂移面从结构上消掉；判据按**观测绑定的当前状态**算（收 `bindings`），故需按
(platform, slugs, bindings) 缓存。

**C. 纯前端镜像 + 跨语言对拍守卫**：零后端改动，但两处规则仍在。

## 没做（如实记录）

- 槽位互斥（`_check_slot_conflicts`）未纳入模型——parity 用例（全脚枚举）实测
  当前库 0 分歧；库变化时会当场红，届时再补一条谓词 kind。
- **组内混端口时的松弛**（已知、故意）：组内一半角色被观测到 A 口、一半在 B 口时
  该组**无解**，模型对所有角色都不给约束（宁可让用户试到第三次撞 400 文案，
  也不假红地把整组脚灰掉）；用例 `test_port_group_follows_observed_bindings` 记录此口径。
- stm32 侧同一判据实测**零分歧**（600/600），本轮未新增 stm32 专属谓词
  （端口组门禁是 mspm0 专属，已由 `test_port_group_is_mspm0_only` 钉住）。
