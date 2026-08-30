# key-multi-instance：key 模块多实例（独立按键）

> 2026-08-31 用户确认定稿（三问三答：宏命名 = 语义变体 + 通用回退；消抖/边沿 = 模块只做原始读取；测试缝 = 沿用既有）。

## 问题陈述

按键是电赛最常见的答题输入（启动 / 停止 / 模式 / 设置）。现在的 key 模块是单键
纯驱动：`get_key_state()` 读唯一一个按键（上拉低电平按下），stm32 默认 PB3、
mspm0 默认 PA2（板载偏置）。选择模型是「每个模块最多选一次」，选一次 key 只有
一个按键——「启动键 + 设置键」要两个键、2026F 要 3 个独立启动键、2026C 数字
钥匙要一键启动 + 门锁手动改 ID 的输入组合，学生只能自己改代码 / 自己接线。
需要把 led 已实现的多实例机制（module-multi-instance/01-06 首例）挂到 key 上：
一次配置选多个独立按键，每个键有自己的显示名 / 引脚，生成后自动配好，代码写
`get_key_state(KEY_START)` 这类通道宏。

## 方案

键模块挂多实例机制：manifest 声明能力 → AI 推荐按题面猜实例 → 用户实例卡
增删改 → 生成时展开为「实例 → (宏名, 默认脚) 计划」→ 渲染 hook 产出通道宏
头文件与 mspm0 syscfg 新实例 → 骨架 / 冒烟接口块注入同一份宏清单。机制层
（注册表 / 展开管线 / 接口块注入）零改动——正是 led spec User Story 11 预告的
扩展口兑现，key 只做「manifest 加块 + 策略行 + 渲染 hook + 词表」。

同时把 led 首例留在展开层里的 led 专属语义（内置色→宏名、内置色指定脚、
变体词表单源）下沉为「按 slug 的策略表」：led 一行（现行为钉死零变化）、
key 一行（新语义）。变体词表供 llm 提示词与解析校验同源消费（沿 led
「词表只改那一处」纪律）。

模块 API 从单键 `get_key_state(void)` 泛型化为通道式 `get_key_state(uint8_t
channel)` + `key_init()`（stm32 逐通道配置内部上拉输入；mspm0 由 syscfg 配置，
空实现）——沿 led 的 led_init(channel) 泛型化先例：单实例路径行为等价，代码
文本从硬编码变泛型。

## User Stories

1. 作为学生，题目要「启动键 + 设置键」时，我可以在配置里选 2 个 key 实例，而不是只有 1 个按键。
2. 作为学生，每个按键实例有独立显示名（启动 / 停止 / 模式 / 设置…），一眼分清用途。
3. 作为学生，内置变体 start/stop/mode/set 生成通道宏 `KEY_START` / `KEY_STOP` / `KEY_MODE` / `KEY_SET`，代码语义可读（按开始键 = `get_key_state(KEY_START)`）。
4. 作为学生，同一变体第 2 次起生成 `KEY_START_2` 这类后缀宏，不会重名（led 内置色后缀先例）。
5. 作为学生，非内置 / 空变体的键生成 `KEY_1` / `KEY_2`… 按创建顺序编号。
6. 作为学生，我的代码只写 `get_key_state(KEY_START)`、`get_key_state(KEY_1)`，不背引脚。
7. 作为学生，生成后每个键的引脚与初始化自动配好，打开就能编译。
8. 作为学生，自动分配引脚和已有模块 / 母版占用冲突时，我能在板图上重绑那个键（多实例下实例脚是权威，绑定只管单实例默认——led 先例）。
9. 作为学生，旧式单键 key：生成产物行为与以前一致（单通道、PA2/PB3 默认脚、上拉低电平按下），不破既有工程习惯。
10. 作为用 AI 推荐的学生，题面写「3 个独立启动按钮键」时，推荐自动给 key×3 实例，我确认后仍可增删改（2026F）。
11. 作为用 AI 推荐的学生，题面没写数量时，实例卡自动预填 1 个默认实例（按键），可见可改。
12. 作为维护者，以后 beep / motor 等多实例只加一问策略行 + 注册渲染 hook，不改机制层。

