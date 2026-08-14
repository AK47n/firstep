# 02 — 绑定模型 + 双平台写侧 + 两条门禁（机制层）

**What to build:** 引脚绑定从"前端配置"到"生成产物"的整条机制：bindings 模型与校验、stm32 pin_config.h 确定性渲染器、mspm0 syscfg 改写器、两条新门禁、错误映射、API 载荷与真机验证。

**Blocked by:** pin-board-config/01（依赖 boards 数据与 manifest pins 声明）

**Status:** resolved（2026-08-14 PR #71 squash merged 3215c99，主会话复核 + 1456 绿复跑；评审修正见 Comments 尾注）

## 需求

1. **bindings 模型**（归 boards.py 或新 pin_bindings.py）：`{"<slug>.<role_id>": "<PIN>"}` 解析与校验——角色存在于选中模块声明、引脚存在于板定义（`boards.board_pin`）、能力合法（`boards.pin_supports`；**角色实例 = 默认引脚能力 token 的实例**，`boards.pin_capability_instances` 推导——enc 限同 EXTI 线号的机械实现）、必选角色允许缺省（走默认）。错误 → `PinBindingError`（登记 errors.py，400 中文文案；未登记异常 = 500 大声失败原则不破）。
2. **stm32 写侧**：`generate_project` 流程里 copytree 后按 bindings 覆写 `pin_config.h`——确定性渲染器（keil.py 确定性渲染先例）。**契约**：默认绑定（bindings 缺省或未覆盖角色）输出与迁移后母版 pin_config.h **逐字节一致**；绑定改哪几个角色，只变对应宏行。enc 角色一个绑定产出三个宏（`MOTOR_A_ENC_EXTI / _LINE / _DIR`）——宏名映射用 `PinDeclaration.macros`（manifest.py，工单 01 已备）。
3. **mspm0 写侧**：syscfg 改写器——读 mspm0.syscfg 文本，按实例名定位、只替换引脚 `$assign` 值（实例名 / 宏名 / 通道名不动——**通道名有 DCC_100_PWM2 先例**：`ti_driverlib_pwm_DCC100_CC0` 为避与 PWMAB 重名改名过，改写器碰它必炸 SysConfig），文本级解析 + 回写；引脚值来自绑定 + 能力 token 里的实例信息。**契约**：改写后实例名/宏名/通道名集合与母版一致（结构测试钉），默认绑定输出与母版 syscfg 逐字节一致。
4. **两条新门禁**入 `GENERATION_GATES`（表 + 谓词，照 categories.RULE_CATEGORIES 先例）：
   - `_check_pin_bindings`：能力合法 / 未知角色 / 未知引脚（重复绑定不拦——同引脚多角色共享合法，spec 已定）。
   - `_check_no_pin_literals_in_main`：clex 注释剥离后 main.c 不得含引脚字面量（PAx/PBx/GPIO_Pin 等——守住"骨架不内联引脚"的现状性质；注意历史产物注释里出现过 PA11 字样，必须注释剥离后判定）。
5. **API**：`/api/generate` 请求体加可选 `bindings`（缺省 = 全默认，向后兼容）；`generate_check.py` 支持 bindings 载荷（真机驱动）。
6. **测试**：渲染器确定性（默认 = 母版逐字节）；syscfg 改写 roundtrip（实例名/宏名/通道名集不变 + 目标引脚变）；**板外默认回归**（HUIDU R3/R4 未绑时其 `$assign` 不动——逐字节契约已覆盖，补显式用例；绑定到板外脚 PB4/PB5 → 400）；门禁红证（非法绑定 400 / 未知角色 400 / main.c 注入引脚字面量被拦、注释中的字样不误伤）；errors 登记结构测试（照 errors.py 反射防漏登先例）。

## 文件边界

- `src/contest_generator/`：boards.py（或新 pin_bindings.py）、generator.py（写侧挂钩 + 门禁两条）、errors.py（PinBindingError 等）、webapp.py（/api/generate 收 bindings）、新 syscfg 改写器模块（如 pinwriter.py，stm32 渲染 + mspm0 改写同住或分住自行定）
- `tests/`：新测试文件 + 既有 generate 契约测试同步（payload 形状变化）
- `.scratch/real-run/generate_check.py`：bindings 支持
- **前端零改动**（payload 兼容性保证）

## 验收

- [x] pytest 全绿 + mypy src 干净（1456 绿——1416 存量 + 40 新增；mypy src 41 文件干净）
- [x] 结构测试：默认绑定 pin_config.h 输出 == 迁移后母版逐字节；syscfg 改写后实例名/宏名集不变
- [x] 红证已验：非法绑定 / 未知角色 → 400 中文；main.c 引脚字面量被拦（注释字样不误伤）
- [x] 真机 stm32：2026C 默认 bindings 生成 UV4 0 错；**改绑定**（如 MOTOR_A_PWM 换线）→ pin_config.h 对应宏行变 → UV4 0 错
- [x] 真机 mspm0：2026H 默认 gmake 0 错；改绑定（如 LED 换脚）→ syscfg $assign 变 → gmake 0 错
- [x] 无 bindings 载荷的旧请求行为不变（回归）
- [x] 独立 worktree + 提交 + 推送

## 实施提示词（复制到新会话）

