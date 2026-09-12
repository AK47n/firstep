# 02 — qmc5883l 模块：双平台完整驱动 + 生成链路可用

**要做什么：** 用户手里买到的是市面上常见的 QMC5883L 电子罗盘模块（HMC5883L 已停产，市售多为此件）时，能选中 `qmc5883l` 生成出**打开即编译**的工程，并得到与 `hmc5883l` 同名同语义的 API——换芯片只改头文件名。QMC 的寄存器表与 HMC 完全不同，故独立成件、独立验收。

**被谁阻塞：** 无——可立即开始（与 01 文件零交叉，可并行）。

**状态：** resolved

- [x] `library/modules/qmc5883l/manifest.json` 与 `code/qmc5883l.{c,h}`、`code/qmc5883l_stm32.{c,h}` 齐备
- [x] mspm0 母版 `mspm0.syscfg` 新增 `QMC5883L` GPIO 实例（SCL=PA23 / SDA=PA24）
- [x] stm32 母版 `pin_config.h` 新增 `QMC5883L_SCL_GPIO/_PIN`、`QMC5883L_SDA_GPIO/_PIN`（默认 PA6/PA7 = 既有软 I2C 总线）
- [x] 寄存器按 QMC 手册：数据 0x00..0x05 **小端** X/Y/Z；状态 0x06；控制1 0x09 = 0x1D（OSR512/±8G/10Hz/连续）；控制2 0x0A = 0x40；SET/RESET 周期 0x0B = 0x01；Chip ID 0x0D 读回 **0xFF** 否则 init 返回 2
- [x] 地址 = 0x0D 写 / 0x0E 读，与库内全部已知 I2C 地址零冲突（0x0D 同段无既有件）
- [x] API 与 `hmc5883l` 同名同语义（`qmc5883l_init/read/read_heading` + `qmc5883l_heading_from_xy` 纯函数）
- [x] notes 写清与 `hmc5883l` 的互替关系与「把 HMC 初始化序列发给 QMC 会写坏控制字」的具体证据（0x09/0x0B 语义对撞）
- [x] `tests/test_module_qmc5883l.py` 照 01 同构；pytest 全绿；`verified` 暂 false（由 04 翻牌）

**结论（工单 02 已 resolved，2026-09-12）**：`library/modules/qmc5883l`（双平台四文件 + manifest）落地；寄存器表经 **QST 官方数据手册 Rev. B 逐页核对** + Betaflight 驱动交叉验证（非编造）；`tests/test_module_qmc5883l.py` 12 例通过。已知项如实记录：Chip ID=0xFF 判别力有限（浮空上拉亦返回全 1）、DRDY 超时窗口内可能取到上一轮值。编译矩阵由工单 04 翻牌，verified 已回写 true。
