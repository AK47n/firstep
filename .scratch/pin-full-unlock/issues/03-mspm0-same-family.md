# 03 — mspm0 同族实例迁移（Tier A：改写器 peripheral/port 字段 + 门禁族级化）

**What to build:** mspm0 同族外设实例间可换（UART0↔UART1、I2C0↔I2C1、TIMGx↔TIMGy、GPIO 组换端口）——实例名不动 → SysConfig 生成宏名不动 → 模块代码零改动；改写器学会改 `peripheral`/`port` 字段；step_motor 四脚同端口锁借 GPIO 组换端口解掉。

**Blocked by:** 02（pinwriter.py / pin_bindings.py 同缝——02 合 main 后再开）

**Status:** resolved（2026-08-15 PR #80 squash merged 77af949，主会话复核 + 1528 绿复跑）

## 需求

1. **前置验证（第一步）**：手动改一份 mspm0.syscfg 的 `peripheral` 字段（如 IMU601 UART0→UART1）+ 对应 $assign 引脚，跑 sysconfig_cli（C:/ti/ccs2050/ccs/utils/sysconfig 相关，命令见 makefiles.py）——确认生成 ti_msp_dl_config.h 的宏形态（IMU601_INST 值随实例变、宏名不变、IRQ 宏 IMU601_INST_INT_IRQN 随实例）+ 通道名不重名 + Resource conflict 行为。结果记录进工单 Comments 再实施。
2. **pinwriter.py syscfg 改写器升级**：除 $assign 引脚值外，支持改 `peripheral` 字段（目标实例由绑定脚 token 推导——如绑 IMU601 到 PA8/PA9（UART1 脚）→ `IMU601.peripheral = "UART0"` 改 `"UART1"`）与 GPIO 组 `port` 字段（四脚绑定全落同端口 → 组 port 字段改）；实例名/宏名/通道名/其余行逐字节不动；文本无变化不落盘契约保持。
3. **pin_bindings.py 门禁族级化（mspm0）**：uart/i2c 类型级（TX/RX 或 SDA/SCL 对同实例交集——机制与 02 同款复用，平台通用）+ 实例冲突门禁同口径（绑定 × 未绑定默认 → 400；IMU601=UART0、DIGIT_UART=UART1 默认不冲突）；pwm **同族内**类型级（绑定脚 pwm token 实例族 == 默认实例族 → 合法；跨族仍 400，04 才放开）；gpio 组角色加**同端口门禁**（step_motor 四脚绑定 port 不一致 → 400 中文）。
4. **板定义数据核对**（mspm0-dimx.json）：排针上 TIMG 各实例（TIMG0/TIMG12…）通道可达脚全表核对补 token；UART0/UART1、I2C0/I2C1 引脚对 token 核对。既有 token 不动为原则。
5. **index.html pinCanHost 镜像**：mspm0 uart/i2c/pwm 同族脚放开（灰显集 = 无该类型 token 的脚）。
6. **测试**：红证先行（改写器缺字段改写时换实例被拦/产物仍是旧 peripheral / 同端口 400）；绿证——IMU601 换 UART1 脚对 → syscfg peripheral 字段变 + $assign 变 + 生成宏 IMU601_INST 值变（真机 gmake 编译过）+ step_motor 四脚换 PA 组 → port 字段变 + 编译；默认不配 == 母版逐字节；新增 tests/test_pin_unlock_mspm0_same.py。
7. **真机**：2024H `--reuse-recommend` ①不配回归 gmake 0 错 + syscfg == 母版逐字节；②绑 IMU601 TX/RX 到 UART1 实例脚 + DIGIT_UART 同请求挪位（避免实例冲突）→ gmake 0 错 + 产物 syscfg 字段断言 + ti_msp_dl_config.h 宏值断言；③step_motor 四脚绑 PA 组同端口 → gmake 0 错；④单角色撞实例 HTTP 400 零产物。运行级用户上板自验。

## 文件边界

- `src/contest_generator/pinwriter.py`、`src/contest_generator/pin_bindings.py`、`src/contest_generator/errors.py`、`src/contest_generator/boards/mspm0-dimx.json`（token 核对）
- `index.html`（pinCanHost）
- `tests/test_pin_bindings.py`、`tests/test_pins.py`（如涉豁免）、`tests/test_pin_unlock_mspm0_same.py`（新）
- 零模块代码 / 母版 syscfg / stm32 侧改动；铁律：独立 worktree（02 合 main 后从最新 main 建）

