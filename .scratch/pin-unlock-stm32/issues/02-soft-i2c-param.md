# 02 — 软 I2C 参数化（ml_i2c / ml_oled 宏迁 pin_config.h）+ 共享端口宏门禁（机制层）

**What to build:** ml_i2c（PB10/11）与 ml_oled（PB8/9）的软 I2C 引脚宏从库内硬编码迁入 pin_config.h 注入——mpu6050 / OLED 的 I2C 角色解锁到任意 GPIO；渲染层加"共享端口宏异值 400"门禁。

**Blocked by:** 01（test_pin_bindings.py 同缝——01 合 main 后再开）

**Status:** resolved（2026-08-15 PR #77 squash merged 5d0fee2，主会话复核 + 1481 绿复跑——解锁轮四张工单全部闭环）

## 需求

1. **母版宏迁移**：`library/masters/stm32/pin_config.h` 新增 6 宏（I2C_GPIO GPIO_B / I2C_SCL_GPIO_Pin Pin_10 / I2C_SDA_GPIO_Pin Pin_11 / OLED_GPIO GPIO_B / OLED_SCL_Pin Pin_8 / OLED_SDA_Pin Pin_9——原值不变 = 默认路径语义不变）；`ml_libs/ml_i2c.h` 与 `ml_libs/ml_oled.h` 删各自三行硬编码，改 `#include "pin_config.h"`（guard `__PIN_CONFIG_H` 已存在；IncludePath `..` 已可达，勿动 uvprojx）。改母版只改仓库 `library/masters/stm32/`（`~/.contest_generator/masters/stm32/` 是旧部署副本，勿碰）。
2. **能力 token 去实例化**：`src/contest_generator/boards/stm32-min-system.json` 全部 io 脚能力集加 `i2c_scl` / `i2c_sda`（无实例）；删除 `i2c_scl:ml_i2c` / `i2c_sda:ml_i2c` / `i2c_scl:ml_oled` / `i2c_sda:ml_oled` 四类 token。软 I2C 参数化后实例无意义（总线身份在宏里不在 token 里，ADR 0011）——strict-all 机器自然降级为类型检查（`pin_capability_instances` 返回空 → 类型级），**pin_bindings.py 零改动**。boards.py 口径注释同步。
3. **oled manifest 补 pins**：`library/modules/oled/manifest.json` stm32 段补 OLED_SCL（i2c_scl，default PB8，macros [OLED_GPIO, OLED_SCL_Pin]）/ OLED_SDA（i2c_sda，default PB9，macros [OLED_GPIO, OLED_SDA_Pin]）。ml_mpu6050 manifest 不动（macros 已指向迁移目标）。
4. **pinwriter.py 共享端口宏门禁**：渲染前对 changes 分组——两条改动绑定写同一 `_GPIO/_PORT` 尾形宏且计算值不同（如 MPU6050_SCL→PA5、MPU6050_SDA→PB6 → I2C_GPIO 冲突）→ `PinBindingError` 400 中文（"共享端口宏 I2C_GPIO 被 MPU6050_SCL、MPU6050_SDA 绑到不同端口"）。只查改动项：未改同族角色的隐式漂移仍为提示语义（前端卡片已做）；同值（同端口）放行。docstring 里"宏不在 pin_config.h 大声失败"的旧判定保留（防御路径）。
5. **测试**：红证——SCL→PA5 / SDA→PB6 异口 400、SCL/SDA→PA5/PA6 同口放行；绿证——mpu6050 绑 PA5/PA6 → pin_config.h `I2C_GPIO GPIO_A` + `I2C_SCL_GPIO_Pin Pin_5` + `I2C_SDA_GPIO_Pin Pin_6`；默认绑定输出 == 新母版逐字节；test_pin_bindings.py:317-322 旧"绑定 mpu6050 到非默认脚 → 宏不在 pin_config.h 大声失败"用例改预期（现为合法绑定）；tests/test_boards.py STM32_ML_LIBS_EXPECTED 同步（i2c token 去实例化）；新增测试文件 tests/test_pin_unlock_i2c.py。
6. **真机**：2026C `--reuse-recommend --add ml_mpu6050 --bindings '{"ml_mpu6050.MPU6050_SCL":"PA5","ml_mpu6050.MPU6050_SDA":"PA6"}'` → pin_config.h 三宏变化 UV4 0 错 0 警；不配 bindings 回归（PB10/11 默认，zigbee+mpu6050 同选默认共享脚现状不拦）。

## 文件边界

- `library/masters/stm32/pin_config.h`、`library/masters/stm32/ml_libs/ml_i2c.h`、`library/masters/stm32/ml_libs/ml_oled.h`、`library/modules/oled/manifest.json`
- `src/contest_generator/boards/stm32-min-system.json`、`src/contest_generator/pinwriter.py`
- `tests/test_boards.py`、`tests/test_pin_bindings.py`（单用例更新）、`tests/test_pin_unlock_i2c.py`（新）
- 零 pin_bindings.py / generator.py / 前端改动；铁律：独立 worktree（01 合 main 后从最新 main 建）

## 验收

