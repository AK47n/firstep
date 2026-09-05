# 04 — ags10 模块（AGS10 有害气体传感器，手册 sensor--ags10-harmful-gas-sensor.md）

**要做什么：** 模块库新增 `ags10` 条目（仅 mspm0）：从手册提炼 AGS10 驱动为纯驱动切片——软 I2C 位操作（2 GPIO，SDA 方向运行时切换，照 AHT10/批次5/批次6 先例）。`ags10_init()`（空实现占位——器件无初始化序列）+ `ags10_read(&voc_ppb)`（写地址 0x34+寄存器 0x00 → 读地址 0x35 应答重试 → 5 字节回包 = 状态 + TVOC 24bit + CRC（`Calc_CRC8(data,4)` 页面原式：初值 0xFF/多项式 0x31 自包含））。页面 I2C 原语族（`AGS10_IIC_*`）收敛为模块内静态；**上游缺陷修正**：读地址重试条件写反（`timeout >= 50` → `timeout < 50`——超时分支原式永不触发，按函数注释语义修正并记 notes）、返回值与错误码混用收敛为出参+状态（mlx90614 先例）。

**被谁阻塞：** 无——可立即开始（软 I2C 先例齐全）。

**状态：** claimed

**结论：** 实施中——见提交历史与工单勾选。

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--ags10-harmful-gas-sensor.md` 「代码块」章节抽完整 `bsp_ags10.c/h` → 改造为 `code/ags10.c` + `code/ags10.h`：去 main/printf、函数名规范化（`ags10_init/ags10_read`）、IIC 原语族静态化（`ags10_iic_start/stop/send_ack/send_nack/wait_ack/send_byte/read_byte`）、`Calc_CRC8` 静态化为 `ags10_crc8`（初值 0xFF/多项式 0x31 页面原式保留）、延时走 delay 模块（`dependencies: ["delay"]`）、**重试条件修正**（`while((WaitAck()==1) && (timeout >= 50))` → `timeout < 50`——按函数注释「等读地址应答 ≤50×1ms、超时返回 3」语义，notes：上游缺陷）、**出参+状态收敛**（页面返回值 = TVOC 值/错误码 1-4 混用（TVOC=1 ppb 语义冲突）→ `ags10_read(uint32_t *voc_ppb)` 返回 0=成功/1=通信失败/2=发送失败/3=等待超时/4=校验失败——mlx90614 先例，notes）
- [ ] 母版 `mspm0.syscfg`：新 GPIO 实例 `AGS10`/SCL+SDA（照 SHT30 先例）——默认 SCL=PB18 / SDA=PA14（与 DC_MOTOR BIN1、MAX7219 CS、DCC_100_PWM2（step_motor 步进脉冲——风机排烟联动）、WS2812 IN（灯带指示）、RC522 SCK 重叠：气体传感与运动控制/读卡/灯带低频同框、同选概率最低；避让原则同 sgp30（不叠温湿度/光照/OLED/语音/按键/报警/无线/批次 5 八脚）），注释说明；跨端口（PB18/PA14）宏按 `<实例>_<引脚名>_PORT/PIN/IOMUX` 分派（max7219 先例）
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS：增 `"AGS10": ("ags10",)`
- [ ] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（模块代码 2z5o）+改造要点+与库内同类分工（**气体**：mq2/mq135/mq5 模拟量相对值、sgp30 TVOC+CO2e、本件 TVOC ppb 0-99999/预热 ≥120s/采样周期 ≥2s）+**上游缺陷修正记录**（重试条件写反、返回值混用——ir_remote/nrf24l01 先例）+**页面规格 ≤15kHz 与页面时序 100kHz 不一致注明**+编译记录）；pins：`AGS10_SCL`/`AGS10_SDA` = gpio_out PB18/PA14；简介判据：能力方向（有害气体 TVOC 检测/空气污染监测）+ 无题绑定
- [ ] wordlist.json 补录：「感知传感器」加「AGS10 有害气体传感器（TVOC）」方案挂 `lib_modules: ["ags10"]`，models 加 "AGS10"
- [ ] 测试：`tests/test_pins.py` MSPM0_DEFAULT_MAP 增 AGS10_SCL/AGS10_SDA 映射；`tests/test_pin_bindings.py` 刻意表更新（PB18 2→3、PA14 3→4 注释补 ags10）；`tests/test_syscfg_prune.py` AGS10 实例保留/裁剪断言；新增 `tests/test_module_ags10.py`（manifest 结构 + 单选生成（syscfg 含 AGS10 实例 + 模块文件落盘 + main.c 调 init/read 过静态门禁）+ CRC8 原式守卫（0x31/0xFF）+ **重试条件守卫**（`timeout < 50`——防回潮页面写反缺陷）+ 出参+状态守卫（`voc_ppb`、页面 1-4 失败码语义保留））
- [ ] 编译验证：复制 `run_joystick_matrix.py` 改 slug（`.scratch/wiki-modules-batch7/run_ags10_matrix.py`）单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交
