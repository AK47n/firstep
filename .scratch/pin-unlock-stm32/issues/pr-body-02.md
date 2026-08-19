软 I2C 参数化 + 共享端口宏异值门禁（工单 `.scratch/pin-unlock-stm32/issues/02`，ADR 0011 决策 3/4）

## 改动

**母版**（`library/masters/stm32/`，旧部署副本未碰）
- `pin_config.h` 增 6 宏（`I2C_GPIO` / `I2C_SCL_GPIO_Pin` / `I2C_SDA_GPIO_Pin` / `OLED_GPIO` / `OLED_SCL_Pin` / `OLED_SDA_Pin`，原值不变 = 默认路径语义不变）
- `ml_i2c.h` / `ml_oled.h` 删硬编码三行改 `#include "pin_config.h"`（GBK/UTF-8 字节级迁移，注释原样保留）

**数据**
- `stm32-min-system.json`：i2c token 去实例化——全 32 io 脚加类型级 `i2c_scl`/`i2c_sda`，删 `i2c_scl:ml_i2c` 等四类实例 token；**pin_bindings.py 零改动**（strict-all 机器自然降级类型检查）
- `oled` manifest stm32 段补 `OLED_SCL`/`OLED_SDA` pins 声明（macros 指向迁移宏）

**机制**（`pinwriter.py`）
- 共享端口宏异值门禁：同 `_GPIO/_PORT` 尾形宏两条改动绑定计算值不同（如 SCL→PA5、SDA→PB6 都写 `I2C_GPIO`）→ `PinBindingError` 400 中文；只查改动项，同值（同端口）放行
- 旧"宏不在 pin_config.h 大声失败"防御保留

## 验收

- pytest 1481 passed + mypy src 41 文件干净
- 红证先行：异口 400 / 同口放行（`tests/test_pin_unlock_i2c.py` 11 用例）；绿证：三宏值断言 + 默认逐字节契约（新母版）
- 真机 2026C（`--reuse-recommend --add ml_mpu6050`）：
  - 绑定 `{"ml_mpu6050.MPU6050_SCL":"PA5","ml_mpu6050.MPU6050_SDA":"PA6"}` → UV4 0 错 0 警，产物 pin_config.h 只变三行（`GPIO_A`/`Pin_5`/`Pin_6`），其余与母版逐字节一致
  - 不配 bindings 回归 → UV4 0 错 0 警，pin_config.h == 新母版逐字节（PB10/11 默认，zigbee+mpu6050 同选共享脚现状不拦）
  - 异口（SCL→PA5 / SDA→PB6）→ HTTP 400 中文零产物

证据日志：`.scratch/real-run/check_2026C_i2c_{bind,default,crossport}.log`（主检出，gitignored）
