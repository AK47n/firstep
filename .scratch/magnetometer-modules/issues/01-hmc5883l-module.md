# 01 — hmc5883l 模块：双平台完整驱动 + 生成链路可用

**要做什么：** 用户在做「电子罗盘/航向角」类赛题时，能选中 `hmc5883l` 并生成出**打开即编译**的工程：默认脚自动分配、工程内落 `hmc5883l.c/.h`（mspm0）或 `hmc5883l_stm32.c/.h`（stm32）、母版 `mspm0.syscfg` 带 `HMC5883L` GPIO 实例、stm32 母版 `pin_config.h` 带四宏；调用 `hmc5883l_init()` 能当场分辨「总线不通」与「器件型号不符」，`hmc5883l_read()` 出三轴 16 位有符号值（已符号扩展），`hmc5883l_read_heading()` 出 0–360° 航向（可传硬铁偏移）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `library/modules/hmc5883l/manifest.json` 与 `code/hmc5883l.{c,h}`、`code/hmc5883l_stm32.{c,h}` 齐备，slug = `hmc5883l`（库内惯例，不带 `ml_` 前缀；旧文件名 `ml_hmc5883l` 只作溯源）
- [x] mspm0 母版 `mspm0.syscfg` 新增 `HMC5883L` GPIO 实例（SCL=PB6 / SDA=PB7，两脚均 OUTPUT）
- [x] stm32 母版 `pin_config.h` 新增 `HMC5883L_SCL_GPIO/_PIN`、`HMC5883L_SDA_GPIO/_PIN`（默认 PA6/PA7 = 既有软 I2C 总线）
- [x] API：`hmc5883l_init()` 返回 0/1（总线无应答）/2（ID 不符）；`hmc5883l_read(int16_t*,int16_t*,int16_t*)`；`hmc5883l_read_heading(float*,int16_t,int16_t)`；头文件暴露纯函数 `hmc5883l_heading_from_xy(float x, float y)` 供单测
- [x] 六条缺陷防回潮断言全绿：① 读地址 = `HMC5883L_ADDR_READ` 且 ≠ 写地址；② 器件寄存器序宏 = X/Z/Y（DOX/DOZ/DOY）；③ 读数做 `(int16_t)` 符号扩展；④ 无声明即弃的 `yaw_hmc` 式死全局；⑤ CRA 写值 ∈ {0x70,0x78} 合法集；⑥ init 必读 ID 三字节（H/4/3）且不符返回 2
- [x] `tests/test_module_hmc5883l.py` 照 `test_module_bh1750.py` 模板：manifest 形状、宏落母版、mspm0 实例、双平台单选生成、代码守卫、航向角纯函数单测
- [x] pytest 本件全绿；`verified` 暂 false（由 04 翻牌），`hardware_bound` = false，notes 如实写「未上板」

**结论（工单 01 已 resolved，2026-09-12）**：`library/modules/hmc5883l`（双平台四文件 + manifest）落地；六条缺陷防回潮断言全绿；`tests/test_module_hmc5883l.py` 10 例通过（含 **gcc 真编译真执行**的航向角数值验证——编译真源文件 + 最小桩头，与 math.atan2f 十二点比对，容差 0.05°）。编译矩阵由工单 04 翻牌（四组 0 error / 0 warning），verified 已回写 true。
