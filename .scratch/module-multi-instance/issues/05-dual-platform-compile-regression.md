# 05 — 双平台编译回归（1/2/4 灯 + 旧单实例）

**What to build:** led 多实例 1/2/4 个灯在 stm32 UV4 与 mspm0 gmake 真编译 0 error、
0 module warning；旧单实例 led 产物与基线逐字节 diff 为空。这是全功能的关门验收票。

**Blocked by:** 03

**Status:** resolved

- [x] 1 灯 / 2 灯 / 4 灯三档，stm32 UV4 真编译 0 error、0 module warning
- [x] 1 灯 / 2 灯 / 4 灯三档，mspm0 gmake 真编译 0 error、0 module warning（syscfg ovsRate 基线 warning 允许并记录）
- [x] 4 灯覆盖内置色 + 重复色 + 非内置色，产物里通道宏 / pin 宏 / 初始化逐项核对
- [x] 旧单实例 led 行为一致（API / 引脚 / 通道不变）；`pin_config.h` / syscfg 逐字节不写（`pinwriter` 不变不写契约兜底）；`ml_led.c/.h` 泛型化后不追「逐字节 diff 为空」（spec D4 定案）
- [x] pytest 全绿 + mypy src 干净
- [x] 编译结果留痕到 `.scratch/module-multi-instance/`（build log 本地证据）

**Notes:** 关门验收，**零生产代码改动**（预期内）。补了 3 条产品断言 + 编译矩阵脚本。

**编译矩阵（`.scratch/module-multi-instance/compile_matrix.py`，真机 UV4/gmake）**：
四档 × 双平台全 PASS（`matrix_results.md` 摘要 + `matrix/*/build.log` 本地证据，
matrix/ 目录 gitignore 照 module-polish 先例不入库）：

| 档 | stm32 UV4 | mspm0 gmake |
|---|---|---|
| 单实例（旧行为） | 0 Error / 0 Warning | exit 0，无 module warning |
| 1 灯（红） | 0/0 | exit 0 |
| 2 灯（红+绿） | 0/0 | exit 0 |
| 4 灯（红+红+绿+状态灯） | 0/0 | exit 0 |

4 灯产物逐项核对（期望列 → 实际）：LED_RED=0/LED_RED_2=1/LED_GREEN=2/LED_1=3；
stm32 脚 PC13/PA0/PC15/PA1、mspm0 脚 PA15/PA0/PA1/PA28（syscfg 追加
LED_2=PA0/LED_3=PA1/LED_4=PA28，pin 名 LED2/LED3/LED4 全局唯一——03 判例）。
每实例 led_init 落 main.c，4 灯含 LED_RED_2 / LED_1 不误占位，真编译 0 error 即证
通道宏与驱动链自洽。

**补的产品断言（`tests/test_module_multi_instance.py`，+3 测试）**：矩阵精确组合
红+红+绿+状态灯此前无直接断言（既有测试用红/黄/绿/状态灯，缺重复内置色）。新增
`test_expand_matrix_4_light_builtin_duplicate_nonbuiltin`（命名 + 默认脚逐项）、
`test_render_matrix_4_light_channel_and_pin_macros`（通道宏值 + stm32 GPIO_x/Pin_y +
mspm0 LED_<n>_* 宏逐项）、`test_generate_smoke_main_matrix_4_light_all_channels_preserved`
（冒烟全通道含 LED_RED_2/LED_1 不误占位）。1707 passed（基线 1704 + 3）。

**红证发现（非生产 bug，测试写法纠正）**：冒烟矩阵测试初版对 stm32 未传
`master_project_dir` → `led_init` 被判未定义、改写占位（led 在 stm32 侧 files 空、
内嵌母版，声明在 ml_led.h）。webapp 生产路径已传 master_dir（`webapp.py:690`
`generate_smoke_main(... master_dir ...)`），故非 bug；测试改为传 `STM32_MASTER`
对齐生产调用，顺带钉死「stm32 冒烟 led_init 依赖母版接口块注入」这一依赖。

**syscfg「逐字节不写」口径**：单实例 mspm0 的 syscfg 不与母版逐字节相等——那是
`syscfg-prune/01` 独立特性按选中模块裁剪未选实例（I2C_0 等）的合法变化，与多实例
无关。多实例的「不写」核对 = 空计划下 `_write_syscfg_for_plan` 不落盘，编译矩阵以
「syscfg 无 `const LED_<n> = GPIO.addInstance`」精确断言；逐字节级契约已由
`test_generate_mspm0_single_led_default_header_and_no_syscfg_write`（假母版无 prune）
钉死。stm32 侧 led_instances.h / pin_config.h 逐字节不写、mspm0 侧 led_instances.h
逐字节不写，编译矩阵以母版/库内默认 diff 空核对。

**code-review 双轴（手动，改动极小）**：Standards——新测试沿用既有 docstring /
断言风格（`_expand`/`_macros`/`_pins` 助手、re.search 通道宏断言），无违规；
compile_matrix.py 照 module-polish/04 + module-functionalize 脚本先例，是 scratch
验证工具非生产代码。Spec——三条断言精确对上验收 2（矩阵 4 灯三类命名）/验收 3
（冒烟不误占位）/ 矩阵编译对验收 1/3/4。无 material 缺陷。

**已知不追（03 判据⑤）**：stm32 `led_toggle` 反转 bug 是 HEAD 既有、行为一致契约下
不改（本票矩阵 main.c 只用 led_init，未触发 toggle），另行立项。
