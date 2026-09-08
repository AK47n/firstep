# 01 — beep 补引脚声明 + 「源码引脚宏必须有主」全库不变量

**要做什么：** 蜂鸣器出现在引脚绑定界面与默认布局里、与别的器件抢脚时生成期门禁会报错；同时新增一条全库结构测试，保证以后没有模块能偷用未声明的引脚宏。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `beep` 的 stm32 平台条目补一条引脚声明（`gpio_out`，默认 PA15，宏 `BUZZER_GPIO` / `BUZZER_PIN`），与 `code/beep_stm32.c` 实际用法一致。
- [x] 实测冲突被看见：`beep` + `jq8900` 同吃 PA15 时，既有引脚冲突能力（`auto_assign_bindings`，即绑定界面与生成期门禁的数据源）把两者标成 `kind=conflict` 并点名 beep（此前该组合一条标注都没有）。注：本仓库对同脚物理冲突的机制是「标注」而非硬 raise（`resolve_bindings` 明确重复绑定不拦，硬 400 只覆盖 TIM/EXTI/UART 实例级冲突），故验收以标注为准——见 Comments「与 spec / 工单口径的两处校准」。
- [x] 蜂鸣器引脚出现在绑定界面与默认布局白名单里（默认 PA15）。
- [x] 新增 `tests/test_library_invariants.py`：模块源码用到的引脚宏必须能被自身或依赖闭包内模块的声明溯源，差集即失败并列出「模块 / 宏 / 出处文件」。
- [x] 该测试在修复前对 `beep` 红、修复后全库绿；对 `debug_uart`（依赖 `config` 合法）始终绿。
- [x] mspm0 条目与两平台代码文件零改动。
- [x] 既有引脚相关测试全绿，含母版宏双向对齐测试（373 个宏）。

## Comments

### 改动清单（相对仓库根）

| 文件 | 改动 |
| --- | --- |
| `library/modules/beep/manifest.json` | stm32 条目补 `pins`（一条：`id=BUZZER_OUT`、`type=gpio_out`、`default=PA15`、`required=true`、`macros=[BUZZER_GPIO, BUZZER_PIN]`）+ notes 补一行说明；mspm0 条目逐字节不动 |
| `tests/test_library_invariants.py` | 新增（6 个用例） |
| `tests/test_default_layout.py` | PA15 共享白名单登记 `beep.BUZZER_OUT`（声明进默认布局后共享角色漂移，白名单是唯一需要跟着走的数据） |

未改：`library/modules/beep/code/**`（两个平台代码文件零改动，`git diff` 可验）、`src/contest_generator/**`、spec。

### 新增测试（`tests/test_library_invariants.py`，6 个全绿）

```
tests/test_library_invariants.py::test_module_source_pin_macros_traceable_to_declarations PASSED
tests/test_library_invariants.py::test_pin_macro_vocabulary_grounded_in_master PASSED
tests/test_library_invariants.py::test_debug_uart_stays_green_via_dependency_closure PASSED
tests/test_library_invariants.py::test_beep_stm32_buzzer_macros_are_declared PASSED
tests/test_library_invariants.py::test_beep_and_jq8900_share_pa15_is_reported_as_conflict PASSED
tests/test_library_invariants.py::test_beep_declaration_reaches_pin_binding_payload PASSED
============================== 6 passed in 0.13s ==============================
```

不变量语义：扫 `library/modules/*/code/*.c`（注释剥离后）里出现的引脚宏 → 与「该模块自身声明 ∪ 依赖闭包内各模块声明」比对，差集即失败，失败信息形如
`模块 beep 的 code/beep_stm32.c 用了未声明的引脚宏：BUZZER_GPIO、BUZZER_PIN`。
依赖展开复用 `selection.resolve_dependencies`（未另写遍历）；宏名单取源不靠手写词表（全库声明 macros 全集 + 母版 `pin_config.h` 机械抽取做独立校验面）；只断言外部行为，不钉声明字段顺序、不钉模块清单。

### 红证（修复前红，工作树内实测）

复跑命令：`python -X utf8 .scratch/beep-pin-declaration/probe_red.py`
（该脚本只在内存里摘掉 beep 的 `pins` 声明——等价于补声明之前的清单——再跑本文件里的用例，不改工作区任何文件。）

```
RED  test_module_source_pin_macros_traceable_to_declarations: 模块源码偷用未声明的引脚宏：
RED  test_beep_stm32_buzzer_macros_are_declared: AssertionError()
RED  test_beep_and_jq8900_share_pa15_is_reported_as_conflict: PA15 未被标注（beep 仍不可见？）
GREEN test_debug_uart_stays_green_via_dependency_closure
```

补声明之前，直接跑新文件的原始输出（TDD 第一步）：

```
tests/test_library_invariants.py:149: AssertionError
E       AssertionError: 模块源码偷用未声明的引脚宏：
E         - 模块 beep 的 code/beep_stm32.c 用了未声明的引脚宏：BUZZER_GPIO、BUZZER_PIN
3 failed, 2 passed in 0.34s
```