## Implementation Decisions

### 能力声明（manifest，模块级）

沿 led 形状：`"multi_instance": {"max": 8, "variant": "function"}`。
`max` 上限（sanity）；`variant` = 区分实例的属性名（led = color，key = function——
键的区分维度是「功能」，与内置变体 token 表呼应）。旧 manifest 缺块 = 单实例。

### 内置变体词表（单源 = 展开策略表）

`start` → `KEY_START`、`stop` → `KEY_STOP`、`mode` → `KEY_MODE`、`set` → `KEY_SET`；
同一变体第 2 次起加 `_2` 后缀；词表外 / 空变体 → `KEY_1`…`KEY_N` 按创建序。
词表只存在于展开策略表一处（提示词可见契约与解析校验同源，改词表只改那一处）。

### API 契约（模块代码泛型化）

- `uint8_t get_key_state(uint8_t channel)`：上拉输入，低电平 = 按下返回 1；
  channel 越界钳回首通道（led 先例）。
- `void key_init(void)`：stm32 = 逐通道 `gpio_init(端口, 脚, 上拉输入)`；
  mspm0 = 空实现（syscfg 已配输入，SYSCFG_DL_init 生效）。
- 通道表头：stm32 落工程根（与 pin_config.h 同级、母版自带默认随母版复制——
  沿 led 先例；驱动引号 include 经工程根 IncludePath 解析）；mspm0 落模块
  code 目录（引号 include 自目录优先，随模块复制）。模块目录双平台共享，
  不能放同名不同内容的文件，故沿用 led 的「stm32 母版根 / mspm0 模块目录」
  两落点。
- 通道表头内容（双平台各自形态）：`KEY_CHANNEL_COUNT` + 通道索引宏
  （`KEY_START`=0…）+ 每通道 (port, pin) 对表；纯表不渲染便捷宏（读函数已够
  简短，与 led 的 _ON()/_OFF() 不同）。
- 默认（空计划）通道表 = 1 通道：stm32 引用 pin_config.h 的 `KEY_GPIO/KEY_PIN`
  （接线单源照旧）、mspm0 引用 syscfg 生成的 `KEY_PORT/KEY_START_PIN`。
- 单实例路径零写侧变化：空计划 = 渲染 hook 不写（默认文件随母版 / 模块复制
  就位）。

### 展开策略（泛化，沿 led 契约）

按 slug 策略表（led 行 = 现行为逐字钉死；key 行 = 新行为）：

- 宏命名：builtin 变体 → 宏名（同变体后缀）；其余 `KEY_<n>`。
- 默认脚：首个实例 → 平台默认键脚（stm32 PB3 / mspm0 PA2——位置语义，沿
  mspm0 led「首实例板载脚」先例，不同平台统一位置语义）；其余按 board 顺序
  首个可用 `gpio_in` 能力脚（同模块内去重）。
- 与母版固定占用 / 其它模块默认脚冲突 = 用户重绑，generate-time 门禁照旧
  当安全网，不新增「找不到空闲脚」的硬 400（led D3 同口径）。
- 声明了 multi_instance 但策略表未登记 slug = 大声失败（防半吊子 manifest）。
- 实例上限守卫（>max SelectionError）与解析校验（name 非空 / variant·pin
  字符串）机制不变，自动覆盖 key。

### 渲染 hook（KeyInstanceRenderer）

- 计划 → 覆写通道表头（沿 led 两落点：stm32 工程根、mspm0 模块 code 目录；
  空计划 = 不写）。
- mspm0 多实例另写 syscfg：通道 0 复用母版 KEY 输入实例（板载 PA2 偏置），
  计划脚 ≠ 现值 → 改 `KEY.associatedPins[0].pin.$assign`；通道 1+ 追加
  `KEY_<实例号>` GPIO 输入实例（pin `$name` 全局唯一判例——`KEY<实例号>`
  形态，direction = INPUT，不配内部电阻：沿母版全部输入实例先例，板载偏置 /
  外置上拉；内部上拉是否可配留待后续验证）。
