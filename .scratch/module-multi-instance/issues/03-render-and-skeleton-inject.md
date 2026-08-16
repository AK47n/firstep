# 03 — 渲染 + 骨架注入（led 首例，垂直切片）

**What to build:** 选 led×N → 生成工程里 N 个灯都能编译：通道宏与每实例 pin 宏落到
新文件 `led_instances.h`（不碰母版 `ml_led.h`/`pin_config.h`），mspm0 多实例引脚落进
syscfg；骨架/冒烟接口把「生成了哪些通道宏」喂给 LLM，冒烟能逐个 `led_init(...)`。
单实例路径不产生任何写侧变化（逐字节护栏）。

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] led 渲染 hook（按 slug 注册，照 `patcher_registry` 先例）：实例计划 → 通道宏 + 每实例 pin 宏，写进生成工程
- [ ] stm32：通道宏 + pin 宏落新文件 `led_instances.h`，母版 `ml_led.h`/`pin_config.h` 对单实例路径零 diff
- [ ] mspm0：多实例引脚落点进 syscfg（`LED_BEEP` 扩 pin 或新增实例，数据细节在此票定并留痕），单实例零写侧变化
- [ ] `build_skeleton_interfaces` 注入通道宏清单，冒烟生成 `led_init(LED_RED)` … `led_init(LED_1)` 逐个初始化，静态自检不误占位
- [ ] 单实例 led 生成产物与基线逐字节 diff 为空（红证先行）
- [ ] pytest 全绿 + mypy src 干净