## 验收

- [x] 前置验证记录（peripheral 字段变更 → sysconfig_cli 生成宏形态实证）入 Comments
- [x] pytest 全绿 + mypy src 干净（1528 passed + mypy 41 文件 Success）
- [x] 红证已验 + 绿证（peripheral/引脚字段断言 + 默认逐字节）——tests/test_pin_unlock_mspm0_same.py 14 用例
- [x] 真机：不配回归 + UART 挪位 + GPIO 组换端口 gmake 全 0 错 + 400 零产物（直接 generate + gmake，证据 .scratch/real-run/tierA_realrun.log）
- [x] 独立 worktree（.claude/worktrees/pin-full-unlock-03，02 合 main 后从 6c38df5 建）+ 提交 + 推送开 PR #80

## 前置验证（2026-08-15，sysconfig_cli 1.27.0 + mspm0_sdk_2_11_00_07）

1. **peripheral 字段变更实证**：母版 syscfg 副本做 UART 换位（IMU601
   UART0→UART1 + PA8/PA9，DIGIT_UART UART1→UART0 + PA28/PA31）跑
   sysconfig_cli → 0 错 2 警（警 = 既有 ovsRate 建议）。生成
   ti_msp_dl_config.h 断言：`IMU601_INST` 宏名不变、值 UART0→UART1；
   `IMU601_INST_IRQHandler` = UART1_IRQHandler、`IMU601_INST_INT_IRQN` =
   UART1_INT_IRQn；GPIO 宏名不变、引脚宏值跟随 $assign。**宏名不动 →
   模块代码零改动成立**。
2. **Resource conflict 实证**：只把 IMU601 挪 UART1（DIGIT_UART 留 UART1）
   → sysconfig_cli `error: DIGIT_UART peripheral.$assign: Resource conflict
   — UART1 is already in use by IMU601`。生成门禁同语义 400 提前拦截成立。
3. **GPIO 组 port 字段实证**：最小 syscfg 只放 STEP_MOTOR 四脚全 GPIOA →
   生成 `#define STEP_MOTOR_PORT (GPIOA)`——**SysConfig 由组内引脚 $assign
   自动推导组端口，母版无 port 字段也无需写侧新增**（工单需求 2 的
   "port 字段改"按实证改为零 port 改动，写侧仍只碰 $assign）。

## 实施记录（2026-08-15，worktree pin-full-unlock-03）

- **pin_bindings.py**：mspm0 uart_tx/uart_rx/i2c_scl/i2c_sda 入类型级
  （实例随绑定脚推导）；`_check_uart_tx_rx_pairs` 泛化为
  `_check_paired_role_instances`（uart TX/RX + i2c SCL/SDA 平台通用交集
  校验）；mspm0 pwm 同族内类型级（角色 id 通道尾 `_C0`/`_C1` 从默认引脚
  实例推族，绑定脚须同族同通道，跨族 400 文案点名"工单 04 才放开"）；
  `_check_mspm0_gpio_port_groups`（数据判据：同模块同类型 gpio 角色默认
  全同端口 → 有效脚必须同端口——现库唯一命中 step_motor 四脚，DC_MOTOR /
  HUIDU / 灰度默认混端口不查）。
- **pinwriter.py**：`_SYSCFG_ASSIGN_RE` 增 path 捕获；
  `rewrite_syscfg` 对 uart/i2c/pwm 绑定在换引脚 $assign 后，按同实例路径
  定位 `peripheral.$assign` 行换值（当前值与候选实例同值 = 不写，最小
  改动）；多实例候选优先匹配母版现值、否则取首个。gpio 组零 port 改动
  （前置验证 3）。
- **generator.py**：`_check_uart_instance_conflicts` 平台守卫放开到
  stm32 + mspm0（同口径：绑定 × 未绑定默认 400；IMU601=UART0、
  DIGIT_UART=UART1 默认不冲突）。
- **index.html**：`pinCanHost` / `pinMissReason` 镜像 mspm0 uart/i2c
  类型级 + pwm 同族灰显（跨族文案"暂未开放"）。
