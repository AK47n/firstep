# 02 — 绑定模型 + 双平台写侧 + 两条门禁（机制层）

**What to build:** 引脚绑定从"前端配置"到"生成产物"的整条机制：bindings 模型与校验、stm32 pin_config.h 确定性渲染器、mspm0 syscfg 改写器、两条新门禁、错误映射、API 载荷与真机验证。

**Blocked by:** pin-board-config/01（依赖 boards 数据与 manifest pins 声明）

**Status:** 待实施

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

- [ ] pytest 全绿 + mypy src 干净
- [ ] 结构测试：默认绑定 pin_config.h 输出 == 迁移后母版逐字节；syscfg 改写后实例名/宏名集不变
- [ ] 红证已验：非法绑定 / 未知角色 → 400 中文；main.c 引脚字面量被拦（注释字样不误伤）
- [ ] 真机 stm32：2026C 默认 bindings 生成 UV4 0 错；**改绑定**（如 MOTOR_A_PWM 换线）→ pin_config.h 对应宏行变 → UV4 0 错
- [ ] 真机 mspm0：2026H 默认 gmake 0 错；改绑定（如 LED 换脚）→ syscfg $assign 变 → gmake 0 错
- [ ] 无 bindings 载荷的旧请求行为不变（回归）
- [ ] 独立 worktree + 提交 + 推送

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
