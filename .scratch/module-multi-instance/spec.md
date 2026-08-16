# module-multi-instance：简单模块多实例（led 首例）

> 2026-08-16 grilling 定稿（用户逐轮确认，实现边界由 agent 拍板后经用户「可以」确认）。

## Problem Statement

题目常要多个同类外设：4 个指示灯、2 个蜂鸣器、多个按键。现在的选择模型是
「每个模块最多选一次」——选 led 只能得到一个 led 模块，通道宏固定
`LED_RED/LED_YELLOW/LED_GREEN` 三色，引脚固定（stm32 PC13/14/15，mspm0 PA15）。
学生遇到「4 个灯」只能自己改代码。需要一种「一次配置里选同一个简单模块多次」
的机制：每个实例有自己的显示名 / 颜色 / 引脚，生成后自动配好，学生代码仍用
`led_init(LED_RED)` 这类通道宏。

## Solution

通用「简单模块多实例」机制，led 为首个实现。用户在配置阶段对支持多实例的模块
添加 N 个实例（N 由题目 / 用户需求决定，上限 8 只是 sanity 上限），每个实例带
显示名 + 变体（led = 颜色）+ 可选引脚；生成时自动为每个实例分配默认引脚、生成
通道宏与初始化段。AI 推荐阶段自动猜实例数量与名称，用户确认后仍可增删改。机制
通用，beep/key/motor 等留扩展口；本阶段只开放 led 多实例。

## User Stories

1. 作为学生，题目要 4 个指示灯时，我可以在配置里选 4 个 led 实例，而不是 1 个 led 模块。
2. 作为学生，每个灯实例有独立的显示名（红 / 黄 / 绿 / 状态灯），我能一眼分清用途。
3. 作为学生，红 / 黄 / 绿三个灯生成的通道宏仍是 `LED_RED/LED_YELLOW/LED_GREEN`，API 不变。
4. 作为学生，超过三个灯或非内置颜色的灯生成 `LED_1/LED_2/...` 通道宏，按创建顺序编号。
5. 作为学生，两个红灯自动生成 `LED_RED` 和 `LED_RED_2`，不会重名。
6. 作为学生，我写的代码是 `led_init(LED_RED)`、`led_on(LED_GREEN)`、`led_toggle(LED_1)`，不背引脚。
7. 作为学生，生成后每个灯的引脚与初始化都自动配好，打开就能编译、直接开写。
8. 作为学生，自动分配的引脚和已有模块/母版占用冲突时，我能在板图上重新绑那个灯。
9. 作为学生，选旧式单实例 led 时，生成产物行为和以前一致（API / 引脚 / 通道不变），不破我已有的工程习惯。
10. 作为使用 AI 推荐的学生，题面写「4 个指示灯」时，推荐自动给我 led×4（红/黄/绿/状态灯），我确认后还能手动增删改。
11. 作为想扩展的学生/维护者，以后 beep/key/motor 也能多实例，不用再动这套机制，只挂各自的渲染 hook。

## Implementation Decisions

### 多实例能力声明（manifest，模块级）

模块 manifest 增一个可选能力块（旧 manifest 缺该字段 = 不支持多实例 = 单实例）：

```json
"multi_instance": {
  "max": 8,          // 实例上限（sanity 上限，实际数量由题目/用户需求决定）
  "variant": "color" // 实例变体名（led = color；驱动命名与渲染的 key）
}
```

`max` 是硬上限守卫（超了报错），不是默认数量；默认实例数由推荐链路猜、用户增删。
`variant` 是区分实例的属性名，led = 颜色；beep/key/motor 以后用各自变体名。

### 实例数据形状（选择 / 生成请求携带）

每模块可选携带实例清单（旧请求不带 = 单默认实例，向后兼容）：

```json
"instances": {
  "led": [
    {"name": "红灯",   "variant": "red",   "pin": null},
    {"name": "绿灯",   "variant": "green", "pin": null},
    {"name": "状态灯", "variant": null,    "pin": null}
  ]
}
```

- `name` = 显示名，自由中文；`variant` = 变体（led = 颜色，内置 red/yellow/green）；
- `pin` = 显式引脚覆盖，`null` = 自动分配默认脚。

### 展开层（通用）

`resolve_selection` 后新增「实例展开」纯函数：`slug×N → (宏名, 默认脚) 计划`。
通用层只做「合成具体实例 + 分配默认脚」，不产代码。