- **板定义数据核对**：mspm0-dimx.json 现有 token 已覆盖本轮所需——
  UART0/UART1/I2C0/I2C1 引脚对、TIMG0/TIMG6/TIMG7/TIMG8/TIMG12 通道
  可达脚全表俱在（核对脚本 .scratch/real-run/tierA_board_check.py），
  既有 token 不动，零新增。
- **测试**：红证已验（缺类型级 / 交集空 / 跨族 400 / step_motor 异口 400 /
  单角色撞实例 400）——tests/test_pin_unlock_mspm0_same.py 14 用例；
  test_pin_bindings.py 旧 mspm0 pwm strict-all 用例改同族类型级预期
  （PA23 合法实例 = 候选列表、PB18 跨族 400）。全量 1528 passed +
  mypy src 41 文件 Success。
- **真机**（直接 generate + gmake，不经 web 服务；证据
  .scratch/real-run/tierA_realrun.log，GMAKE=ccs2050/utils/bin/gmake.exe）：
  ① 2024H 十模块不配回归——syscfg == 母版逐字节 + gmake 0 错 0 警
  11.9s；② +digit_uart UART 换位（IMU601→UART1 PA8/PA9、DIGIT_UART→
  UART0 PA28/PA31）——syscfg peripheral/引脚六字段断言 + gmake 0 错 0 警
  + ti_msp_dl_config.h `IMU601_INST UART1` / `DIGIT_UART_INST UART0` 宏值
  断言；③ +step_motor 四脚换 GPIOA（PA15-18）——**必要连带换位**：LED_BEEP
  →PB24、DC_MOTOR AA/AB/AIN2→PB6/PB7/PB8（原 step_motor 四脚让出的 PB 脚
  恰好接住 PA 组原住户；只绑 step_motor 会撞 4 处 Resource conflict，已用
  sysconfig_cli 实证）——syscfg 八字段断言 + gmake 0 错 0 警 +
  ti_msp_dl_config.h `STEP_MOTOR_PORT (GPIOA)` 断言；④ 单角色 IMU601→UART1
  → UartInstanceConflictError 400 中文 + 零产物（与 web 400 同源）。

## Comments

- 2026-08-15 开工（Status claimed，主检出 6c38df5 建 worktree）。
- 工单文件边界实际改动：`src/contest_generator/static/index.html`（工单写
  `index.html`，仓库实际路径带 static/）；errors.py 零新增（复用
  PinBindingError / UartInstanceConflictError）；boards/mspm0-dimx.json
  零改动（核对结论 = 无需补 token）。
- **合并复核**（PR #80 squash merged 77af949，主会话）：diff 逐项对工单——
  pin_bindings 类型级分支（mspm0 uart/i2c 入类型级，实例随绑定脚；pwm 同族
  通道推族逻辑：id 尾 `_C0`/`_C1` 滤默认实例 → 族集合，绑定脚须同族同通道，
  PA23 候选 TIMG8/TIMG7/TIMG0_C0 全随绑定推导、PB18 跨族 400 文案正确）；
  成对角色同实例校验泛化（uart + i2c，平台通用，stm32 回归不受影响）；
  gpio 同端口门禁数据判据（默认全同端口才查——现库唯一命中 step_motor，
  DC_MOTOR/HUIDU/灰度默认混端口不误伤）；generator 门禁平台放开
  （mspm0 默认 IMU601=UART0、DIGIT_UART=UART1，单角色换实例 400 语义与
  sysconfig_cli Resource conflict 实证一致）；pinwriter peripheral 行按
  path_index 定位 + 候选优先匹配现值（最小改动契约）；index.html 镜像同族
  灰显。偏差留痕理由成立：① GPIO 组零 port 改动——前置验证 SysConfig 由
  组内 $assign 自动推导 STEP_MOTOR_PORT；② 真机场景 ③ 必要连带换位
  LED_BEEP/DC_MOTOR 三脚——只绑 step_motor 会撞 4 处 Resource conflict
  （已实证），连带换位是唯一 gmake 绿解；③ 工单写 index.html、仓库实际
  static/index.html。合并后 main 复跑 1528 绿 33.8s + mypy src 41 文件
  干净。worktree pin-full-unlock-03 照例保留。
