# 05 — aht10 模块（温湿度传感器，手册 sensor--aht10-temp-humi-sensor.md）

**要做什么：** 模块库新增 `aht10` 条目（仅 mspm0）：从手册代码块提炼完整驱动为纯驱动切片（软 I2C 位操作初始化 + 读温湿度 + 换算），选中后生成即编译、可调用（`aht10_init()` + 读温度/湿度服务函数）——环境温湿度采集类赛题无需自备驱动。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-05 完成并提交（23b3c9b0 前置提交）。gmake 0 error / 0 module warning（首版 IOMUX 宏名猜错编译失败，实测为 <实例>_<引脚>_IOMUX 后通过）；PB6/PB7 默认重叠入 test_pin_bindings 刻意重叠表。

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--aht10-temp-humi-sensor.md`「代码块」章节抽全文（soft I2C 起始/停止/应答/读写字节原语 + 温湿度命令/换算）→ 模块规范改写（`code/aht10.c/h`；delay_us 走 delay 依赖；去掉 main.c 演示/printf；无状态机）
- [ ] 母版 `mspm0.syscfg` 加 GPIO 实例（命名 AHT10，2 associatedPins：SCL 输出 + SDA 双向，地猛星排针空闲脚不与默认布局重叠）；`syscfg_instances.py` 登记（共享/冲突判据：AHT10 为软 I2C 专属 GPIO，不与硬件 I2C 实例共享）
- [ ] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（kit/source_url = 手册原页；notes 含手册路径 + 原页 + 网盘链接 + 改造要点）；简介能力方向（温湿度采集 + 环境监测）+ 无题绑定；pins 2 × gpio（SCL/SDA）
- [ ] wordlist.json 补录：「感知传感器」类加「AHT10 温湿度传感器」方案挂 `lib_modules: ["aht10"]`
- [ ] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增 AHT10 实例断言；新增 `tests/test_module_aht10.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/读温湿度过静态门禁）
- [ ] 编译验证：gmake 真编译 0 error、模块 warning 0；回写 manifest verified/notes
