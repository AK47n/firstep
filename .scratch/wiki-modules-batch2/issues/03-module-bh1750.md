# 03 — bh1750 模块（BH1750 光照强度传感器，手册 sensor--bh1750-light-intensity-sensor.md）

**要做什么：** 模块库新增 `bh1750` 条目（仅 mspm0）：从手册提炼完整软 I2C 驱动为纯驱动切片——`bh1750_init()`（Power On 0x01）+ `bh1750_start_measure()`（0x10 连续高分辨率测量启动）+ `bh1750_read_lux(float *lux)`（读 2 字节 /1.2 出 lx，0=成功 1=无应答）；软 I2C 占 2 GPIO（SDA 方向运行时切换），不占硬件 I2C 外设；选中后生成工程打开即可编译。

**被谁阻塞：** 无——可立即开始（照 aht10 先例，机械复制度高）。

**状态：** resolved

**结论：** 2026-09-05 完成。软 I2C 照 aht10 先例（SDA 方向运行时切换、半周期 2us；delay 模块依赖）；API 规范化（bh1750_init/start_measure/read_lux，等待应答超时统一 0=成功 1=失败，0x10 测量命令独立暴露）；母版 syscfg 新 GPIO 实例 BH1750/SCL+SDA 默认 PA12/PA13（与 PWMAB C0/C1 重叠——光照度与双电机驱动同选概率最低；故意不叠 AHT10 的 PB6/PB7——温湿度+光照为环境监测常见组合）；不占硬件 I2C 外设与 TIMER。单选生成 → gmake 0 error / 0 warning（PASS）；未上板。另：test_pins 引脚字面量验收的 ADC_Channel_N 豁免扩至 us016（薄封装 API 参数非引脚字面量）。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--bh1750-light-intensity-sensor.md` 「代码块」章节抽完整 `bsp_gy30.c/h` → 改造为 `code/bh1750.c` + `code/bh1750.h`：去 main/printf、函数名规范化（`bh1750_init/start_measure/read_lux`，去掉 `IIC_`/`Single_Write_BH1750`/`Multiple_read_BH1750`/`GY30_Init` 菜市场命名）、I2C 原语静态化（iic_start/stop/ack/wait_ack/send_byte/read_byte，照 aht10）
- [x] 软 I2C 照 aht10 先例：2 GPIO 位操作（SDA_OUT/SDA_IN 运行时切换；半周期 2us ≈ 100kHz 级；节点需板上/模块自带上拉）；延时全部走库内 `delay` 模块（`dependencies: ["delay"]`）；不占硬件 I2C 外设
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 `BH1750`（2 associatedPins：SCL 输出 + SDA 输出（initialValue CLEARED，运行时切输入），照 AHT10 先例）；默认脚按"同选概率最低重叠"分配：SCL=PA12 / SDA=PA13（与 PWMAB ccp0/ccp1——motor PWM 重叠：光照度监测/台灯与双电机驱动同选概率最低；不选 AHT10 的 PB6/PB7——温湿度+光照=环境监测站常见组合同选概率高），注释写明依据；重叠对登记 `test_pin_bindings` 刻意表（PA12 1→2、PA13 1→2）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"BH1750": ("bh1750",)`
- [x] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录）；pins：SCL = gpio_out（PA12）、SDA = gpio_out（PA13）；简介判据：能力方向（环境光照度采集/光照控制/显示监测）+ 无题绑定
- [x] wordlist.json 补录：「感知传感器」加「BH1750 光照度传感器」方案挂 `lib_modules: ["bh1750"]`；models 加 "BH1750"
- [x] 测试：`tests/test_pins.py::MSPM0_DEFAULT_MAP` 增（bh1750, BH1750_SCL/SDA）映射；`test_syscfg_prune.py` 增 BH1750 实例断言；`test_pin_bindings.py` 刻意表 PA12/PA13 计数 + 注释；新增 `tests/test_module_bh1750.py`（单选生成 → syscfg 含 BH1750 实例 + 模块文件落盘 + main.c 调 init/start_measure/read_lux 过静态门禁）
- [x] 编译验证：复制 `run_joystick_matrix.py` 改 slug 为 bh1750 → gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录；code-review 后中文提交


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