- [x] pytest 全绿 + mypy src 干净（1481 passed + mypy 41 文件 Success，2026-08-15 worktree pin-unlock-02 @ 29c114d）
- [x] 红证已验（异口 400 / 同口放行）+ 绿证（三宏值断言 + 默认逐字节契约对新母版成立）——tests/test_pin_unlock_i2c.py 11 用例，红证先行（缺门禁/数据/宏时 12 红 1 绿，防御用例现路径本就过）
- [x] 真机：mpu6050 绑 PA5/PA6 UV4 0 错 0 警 + pin_config.h 三宏 GPIO_A/Pin_5/Pin_6 且其余行逐字节（diff 仅 3 行）；不配回归 UV4 0 错 0 警 + pin_config.h == 新母版逐字节（zigbee+mpu6050 同选默认共享脚现状不拦）；HTTP 层异口 400 中文零产物
- [x] 独立 worktree（.claude/worktrees/pin-unlock-02，01 合 main 后从 b589786 建）+ 提交 + 推送（PR）

## Comments（2026-08-15 实施记录）

- **真机三跑**（2026C stm32，worktree 零写入启动法：AppContext 内存 replace 指向
  worktree 库目录 + GENERATE_CHECK_CACHE_DIR 复用主检出缓存 + --clarify 20 条零警告；
  证据日志主检出 .scratch/real-run/check_2026C_i2c_{bind,default,crossport}.log）：
  ① `--reuse-recommend --add ml_mpu6050 --bindings '{"ml_mpu6050.MPU6050_SCL":"PA5",
  "ml_mpu6050.MPU6050_SDA":"PA6"}'` → UV4 exit=0 0 错 0 警，产物 pin_config.h 只变
  I2C_GPIO/I2C_SCL_GPIO_Pin/I2C_SDA_GPIO_Pin 三行（GPIO_A/Pin_5/Pin_6），其余与
  母版逐字节一致；② 不配 bindings 同 8 模块 → UV4 0 错 0 警，pin_config.h == 新母版
  逐字节（PB10/11 默认，zigbee+mpu6050 共享脚不拦）；③ SCL→PA5 / SDA→PB6 异口 →
  HTTP 400 "共享端口宏 I2C_GPIO 被 ml_mpu6050.MPU6050_SCL、ml_mpu6050.MPU6050_SDA
  绑到不同端口 GPIO_A、GPIO_B"，零产物。
- **文件边界外必要改动**：tests/test_pins.py——`test_every_declaration_default_on_
  board_and_capable` 对 stm32 i2c_scl/i2c_sda 加类型级豁免（token 去实例化后
  旧"默认引脚须有实例"判据必红）+ STM32_MACRO_VALUES 钉死 6 新宏值 +
  `_master_header_defines` docstring 同步；test_boards.py STM32_ML_LIBS_EXPECTED
  PB8/9/10/11 行改类型级 token。均为结构测试随数据契约的必要同步，非超范围功能。
- **实施细节**：ml_i2c.h（GBK）/ ml_oled.h（UTF-8）字节级编辑保编码——只删 3 行
  ASCII define + 插 include，注释字节原样；板 JSON 行级变换保格式（两脚本后
  diff 恰 32 io 行语义变化）；门禁只查 `_GPIO/_PORT` 尾形宏的改动项，同值放行，
  值推导复用 `_stm32_macro_value`（零新推导逻辑）。
- **2026-08-15 合并复核**（PR #77 squash merged 5d0fee2，远端分支已删）：主会话 diff 复核——6 宏原值迁移/32 io 行 token 去实例化/门禁值与写侧同源/测试三同步全对工单；合并后 main 复跑 1481 绿 29.3s。

## 实施提示词（复制到新会话）

```
实施软 I2C 参数化工单 .scratch/pin-unlock-stm32/issues/02-soft-i2c-param.md：
1. 读工单 + .scratch/pin-unlock-stm32/spec.md（关键事实节必读）+ ADR 0011 + 最新 main
   （前置工单 01 已合）
2. 母版：pin_config.h 增 6 宏（原值不变）；ml_i2c.h / ml_oled.h 删硬编码改 include
   "pin_config.h"；只改仓库 library/masters/stm32/（旧部署副本勿碰）
3. boards/stm32-min-system.json：i2c token 去实例化（全 io 脚加 i2c_scl/i2c_sda，
   删四个带实例 token）；pin_bindings.py 零改动（strict-all 机器自然降级类型检查）
4. oled manifest stm32 段补 OLED_SCL/OLED_SDA pins 声明（macros 指向迁移宏）
5. pinwriter.py 共享端口宏门禁：同 _GPIO/_PORT 尾形宏两改动值不同 → PinBindingError 400；
   只查改动项；旧"宏不在 pin_config.h"防御保留
6. 红证先行：异口 400 / 同口放行；绿证：三宏值断言 + 默认逐字节契约（新母版）；
   test_pin_bindings.py 旧 I2C_GPIO 用例改预期；test_boards.py 能力表同步
7. 真机：2026C --reuse-recommend --add ml_mpu6050 --bindings
   '{"ml_mpu6050.MPU6050_SCL":"PA5","ml_mpu6050.MPU6050_SDA":"PA6"}'
   → pin_config.h 三宏变化 UV4 0 错 0 警 + 不配回归
8. 提交 + 推送开 PR
注意：独立 worktree（01 合 main 后建）；文件边界见工单；零 pin_bindings/generator/前端改动
```
