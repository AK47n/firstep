# 04 — 后端：绑定判据端点 `/api/bindings/matrix`（单源下发「角色此刻能绑哪些脚」）

**状态：** resolved（2026-08-xx；实现在 `src/contest_generator/pin_bindings.py` +
`webapp.py` 路由，用例 `tests/test_bindings_matrix.py` 15 条全绿）

## 交付的契约（实现后定稿，与最初草案的差异见「实现期修正」）

```
POST /api/bindings/matrix
请求  {platform, slugs: [...], bindings?: {"<slug>.<role>": "<PIN>"}}
响应  {roles: [{role, type, default, selectable: [PIN...], constraint}...]}

constraint = null
           | {kind: "port",     port: "B", reason: "…"}
           | {kind: "instance", instances: [...], pair: "<slug>.<role>", reason: "…"}
```

- `selectable` = **自身能力层**选得出来的脚（前端当候选集；与 `resolve_bindings`
  能力层逐条同口径，三条判据见下）；
- `constraint` = **跨角色**谓词，前端只求值、不复制规则：
  - `port`：同模块同类型 gpio 组（**mspm0 专属**），候选脚端口必须 == 同组其余角色
    有效脚的端口（单元素；多元素 = 该组此刻无解 → `null`，不假红）；
  - `instance`：**pwm 两通道**——候选脚 pwm 实例集须与对脚有效实例集**按基名**相交
    （`instances` 是对脚的完整实例集，不过滤通道）。
- 判据单源：`_strict_all_instances`（能力层）+ `_port_group_roles`（端口组）+
  `_role_pair_mate`（成对）都由门禁与模型**共用**；`resolve_bindings` 的能力层分支
  已改为调 `_strict_all_instances`（原来那段内联代码是第二处实现）。

## 实现期修正（每条都是被对拍/用例当场抓出来的，记下来防重犯）

1. **`eligible` → `selectable`**：原草案只下发「类型命中的脚」，但**能力层还有两条**
   会挡住合法候选——strict-all（默认脚实例全中）与 mspm0 带通道 pwm 的「实例须带
   `_C0` 尾」（`_mspm0_pwm_instances`）。缺它们 = 74 条假绿，实测被对拍用例抓出。
2. **端口组是 mspm0 专属**：`resolve_bindings` 只在 mspm0 分支调
   `_check_mspm0_gpio_port_groups`；给 stm32 也加 port 谓词会误挡
   `config.DIP0-3`（默认全 PB12-15）= 一批假红。
3. **pwm 对脚实例不过滤通道**：门禁按**基名**交集，预过滤 `_C0` 会让交集恒空 →
   `PWMAB_C0/C1` 全不可绑。
4. **uart/i2c 成对不叠谓词**：其「成对同实例」实为「脚自带实例集一致」，模型用每脚
   实例集表达（`selectable` 收窄）——叠跨角色谓词反而会挡住合法换位。
5. **`_pwm_channel_suffix`**：`_pwm_role_channel` 返回**含 C 的尾**（'C0'），
   比 `_C0` 而不是 `_C0` 再拼一次 C（实现中途多拼一层，通道过滤恒空）。

## 测试（`tests/test_bindings_matrix.py`，15 条）

- 形状 / 覆盖 / 三平台分支；端口组（默认、混端口、随观测、mspm0 专属）；
  成对（pwm 双向、随观测、uart 不叠谓词）；
- **单源对拍**：744（mspm0）+ 600（stm32）条候选逐条比 `selectable`+谓词 ×
  `resolve_bindings` —— 放行但后端拒 = 0、挡掉但后端收 = 0；
- **锚**：工单 03 的 115 条分歧全被挡住、后端拒的 158 条全被挡住、候选规模 744；
- **贪心走链**：逐角色绑脚，每步累积态回验后端（假绿在连走时最容易漏）；
- 性能：全库矩阵 < 1s。

## 不做（本轮范围外）

- 槽位互斥（`_check_slot_conflicts`）不进模型（parity 用例会当场抓出来，目前 0 分歧）。
- 不改 validate / auto / generate 的请求响应形状。
