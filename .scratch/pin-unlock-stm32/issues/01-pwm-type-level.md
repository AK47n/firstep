# 01 — stm32 pwm 类型级校验 + 骨架定时器冲突门禁 + 前端镜像（机制层）

**What to build:** stm32 的 pwm 角色从 strict-all 实例锁放宽为类型级（任意 pwm 脚可绑，实例从绑定引脚推导喂渲染器）；新增"骨架定时器 × PWM 绑定实例"冲突门禁；前端 pinCanHost 同步镜像。

**Blocked by:** 无（基于最新 main）；同缝提示——`.scratch/index-html-ui-redo/issues/01` 也动 index.html，本单先行（功能优先）、redo 其后 rebase。

**Status:** resolved

## 需求

1. **pin_bindings.py 类型级分支**（128-147 行区域）：`platform == stm32 and declaration.type == "pwm"` → 绑定脚须有 ≥1 个 `pwm:*` token（`pin_capability_instances(bound, "pwm")` 非空），`instances` = **绑定引脚**的实例元组（喂渲染器写 TIM/CH 宏）；否则保持现有 strict-all 原逻辑逐字节不动（mspm0 与 stm32 其余类型）。单实例假设保持（stm32 每脚单 pwm token，`_require_instance` 防御保留）。docstring / 报错文案同步更新（"角色实例随默认引脚锁定"等字样）。
2. **generator.py 新门禁** `_check_timer_instance_conflicts` 入 GENERATION_GATES：main_c 经 clex 注释/字符串剥离（同 `_check_no_pin_literals_in_main` 先例）后，扫 `tim_interrupt_ms_init(TIM_x`（x ∈ 2/3/4，兼容 `TIM_2`/`TIM2` 两写法），与绑定 pwm 角色的 TIM 实例（instances 前段，如 `TIM3_CH1` → 3）冲突 → 抛新错误类（如 `TimerConflictError`）登记 errors.py（400 中文："PWM 绑定 TIM3_CH1 与骨架调度定时器 TIM_3 冲突"）。**只查用户绑定**（无 bindings 或绑定=默认值不触发——默认组合冲突不拦，现状性质 spec 已留痕）；识别不到（LLM 换写法）不拦——漏报优于误报。
3. **index.html pinCanHost 镜像**（1434-1449 行区域）：`chosenPlatform === "stm32" && decl.type === "pwm"` → 引脚能力集含任意 `pwm:*` token 即 canHost（灰显原因文案："该脚不支持角色类型 pwm"）；其余平台/类型走现有 strict-all。菜单/高亮/默认被占用警示自动跟着 pinCanHost 走（零其它前端改动）；卡片 strict-all 注释同步更新。
4. **测试**：红证先行——绑无 pwm 脚（如 PB4）拒 / 骨架含 `tim_interrupt_ms_init(TIM_3, 10)` + 绑 `MOTOR_A_PWM→PA6`（TIM3_CH1）→ 400 / 注释中的 tim_interrupt_ms_init 字样不误伤（红证后补门禁再转绿）；绿证——`MOTOR_A_PWM→PA6` 合法且 `instances == ("TIM3_CH1",)`、`→PB6`（TIM4_CH1）合法、mspm0 strict-all 原用例全保持。test_pin_bindings.py:603-617 旧非法样例（MOTOR_A_PWM→PA6 当非法）换新非法样例；test_generator.py 门禁表计数/顺序测试同步；主会话板图程序化验收脚本若有 strict-all UI 断言需同步（stm32 pwm 部分）。
5. **真机**：2026C `--reuse-recommend --add motor --bindings '{"motor.MOTOR_A_PWM":"PB6"}'` → pin_config.h `MOTOR_A_PWM_TIM TIM_4` / `MOTOR_A_PWM_CH TIM4_CH1 /* PB6 */`（默认 TIM_2/TIM2_CH1 恰两行变化）UV4 0 错 0 警；不配 bindings 回归（TIM_2/TIM2_CH1 原值 UV4 0 错）；骨架 TIM_3 冲突场景红证走 HTTP 层（400 detail 中文）。

## 文件边界

- `src/contest_generator/pin_bindings.py`、`generator.py`、`errors.py`、`static/index.html`
- `tests/test_pin_bindings.py`、`tests/test_generator.py`（门禁表）+ 如需新测试文件自定
- 零 boards 数据改动、零 pinwriter 功能改动（docstring 可在 02 统一更新，本单不碰 pinwriter.py）
- 铁律：独立 worktree（从最新 main 建）；与 03/04 并行（文件不重叠）；8000 端口真机验证错峰

## 验收

