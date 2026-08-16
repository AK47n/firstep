# ADR 0013 — 简单模块多实例：能力声明 + 展开层 + per-module 渲染 hook

- 状态：已接受（2026-08-16，六票全闭；grilling 定稿后经用户逐轮确认）
- 前置：ADR 0009（模块 = 纯驱动切片）、ADR 0010（板级引脚配置）、ADR 0012（引脚全解）

## 背景

选择模型是「每个模块最多选一次」：选 led 只得到一个 led 模块，通道宏固定
`LED_RED/YELLOW/GREEN` 三色、引脚固定（stm32 PC13/14/15、mspm0 PA15）。题目常要多个
同类外设（4 个指示灯），学生只能自己改代码。需要「一次配置选同一简单模块多次」的机制：
每实例有显示名 / 颜色 / 引脚，生成后自动配好，学生代码仍用 `led_init(LED_RED)` 这类
通道宏。机制通用、led 首例；beep/key/motor 留扩展口。

## 决策

1. **manifest 能力声明**：模块级可选 `multi_instance: {max, variant}`（led = max 8 /
   variant color），缺省 = 单实例（旧 manifest 逐字节兼容）。max 是 sanity 上限，不是
   默认数量——实例数由题目 / 用户需求决定。
2. **展开层（通用）**：`expand_instances` 把 `slug×N` 合成 `(通道宏名, 默认脚)` 计划；
   命名规则（内置色 → `LED_RED`、重复内置色 → `LED_RED_2`、非内置 → `LED_1..n`）与默认
   脚分配（stm32 红/黄/绿 PC13/14/15、mspm0 首 PA15、其余 board 顺序首个可用 io 脚）在此。
3. **per-module 渲染 hook**：通用层只产「实例 → (宏, 脚)」计划，代码渲染归按 slug 注册
   的 hook（led 首个）；beep/key/motor 各挂各的 hook——扩展口在此。
4. **默认脚 = 首个可用 GPIO，冲突用户重绑**：不做全局空闲集扫描、不新增「找不到空闲脚」
   硬 400；与母版固定占用 / 其他已选模块默认脚冲突由用户重绑，generate-time 门禁（slot
   冲突 400 / mspm0 SysConfig Resource conflict）照旧当安全网。
5. **led 双平台泛型化**：`ml_led.c` / `led.c` 读生成文件 `led_instances.h`
   （`LED_CHANNEL_COUNT` + 通道索引 + pin 表），不再写死 3 / 1 通道。单实例 = 默认 3 通道
   PC13/14/15（stm32）/ 1 通道 PA15（mspm0），行为一致但**不再逐字节 diff 为空**（.c/.h
   源文本从硬编码变泛型）；`pin_config.h` / syscfg 仍逐字节不写（接线单源，字节契约守这里）。

## 后果

- 单实例 led 行为一致、`pin_config.h`/syscfg 逐字节不写，但 `ml_led.c/.h` 源码泛型化——
  验收口径从「逐字节 diff 为空」改为「行为一致」。
- 通道宏索引两平台一致（`LED_RED=0/YELLOW=1/GREEN=2/LED_1=3…`），pin 表平台异构。
- mspm0 多实例 syscfg：通道 0 复用 `LED_BEEP`、其余新实例 `LED_<n>`（pin 名全局唯一是
  SysConfig 硬约束）。
- 留扩展口：beep/key/motor 多实例只加渲染 hook + 能力声明，机制不重动。
- 存量 bug 另立项：stm32 `led_toggle` 反转（行为一致契约下 03/05 不改，见
  `.scratch/led-toggle-fix/`）。