`debug_uart` 全程绿（它驱动 LED/BUZZER 但 `dependencies=("config",)`，闭包溯源合法——「依赖合法」一侧的反向守卫）。

### 绿证（修复后全库绿）

```
$ python -m pytest tests/test_library_invariants.py -q
6 passed in 0.12s

$ python -m pytest tests/test_library_invariants.py tests/test_pins.py tests/test_default_layout.py tests/test_pin_bindings.py tests/test_module_led_beep.py -q
91 passed in 1.16s
```

母版宏双向对齐（373 宏）由库审计脚本复核（`.scratch/library-audit/audit.py`，与既有 `tests/test_pins.py` 双向断言同一判据）：
`python -X utf8 .scratch/library-audit/audit.py` → `BLOCKER 0`、`[宏]` 类无新增风险项（BUZZER_GPIO/BUZZER_PIN 本就在母版、且早已被 config 声明，对齐关系不变）。

### 全量 pytest

```
$ python -m pytest -q
3852 passed, 6 xfailed, 3 warnings in 147.55s (0:02:27)
```

（中途一次全量跑曾出现 26 个 recommend 流程用例失败 + `tests/test_llm.py` 采集报错——那是并行工单正在改 `selection.py` / `llm.py` / `webapp.py` / `tests/test_llm.py` 的瞬时中间态；等它写完再跑即全绿，与本工单改动无关。）

### 门禁验证（beep + jq8900 同吃 PA15）

生成期引脚冲突能力的唯一实现 = `pin_bindings.auto_assign_bindings`（`/api/bindings/auto` 端点与前端 pinShareClass 同一数据源；`resolve_bindings` 只校验用户传的绑定，默认×默认组合走这里标注）。新用例 `test_beep_and_jq8900_share_pa15_is_reported_as_conflict` 就是这条断言，可复跑命令：

```
$ python -X utf8 .scratch/beep-pin-declaration/probe_gate.py
=== 场景 A 修复前（全库选中） ===
  roles : ['config.BUZZER', 'ili9341.ILI9341_BLK', 'ili9488.ILI9488_BLK', 'jq8900.JQ8900_TX', 'lcd.LCD_BLK', 'st7789_para.ST7789_PARA_BLK']
  kind  : conflict
  reason: 同引脚但分属不同外设（物理不通）——请改线
  beep 可见: False；jq8900 在组内: True
=== 场景 A 修复后（全库选中） ===
  roles : ['beep.BUZZER_OUT', 'config.BUZZER', 'ili9341.ILI9341_BLK', 'ili9488.ILI9488_BLK', 'jq8900.JQ8900_TX', 'lcd.LCD_BLK', 'st7789_para.ST7789_PARA_BLK']
  kind  : conflict
  beep 可见: True；jq8900 在组内: True
=== 场景 B 修复前（仅 beep + jq8900） ===
  PA15 无标注（同脚冲突静默放行）
=== 场景 B 修复后（仅 beep + jq8900） ===
  roles : ['beep.BUZZER_OUT', 'jq8900.JQ8900_TX']
  kind  : conflict
  reason: 同引脚但分属不同外设（物理不通）——请改线
```

### 与 spec / 工单口径的两处校准（未改 spec，如实登记）

1. **「生成期门禁报错」的准确机制**：本仓库对「同脚物理冲突」没有硬 raise 的门禁——`resolve_bindings` 明确「重复绑定不拦」，冲突以 `kind=conflict` 标注的形式返回给前端（`pin-share-rule/01` 口径）；硬 400 只覆盖 TIM/EXTI/UART 实例级冲突。所以本工单的验收以「既有引脚冲突能力（`auto_assign_bindings`）看得见 beep 并标 conflict」为准，而不是新增一个 raise 门禁（那会改 `generator.py` 门禁表，超出本工单范围且与并行工单冲突）。
2. **「静默通过」的准确范围**：全库选中时 PA15 本来就有 `config.BUZZER` 在组里（config 与 beep 共用 `BUZZER_GPIO/BUZZER_PIN` 宏），PA15 一条 conflict 标注并非完全不存在——真正静默的是 **beep 本身**（不出现、不可改绑）与 **config 不在场时的组合**（场景 B 才是一条标注都没有）。修复后两种情况都点名 beep。

### 遗留风险

- `beep` 与 `config.BUZZER` 声明同一物理脚（PA15）且共用同一对宏，两模块同选时是「同一脚两个角色」，与 `config.LED_*` 既有重叠同性质（默认布局白名单已登记）——用户改绑 beep 的脚会同时写 `BUZZER_GPIO/BUZZER_PIN` 两个宏，也就是连带改了 config 的蜂鸣器脚。这是宏单源（母版 `pin_config.h`）决定的既有耦合，本工单不拆。
- 新不变量只看 `.c`（引脚宏的实际使用面）；`.h` 里的引脚宏引用暂不在扫描范围（现状无此形态）。