- [x] pytest 全绿 + mypy src 干净（基线以当时 main 为准）
- [x] 红证已验（无 pwm 脚拒 / TIM3 冲突 400 / 注释字样不误伤）+ 绿证（PA6/PB6 合法、instances 随绑定引脚、mspm0 strict-all 保持）
- [x] node --check 过 + jsdom/浏览器：stm32 菜单 MOTOR_A_PWM 在 PB6（TIM4_CH1）可绑、PA6 可绑、PB4 不列（无 pwm token）；mspm0 菜单 PWMAB_C0 在 PA28 仍灰显
- [x] 真机：2026C 改绑定 PB6 → pin_config.h TIM_4/TIM4_CH1 UV4 0 错；不配回归；HTTP 400 冲突文案
- [x] 独立 worktree + 提交 + 推送（PR）

## 实施提示词（复制到新会话）

```
实施 stm32 PWM 类型级解锁工单 .scratch/pin-unlock-stm32/issues/01-pwm-type-level.md：
1. 读工单 + .scratch/pin-unlock-stm32/spec.md（关键事实节必读）+ ADR 0011 + 最新 main 的
   pin_bindings.py / generator.py / index.html pinCanHost（1434 行附近）
2. pin_bindings.py：stm32+pwm 类型级分支（instances 从绑定引脚推导）；其余 strict-all 原逻辑
   逐字节不动；docstring/报错文案同步
3. generator.py 新门禁 _check_timer_instance_conflicts 入 GENERATION_GATES：clex 剥离 main_c 后
   扫 tim_interrupt_ms_init(TIM_x（x∈2/3/4，TIM_2/TIM2 两写法）× 绑定 pwm 实例前段冲突 → 400；
   新错误类登记 errors.py；只查用户绑定、识别不到不拦
4. index.html pinCanHost 镜像：stm32+pwm → 任意 pwm:* token 即 canHost；灰显文案与
   strict-all 注释同步；其余零改动
5. 红证先行再落绿：无 pwm 脚拒 / TIM3 冲突 400 / 注释字样不误伤；绿证 PA6/PB6 合法、
   mspm0 strict-all 保持；test_pin_bindings.py 旧非法样例换新；test_generator.py 门禁表同步
6. 真机：2026C --reuse-recommend --add motor --bindings '{"motor.MOTOR_A_PWM":"PB6"}'
   → pin_config.h TIM_4/TIM4_CH1 UV4 0 错 0 警 + 不配回归（8000 端口若被并行会话占用请错峰）
7. 提交 + 推送开 PR
注意：独立 worktree（从最新 main 建）；文件边界见工单；pinwriter.py 不碰（02 统一）；
同缝 index-html-ui-redo/01 在后 rebase
```

## Comments

- 2026-08-15 立项（stm32 引脚解锁 grilling 定稿，189d9df）。
- 2026-08-15 实施完成（分支 pin-unlock-01，独立 worktree 从 origin/main）：**pin_bindings.py 类型级分支**——stm32+pwm 实例随绑定引脚推导（pin_capability_instances(bound)，无 pwm token 拒"不支持角色类型 pwm"），strict-all 原逻辑入 else 逐字节不动；**generator.py 门禁 _check_timer_instance_conflicts** 入 GENERATION_GATES（pin_bindings 之后）——clex 注释/字符串剥离后扫 `tim_interrupt_ms_init(TIM_?([234])`（TIM_2/TIM2 两写法，ml_tim 只注册 2/3/4）× 用户改动过的绑定（pin ≠ default，no-op 不触发）pwm 实例前段 `TIM([234])_`（mspm0 TIMG0/TIMA0 形态自然不命中）→ TimerConflictError 登记 errors.py 400 中文；**index.html pinCanHost 镜像**——stm32+pwm 任意 pwm:* token 即 canHost（pinListsType 复用），pinMissReason 同步"该脚不支持角色类型 pwm"，卡片/能力判定注释同步，其余零改动。红证先行实录：PA6 旧 strict-all 拒（实例锁文案）+ PB4 旧文案非类型级 + 门禁 ImportError 收集红；绿证 1464 全绿 32.1s + mypy src 41 文件干净 + node --check（脚本段提取）过 + jsdom 冒烟 8/8（PB6/PA6 可绑、PB4 不列、mspm0 PA28 仍灰显 PA23 可绑、stm32 uart 严格保持）。真机（worktree 服务 8000 + 缓存复用）：2026C `--reuse-recommend --add motor --bindings {"motor.MOTOR_A_PWM":"PB6"}` → pin_config.h `MOTOR_A_PWM_TIM TIM_4` / `MOTOR_A_PWM_CH TIM4_CH1 /* PB6 */` UV4 0 错 0 警；不配 bindings 回归 → TIM_2/TIM2_CH1 原值 UV4 0 错 0 警；HTTP 层红证 `tim_interrupt_ms_init(TIM_3, 10, 0)` 骨架 + PA6 绑定 → 400 detail "PWM 绑定 TIM3_CH1（motor.MOTOR_A_PWM）与骨架调度定时器 TIM_3 冲突…" 且零产物目录。
