# 01 — C 类核对（servo/motor/ml_mpu6050/0-96-iic——stm32 线收官第一段）

**要做什么：** 地阔星 C 类 7 页 4 slug（库已有 stm32 条目/母版内嵌）逐页对照——芯片/总线/地址/寄存器/时序/换算/默认脚/页面缺陷 vs 库内实现与 notes；核对结论写入 `.scratch/wiki-stm32-batch11/核对报告.md`：一致即确认；**实质差异才改**（高置信 + 具体建议，改动最小化——优先 notes 补充；代码改动须重跑矩阵）。

**状态：** resolved（2026-09-08 实施完成，commit 2eb39d38）。

**实施清单：**
- [x] servo（control--16-ch-servo-drive-module.md）：对照错位非缺陷（页面 = PCA9685 16 路 → 库内真实对应 pca9685 模块——其 notes 已记录页面 7 条缺陷；servo 语义同源页 = sg90（50Hz/0.5-2.5ms/0-180° 逐项吻合））→ servo notes 补映射说明（16 路走 pca9685）；**本收尾补 stm32 条目 kit/source_url**（sg90 dkx 原页——溯源缺口）
- [x] motor（control--tb6612-motor-drive-module.md）：超集/默认脚体系差异无事实矛盾（PWM 均 1kHz、正转极性一致）→ notes 订正「21F 原值编码器 PA2/PA4 + 方向 PA3/PA5」已过期——现默认 A=PB5/PB4、B=PA4/PA5（离 PA2/PA3 让位 DEBUG_UART）；**本收尾补 stm32 条目 kit/source_url**（tb6612 dkx 原页）
- [x] ml_mpu6050（sensor--mpu6050-six-axis-sensor.md）：多项实质差异 → 必改 1 条 **ml_mpu6050.h TEMP_OUT_H 0x65→0x41**（非定义寄存器——原注释「与 ACCEL_YOUT_L 撞值」措辞订正）+ notes 补四条（I2C_Init 前置/页面缺陷清单/50Hz vs 200Hz/DMP 欧拉角 stm32 无对应）；**本收尾补 .h 前置注释行**（使用前先调 I2C_Init()——页面脚 PB8/PB9 未照抄）
- [x] 0-96-iic（screen--0-96-iic-single-screen.md）：事实层一致（SSD1306 128×64 软 I2C 0x78、序列等价）→ oled notes 补两行（页面默认脚 PB10/11 未照抄；页面四档字号与 OLED_Refresh 在 stm32 无对应——仅 8×16 直写）

**结论（2026-09-08 + 2026-09-12 终局补缺）**：四件全部无事实矛盾需改实现代码（ml_mpu6050.h 常量订正除外——已改）；核对结论见 `核对报告.md`；终局收尾补：servo/motor kit+source_url（C 类溯源缺口）、ml_mpu6050.h 前置注释行（核对报告建议②落地）。