- 骨架 / 冒烟接口块：注入通道表全文 + `key_init()` 与逐个
  `get_key_state(<通道宏>)` 提示（喂 LLM 的宏清单 = 工程实际生成的宏）。
- `managed_headers` 声明接管文件（接口块剔除库内基线，防 LLM 见默认 + 计划
  两份矛盾宏——led 教训）。

### AI 推荐链路

- 多实例规则段 + 输出契约的变体词表从「led 单表」泛化为「按 slug 词表」
  （策略表投影；led 段文本词表来源不变，内容随泛化保持）。
- `_parse_model_instances` 能力清单校验自动覆盖 key（manifest 加块 →
  ManifestSummary 自动带 multi_instance 标注）。
- 默认回填：平台默认清单泛化为按 slug（led 现行为保持 += key = 1 实例，
  显示名「按键」、变体 start——对应板载启动键语义）。

### 前端

- 多实例卡 / 增删改 / 回填管线已通用（manifest 驱动），key 自动出现；
  实例显示「变体 = function」。
- 板图选脚候选从硬编码 `gpio_out` 能力改为按模块首 pin 角色类型（key =
  gpio_in；led = gpio_out 不变），选脚提示文案同步。

## Testing Decisions

- 好测试 = 只测外部行为：渲染纯函数（计划 → 头文件全文 / syscfg 文本，
  字符串进字符串出，默认文本与盘上逐字节钉死）；展开纯函数（清单 → 宏名 /
  默认脚计划）；零回归（旧请求无 instances → 生成写侧与现状逐字节一致；
  led 策略行现行为不回退）。
- 沿用既有测试缝（不新增）：
  - 渲染 / 展开 / 零回归 → `tests/test_module_multi_instance.py`；
  - 展开策略与默认回填 → `tests/test_selection.py`（既有
    default_instance_plan 断言随按 slug 泛化更新，led 行为保持）；
  - llm 提示词 / 输出契约词表段 → 既有 llm prompt 测试文件；
  - 真机编译：`.scratch/module-multi-instance/compile_matrix.py` 流程
    （UV4 / gmake 0 error、0 module warning；mspm0 多实例产物经 SysConfig
    生成真机验证——syscfg 追加实例块唯一无法纯单测的环节）。
- 编译验收口径沿 module-polish：0 error、0 module warning，基线 warning
  允许并记录。

## Out of Scope

- 矩阵键盘（4×4 扫描）——本特性是独立按键多实例；拨码开关等同形态可复用
  gpio_in 多实例表达，但不设专门设计；
- 消抖 / 边沿检测 / 长按等时序逻辑——模块只做原始读取（用户拍板；ADR 0009
  状态机 / 时序归生成骨架 + 参考文件库素材）；
- mspm0 内部上拉配置（有外置偏置先例，待验证后另行）；
- beep / motor 等其它模块的多实例开放——机制已就位，manifest 未声明 = 单实例
  不变；
- 生成后编辑持久化（v1 口径照旧）。

## Further Notes

- 命名撞名说明：通道宏 `KEY_START` 与引脚角色 id `KEY_START` 同名不同
  空间——角色 id 是绑定 UI / 接线单源（KEY_START（启动按键）），通道宏是
  key_instances 里的 C 宏；两者语义同源（同一启动键），不同标识符空间
  （mspm0 的 `KEY_START_PIN` 是 syscfg 生成的独立宏），无冲突。
- mspm0 板载键 = KEY 实例（PA2，板载 100k 偏置，pin `$name` = START）；
  新实例 pin `$name` = `KEY<实例号>`（与实例名 `KEY_<实例号>` 对应，
  SysConfig pin 名全局唯一判例）。
- led 教训引用：多实例下通道脚以实例计划为准（pin_config.h / 绑定只服务
  单实例默认）；接口块注入剔除库内基线。
- 2026C 门锁 4 位拨码（常设输入）+ 钥匙端一键启动（按键）+ 手动改 ID
  （按键组合）——多实例按键覆盖后两者；拨码用 4 实例 gpio_in 表达可行，
  留待骨架逻辑。
