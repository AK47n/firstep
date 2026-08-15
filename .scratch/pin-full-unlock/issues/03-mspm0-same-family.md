# 03 — mspm0 同族实例迁移（Tier A：改写器 peripheral/port 字段 + 门禁族级化）

**What to build:** mspm0 同族外设实例间可换（UART0↔UART1、I2C0↔I2C1、TIMGx↔TIMGy、GPIO 组换端口）——实例名不动 → SysConfig 生成宏名不动 → 模块代码零改动；改写器学会改 `peripheral`/`port` 字段；step_motor 四脚同端口锁借 GPIO 组换端口解掉。

**Blocked by:** 02（pinwriter.py / pin_bindings.py 同缝——02 合 main 后再开）

**Status:** 待实施

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

- [ ] 前置验证记录（peripheral 字段变更 → sysconfig_cli 生成宏形态实证）入 Comments
- [ ] pytest 全绿 + mypy src 干净
- [ ] 红证已验 + 绿证（peripheral/port 字段断言 + 默认逐字节）
- [ ] 真机：不配回归 + UART 挪位 + GPIO 组换端口 gmake 全 0 错 + HTTP 400 零产物
- [ ] 独立 worktree + 提交 + 推送开 PR

## 实施提示词（复制到新会话）

```
实施 mspm0 同族实例迁移工单 .scratch/pin-full-unlock/issues/03-mspm0-same-family.md：
1. 读工单 + .scratch/pin-full-unlock/spec.md（关键事实节必读）+ ADR 0012 + 最新 main（前置 01/02 已合）
2. 第一步前置验证：手动改 syscfg peripheral 字段跑 sysconfig_cli，记录生成宏形态入 Comments
3. pinwriter.py：syscfg 改写器加 peripheral/port 字段改写（目标实例由绑定脚 token 推导；实例名不动）
4. pin_bindings.py：mspm0 uart/i2c 类型级（对同实例，与 02 同机制）+ pwm 同族内类型级（跨族仍 400）
   + step_motor 四脚同端口门禁
5. 板定义 mspm0-dimx.json：TIMG/UART/I2C 实例可达脚 token 全表核对
6. index.html pinCanHost：mspm0 同族脚放开镜像
7. 红证先行 + 绿证（peripheral/port 字段断言 + 生成宏值 + 默认逐字节）
8. 真机：2024H 不配回归 / IMU601↔DIGIT_UART 挪位 / step_motor 换 PA 组 / 撞实例 HTTP 400
   （gmake 全 0 错，sysconfig_cli 走通）
9. 提交 + 推送开 PR
注意：独立 worktree；文件边界见工单；零模块代码改动（同族迁移模块零改码是核心卖点）
```