### 通道宏命名（led 渲染 hook，非通用机制）

- 内置色 red/yellow/green → `LED_RED` / `LED_YELLOW` / `LED_GREEN`；
- 同一内置色第 2 次起 → `LED_RED_2`、`LED_GREEN_2`（按出现序加后缀）；
- 非内置色（variant null 或未知）→ `LED_1` / `LED_2` / …，按创建顺序编号。

### 默认脚分配（D3，简化口径）

确定性「第一个能用的 GPIO」，不做全局空闲集扫描：

- stm32：红/黄/绿 → PC13/PC14/PC15；第 4 个起按 board 顺序找下一个可用 io 脚；
- mspm0：第一个实例 → PA15，其余按 board 顺序找下一个可用 io 脚；
- 只做**同模块内去重**（不把两个灯塞同一脚）；
- 与母版固定占用 / 其他已选模块默认脚冲突 = **用户重绑**（现有绑定 UI 已支持），
  现有 generate-time 门禁（slot 冲突 400 / mspm0 SysConfig Resource conflict）
  照旧当安全网，不新增「找不到空闲脚」的硬 400。

### 渲染（led 渲染 hook，D2 扩展口）

通用层产出「实例 → (宏名, 引脚)」计划；led hook 负责把它渲染成：

- 新文件 `led_instances.h`（通道宏 `LED_RED` … + 每实例通道索引 + pin 表）；
  `ml_led.h` / `ml_led.c` 改成「读 `led_instances.h`」的泛型驱动（不再写死 3 通道，
  详见 D4）；`pin_config.h` **逐字节不写**（引脚接线单源，字节契约守这里）；
- mspm0 侧多实例的 syscfg 引脚落点（数据细节在工单 03 定）。

### 骨架 / 冒烟注入

`build_skeleton_interfaces` 把「生成了哪些通道宏」注入接口块/prompt，LLM 才能
生成 `led_init(LED_RED)` … `led_init(LED_1)` 逐个初始化，静态自检不误占位。

### 向后兼容

旧单选 = 1 个默认实例（led 单实例仍生成红/黄/绿三通道，API / 引脚 / 通道行为
一致——`led_instances.h` 默认 3 通道 PC13/14/15，`LED_RED/YELLOW/GREEN=0/1/2`）。
**`ml_led.c/.h` 泛型化后单实例不再「逐字节 diff 为空」**（源码文本从硬编码变泛型），
改为行为一致；`pin_config.h` 仍逐字节不写（`pinwriter` 不变不写契约，引脚接线单源）。

## Testing Decisions

- 好测试 = 只测外部行为，不测实现细节：展开层测「给定实例清单 → 宏名/默认脚
  计划」；渲染层测「给定计划 → 生成的头文件/工程里含预期通道宏与初始化」；
  兼容层测「旧 manifest / 旧请求缺字段 → 单实例产物与基线逐字节一致」。
- 复用现有测试缝隙：`tests/test_module_led_beep.py`（真实库不变量）、
  `tests/test_pin_bindings.py`、`tests/test_default_layout.py`（白名单）为
  prior art；新增 `tests/test_module_multi_instance.py` 收展开/命名/分配/兼容。
- 编译级验收口径沿用 module-polish：UV4/gmake 0 error、0 module warning、
  syscfg ovsRate 基线 warning 允许并记录。

## Out of Scope

- beep/key/motor 的实际多实例实现（本阶段只留 hook 扩展口，不实现）；
- 生成后编辑持久化（仍是生成前锁定，v1 口径）；
- 复杂模块（motor 这种 10 引脚、成对 pwm 约束的）多实例——「简单模块」先行。

## Further Notes

- led 双平台不对称是最大坑：stm32 侧 led `files=[]` 内嵌母版、0 pins、3 个固定
  通道宏；mspm0 侧 1 个 pin 角色 `LED`(gpio_out/PA15)、syscfg 实例 `LED_BEEP`。
  通用机制必须同时覆盖两种形态，led 的「颜色→宏命名 + 代码渲染」必须落在 led
  hook，不写进通用层。
- 并行工单竞态教训（[[parallel-tickets-shared-checkout-race]]）：工单 04/06 若
  与主链并行，各自独立 worktree，提示词给文件边界。
