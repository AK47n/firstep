# 04 — hx711 模块（称重传感器，手册 sensor--hx711-weighing-sensor.md）

**要做什么：** 模块库新增 `hx711` 条目（仅 mspm0）：从手册代码块提炼完整驱动为纯驱动切片（初始化 + 读重量：SCK 输出/Dt 输入双 GPIO 时序，增益 128 + 平均滤波），选中后生成即编译、可调用（`hx711_init()` + `hx711_read()`/`hx711_get_weight()` 类服务函数）——电子称重/拉力检测类赛题无需自备驱动。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--hx711-weighing-sensor.md`「代码块」章节抽 `bsp_hx711.c/h` 全文 → 模块规范改写（`code/hx711.c/h`，delay_us 走 delay 依赖；去皮/均值等按手册算法保留为纯函数服务接口；去 printf；无状态机）
- [ ] 母版 `mspm0.syscfg` 加 GPIO 实例（命名 HX711，2 associatedPins：SCK 输出 + DT 输入，地猛星排针空闲脚不与默认布局重叠）；`syscfg_instances.py` 登记
- [ ] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（kit/source_url = 手册原页；notes 含手册路径 + 原页 + 网盘链接 + 改造要点）；简介能力方向（电子称重/拉力检测、重量阈值判断辅助）+ 无题绑定；pins 1 × gpio_out(SCK) + 1 × gpio_in(DT)
- [ ] wordlist.json 补录：「感知传感器」类加「HX711 称重传感器」方案挂 `lib_modules: ["hx711"]`
- [ ] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增 HX711 实例断言；新增 `tests/test_module_hx711.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/读重过静态门禁）
- [ ] 编译验证：gmake 真编译 0 error、模块 warning 0；回写 manifest verified/notes
