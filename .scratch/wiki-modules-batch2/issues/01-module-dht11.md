# 01 — dht11 模块（DHT11 温湿度传感器，手册 sensor--dht11-temp-humi-sensor.md）

**要做什么：** 模块库新增 `dht11` 条目（仅 mspm0）：从手册提炼完整单总线驱动为纯驱动切片——`dht11_init()` + `dht11_read(&temp, &humi)`（0=成功 1=校验/超时失败，内部完成起始/响应/40bit 接收/校验和/温湿度换算）+ `dht11_read_temperature/read_humidity` 便捷封装；选中后生成工程打开即可编译，不再"需自备"。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-05 完成。DHT11 单总线位时序：delay 模块延时（delay_ms(19) 起始 / delay_us(20/28) 位分界 / 80 步进超时，页外 delay_uus 替换）、数据线方向运行时切换（AHT10_SDA 先例）、校验和 + 应答超时防护、出参指针；母版 syscfg 新 GPIO 实例 DHT11/DATA（OUTPUT、initialValue SET）默认 PB7（与 AHT10 SDA/STEP_MOTOR DIR2/HUIDU R4 重叠，温湿度互替 + 步进/巡线簇同选概率最低）；无 TIMER 占用。单选生成 → gmake 0 error / 0 warning（PASS）；未上板。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--dht11-temp-humi-sensor.md` 「代码块」章节抽完整 `dht11.c/h` → 改造为 `code/dht11.c` + `code/dht11.h`：去 main/printf、函数名规范化（`dht11_init/read/read_temperature/read_humidity`）、全局温湿度缓存改出参指针、校验和/超时改显式返回 0=成功 1=失败（原版校验失败 return 0、成功 return val 语义反转，按库内 aht10 惯例统一）
- [x] 时序：微秒/毫秒延时全部走库内 `delay` 模块（`dependencies: ["delay"]`；页外 `delay_uus` 工具函数替换为 `delay_us`，同 ws2812 先例）；**不占 TIMER**
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 `DHT11`（1 个 associatedPin DATA，direction OUTPUT、initialValue SET——总线空闲高电平；运行时方向切换照 AHT10_SDA 先例）；默认脚按"同选概率最低重叠"分配：DATA=PB7（与 AHT10 SDA——温湿度互替、STEP_MOTOR DIR2/HUIDU R4 重叠——温湿度与步进/巡线同选概率最低，同批 AHT10 先例），注释写明依据；重叠对登记 `test_pin_bindings` 刻意表（PB7 3→4）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"DHT11": ("dht11",)`
- [x] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录）；pins：DATA = gpio_out（default PB7）；简介判据：能力方向（环境温湿度采集/恒温恒湿监测）+ 无题绑定（过 BANNED_TOPIC_WORDS 拦截）
- [x] wordlist.json 补录：「感知传感器」加「DHT11 温湿度传感器（单总线）」方案挂 `lib_modules: ["dht11"]`；models 加 "DHT11"
- [x] 测试：`tests/test_pins.py::MSPM0_DEFAULT_MAP` 增（dht11, DHT11_DATA）映射；`test_syscfg_prune.py` 增 DHT11 实例断言；`test_pin_bindings.py` 刻意表 PB7 计数 3→4 + 注释；新增 `tests/test_module_dht11.py`（单选生成 → syscfg 含 DHT11 实例 + 模块文件落盘 + main.c 调 init/read 过静态门禁）
- [x] 编译验证：复制 `.scratch/wiki-modules-batch1/run_joystick_matrix.py` 改 slug 为 dht11 → gmake 真编译 0 error、模块自身 warning 0（`C:/ti/ccs2050`）；结果回写 manifest verified=true + notes 记录；code-review 后中文提交


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
