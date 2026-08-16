# 03 — 渲染 + 骨架注入（led 首例，垂直切片）

**What to build:** 选 led×N → 生成工程里 N 个灯都能编译：通道宏与每实例 pin 宏落到
新文件 `led_instances.h`（不碰母版 `ml_led.h`/`pin_config.h`），mspm0 多实例引脚落进
syscfg；骨架/冒烟接口把「生成了哪些通道宏」喂给 LLM，冒烟能逐个 `led_init(...)`。
单实例路径不产生任何写侧变化（逐字节护栏）。

**Blocked by:** 02

**Status:** resolved

- [x] led 渲染 hook（按 slug 注册，照 `patcher_registry` 先例）：实例计划 → 通道宏 + 每实例 pin 宏，写进生成工程
- [x] stm32：通道宏 + pin 宏落新文件 `led_instances.h`，母版 `ml_led.h`/`pin_config.h` 对单实例路径零 diff
- [x] mspm0：多实例引脚落点进 syscfg（`LED_BEEP` 扩 pin 或新增实例，数据细节在此票定并留痕），单实例零写侧变化
- [x] `build_skeleton_interfaces` 注入通道宏清单，冒烟生成 `led_init(LED_RED)` … `led_init(LED_1)` 逐个初始化，静态自检不误占位
- [x] 单实例 led 行为一致（API / 引脚 / 通道不变，`led_instances.h` 默认 3 通道 PC13/14/15）；`pin_config.h` 逐字节不写；`ml_led.c/.h` 泛型化后不追「逐字节 diff 为空」
- [x] pytest 全绿 + mypy src 干净

**Notes:** 渲染层落地 `instance_render.py`（slug 注册表 + LedInstanceRenderer +
expand_instance_plans 聚合 + instance_interface_blocks / managed_header_rels 注入面），
骨架侧 `build_skeleton_interfaces` 注入与生成侧渲染同源文本。1666 passed + mypy 44 文件干净。

**mspm0 多实例 syscfg 落点方案（验收 3 留痕）**：通道 0 复用母版 LED_BEEP（计划脚 ≠ 现值时
改写 `LED_BEEP.associatedPins[0].pin.$assign`）；通道 k≥1 新 GPIO 实例 `LED_<实例号>`
（关联 pin `$name = LED<实例号>`）。真机判例：新实例 pin 名全用 "LED" → SysConfig
`Duplicate name: 'LED' also exists on instance(s)` 4 error → 改为 LED2/LED3 形态（pin 名
全局唯一是 SysConfig 硬约束）；生成宏 = `<INSTANCE>_PORT` / `<INSTANCE>_LED<实例号>_PIN`
（单 pin 实例的 PORT 宏形态 = LED_BEEP 先例）。`led_instances.h` 落点：stm32 工程根
（与 pin_config.h 同级，母版自带默认 = 单实例三通道）；mspm0 `modules/led/code/`
（led.c 同目录，manifest files 声明 + 库内默认单通道——复制即就位，单实例零写侧变化）。

**编译验收（2026-08-16 真机冒烟）**：stm32 led×4 UV4 `0 Error(s), 0 Warning(s)`；
stm32 单实例 0/0；mspm0 led×4 gmake exit 0（含 syscfg 新实例 SysConfig 生成 + 主循环
逐个 led_init）；mspm0 单实例 exit 0。全矩阵归 05。

**判据留痕**：① mspm0 单实例默认 = `LED_CHANNEL_COUNT 1` + RED/YELLOW/GREEN=0/1/2，
越界钳回首通道 → 三宏仍指 PA15（旧三别名同脚行为一致，通道索引两平台一致）；
② stm32 默认通道引脚取 pin_config.h 宏（LED_PORT/LED_RED_PIN…，接线单源，
config.LED_* 绑定照旧驱动三内置灯）；多实例 = 全通道具体 GPIO_x/Pin_y（实例计划脚
权威）；③ 渲染在 apply_pin_bindings **之后**：多实例模式实例脚为权威（led.LED 角色
绑定与实例脚双源冲突时渲染胜，04 前端只发其一）；④ 渲染接管文件剔除模块接口块
（managed_headers）——否则 LLM 同时看到库内默认与计划两份矛盾通道宏（真机测试
抓出）；⑤ 观察到的存量行为保留：stm32 `led_toggle` 恒不动（读到高 led_on / 读到低
led_off，疑似历史反转 bug，HEAD 即有——行为一致契约下未改，建议另开小工单；mspm0
侧 DL_GPIO_togglePins 是真翻转）；⑥ stm32 引脚→枚举转换（GPIO_x/Pin_y、_digits）与
pinwriter 的知识重复——两消费方暂不复用（rule of two，第三处时单源化）；⑦ webapp
请求层 instances 解析归 04（本票域层签名就位，路由未改——缺省 = 现行为逐字节）；
⑧ CONTEXT.md 加「多实例」词条 + 母版行 led_instances.h 补充（超出工单文件边界，
工作流 Step 1 词表同步要求）。

code-review 双轴：Standards——CONTEXT 词表未同步（已修）、断言风格（pinwriter 同款
断言先例，留）、5 条 smell 判（_digits 重复 / syscfg 正则同款 / 注册表循环 3 次 /
展开前置重复 / 参数命名——参数命名已修、展开前置已合并进 expand_instance_plans）；
Spec——编译证据在 Notes、webapp 归 04、绑定×实例脚双源已留痕、追加块粘尾行已修。
无 material 缺陷。