```
实施板级引脚配置机制层工单 .scratch/pin-board-config/issues/02-binding-write-gates.md：
1. 读工单 + .scratch/pin-board-config/spec.md + 工单 01 产物（boards/*.json + manifest pins）
2. bindings 模型与校验（PinBindingError 登记 errors.py，400 中文）
3. stm32 写侧：copytree 后按绑定覆写 pin_config.h——确定性渲染器，默认绑定输出与母版逐字节一致；
   enc 角色一个绑定产三个宏（宏名映射用 PinDeclaration.macros；角色实例 = 默认引脚能力 token 实例，pin_capability_instances 推导）
4. mspm0 写侧：syscfg 改写器——实例名定位、只换 $assign 引脚值、实例名/宏名不动；
   默认绑定输出与母版逐字节一致
5. 门禁两条入 GENERATION_GATES：_check_pin_bindings（能力/未知角色/未知引脚；重复不拦）、
   _check_no_pin_literals_in_main（clex 注释剥离后判定，注释字样不误伤）
6. /api/generate 加可选 bindings（缺省 = 全默认）；generate_check.py 支持 bindings
7. 验收：结构测试（逐字节契约 + 实例名集不变）+ 红证 + 真机双平台默认与改绑定各一遍
   （stm32 UV4 / mspm0 gmake 全 0 错）+ 无 bindings 旧请求回归
8. 提交 + 推送
注意：独立 worktree；前端零改动；写侧改动只影响带 bindings 的请求（缺省路径 = 旧行为逐字节）
```

## Comments

- 2026-08-14 立项（板级引脚配置 grilling 定稿；工单 01 的写侧部分拆出成张）。
- 2026-08-14 实施完成（分支 pin-board-config-02，独立 worktree）：**模型** pin_bindings.py——resolve_bindings 唯一校验出口（键格式/未知角色/未知引脚/能力/槽位），ResolvedBinding 喂写侧，PinBindingError 登记 errors.py 400 中文（结构防漏登测试自动收编）；**stm32 渲染器** pinwriter.render_pin_config——宏行级替换（head/name/sep/eol 原样保留，CRLF 母版逐字节契约）、8 种宏名尾形分派（_EXTI/_LINE/_TIM/_CH/_UART/_INST/_PORT/_GPIO/_PIN）、注释旧引脚字样同步、宏不在 pin_config.h（ml_mpu6050 的 I2C_* 住 ml_i2c.h）大声失败；**syscfg 改写器** rewrite_syscfg——默认引脚值定位槽位（母版 $assign 引脚值唯一，真库不变量测试钉）、只换 $assign 引号值、实例名/宏名/通道名集合结构测试钉（DCC100_CC0 先例防炸）、同槽位多角色绑同脚 dedupe/绑异脚 400；**门禁两条**入 GENERATION_GATES（GateContext 第 4 参，存量谓词忽略）——_check_pin_bindings（校验即 resolve，generate 预解析喂写侧 + 门禁独立再校验同纯函数）+ _check_no_pin_literals_in_main（clex 注释/字符串剥离后扫 PAx/PBx/Pin_N/GPIO_<口>/GPIO_PIN_N——前缀允许 _ 收 EXTI_PA2/GPIO_Pin_13，尾 \b 挡宏名后缀）；**API** /api/generate 可选 bindings（形状判决归域层）+ generate_check.py --bindings（JSON 字符串）。真机：stm32 2026C 默认 UV4 0 错 0 警 + 改绑定 motor.MOTOR_B_ENC→PB4（pin_config.h 与母版 diff 恰 1 行 EXTI_PA4→EXTI_PB4）UV4 0 错 0 警；mspm0 2026H 默认 gmake 0 错（2 既有母版 ovsRate 提示）+ 改绑定 LED_BEEP_LED↔KEY_START 换位（syscfg diff 恰 2 行）gmake 0 错；无 bindings 旧请求回归两平台全过（产物树门禁含两条新门禁）。红证 4 条已验（errors 漏登/渲染器丢行尾/注释误伤/any-of 放宽）。**关键裁决与发现**：① 能力校验 = strict-all（默认引脚全部实例都要支持——mspm0 PWMAB_C0 默认 PA12 双实例，any-of 会放行仅 TIMA0_C3 的 PA28 但 SysConfig 路由必炸，宁严勿假绿；PWMAB 仍可移到双实例俱有的 PA23）；② 工单文案"enc 一绑三宏"与工单 01 产物对齐：DIR 是独立角色（MOTOR_A_ENC_DIR），渲染器按 PinDeclaration.macros 逐宏驱动，等价覆盖；③ 共享宏族陷阱（LED_PORT 三灯共口 / DIP_GPIO 四拨码共口——绑一个角色会改到其它角色的共享宏）v1 不拦，接线语义用户把关，工单 03 前端可加共享宏族提示；④ **mspm0 单角色换脚必撞已占用引脚**（母版 syscfg 排针 32 IO 全占满，实证 LED→PB8 撞 STEP_MOTOR DCY2：SysConfig "Resource conflict" exit=2——机制改写正确、冲突是接线语义）——干净改法 = 双角色换位（本次验收形态）或未来"腾挪已占用角色"交互，工单 03 前端设计必读。
- 2026-08-14 主会话复核合并（PR #71 squash merged 3215c99，远端分支已删）：读码 pin_bindings.py / pinwriter.py（行级替换 + CRLF 逐字节 + 8 宏名尾形 + 槽位定位）/ generator 门禁装配（GateContext 第 4 参存量谓词零改动）/ errors 登记；主检出复跑 1456 绿 34.1s。评审修正：resolve_bindings 内两处陈旧注释"多实例任一命中"与 strict-all 代码矛盾，改"全部命中"（code 本来就是 strict-all，纯注释对齐）。**合并过程事故**：主检出 index.html 有一处未提交改动，reset --hard origin/main 时被抹掉（未进对象库不可恢复）——若用户手头有该改动副本请重新应用，与本工单代码无关。
