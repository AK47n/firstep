# 03 — ws2812 模块（幻彩 RGB 灯，手稿 control--ws2812-color-rgb-led.md）

**要做什么：** 模块库新增 `ws2812` 条目（仅 mspm0）：从手册代码块提炼完整驱动为纯驱动切片（初始化 + 单颗/多颗 24bit 写码），该模块被选中后生成工程打开即可编译、可调用（`ws2812_init()` + 写色服务函数），不再"需自备"。mspm0 灰底 syscfg 加 1 个 GPIO 输出实例，生成时按选中裁剪。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/control--ws2812-color-rgb-led.md` 的「代码块」章节抽 `bsp_ws2812.c/h` 全文（正文内嵌段落是行拆散版，不可用）→ 改写为模块规范：`code/ws2812.c` + `code/ws2812.h`，gpio 位操作时序（delay_us 走 delay 模块依赖），去掉 main.c 演示/printf，无状态机（ADR 0009）
- [ ] 母版 `mspm0.syscfg` 加 GPIO 输出实例（命名 WS2812，1 associatedPin，地猛星排针空闲脚且不与现有默认布局重叠）；`syscfg_instances.py` INSTANCE_CONSUMERS 登记
- [ ] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url = 手册原页/notes 含手册路径 + 原页 + 网盘链接 + 改造要点）；简介判据：与代码一致 + 能力方向（RGB 幻彩指示/氛围灯效）+ 无题绑定（过 BANNED_TOPIC_WORDS 机械拦截，无题号/年份/题名）；pins 声明 1 × gpio_out（macros 与 syscfg 宏名对齐）
- [ ] wordlist.json 补录：「显示」类加「WS2812 幻彩灯」方案挂 `lib_modules: ["ws2812"]`
- [ ] 测试：`tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增 WS2812 实例保留/裁剪断言；新增 `tests/test_module_ws2812.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/写色过静态门禁）
- [ ] 编译验证：module-polish 编译矩阵配方 gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录
