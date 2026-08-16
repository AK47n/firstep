# 02 — 展开 + 默认脚分配（纯函数，重测）

**What to build:** 给定「led × N 实例清单」，一个纯函数产出 `(通道宏名, 默认脚)` 计划：
红/黄/绿 → `LED_RED/YELLOW/GREEN`，重复内置色 → `LED_RED_2`，非内置色按创建顺序 →
`LED_1..n`；默认脚确定性分配（stm32 红/黄/绿 PC13/14/15、其余按 board 顺序首个可用 io；
mspm0 首个 PA15、其余同），同模块内去重。超出 `max` 大声失败。

**Blocked by:** 01

**Status:** resolved

- [x] 展开纯函数：实例清单 → `(slug, 实例号, 宏名, 默认脚)` 计划，输入输出确定性（同输入同输出）
- [x] 通道宏命名规则全落地：内置色、重复内置色 `_2`、非内置色 `LED_1..n` 按创建顺序
- [x] 默认脚分配：stm32 PC13/14/15 优先、mspm0 PA15 优先，其余按 board 顺序首个可用 io 脚（`board_pin`/`pin_supports`/`pin_capability_instances` 复用），同模块内去重，不跨模块全局扫描
- [x] 上限守卫：实例数 > `max`（8）抛错，中文可读
- [x] 新测试 `tests/test_module_multi_instance.py`：命名 / 去重 / 后缀 / 默认脚 / 上限 全覆盖；pytest 全绿 + mypy src 干净

**Notes:** `selection.py` 落地 `expand_instances` + `ExpandedInstance`（frozen，slug/index/macro/pin）+ 三个私有助手（`_led_default_pin`/`_led_designated_pins`/`_next_led_pin`）。关键判据：① 指定脚（stm32 PC13/14/15、mspm0 PA15）**保留**给内置色首现 / 首实例——重复内置色与非内置色走 board 顺序「跳过指定脚 + 同模块已用」的 `gpio_out` 脚（`pin_supports` 复用），红/黄/绿 → PC13/14/15 固定映射不被抢占；② mspm0 首个实例 = 位置语义（非颜色），与 led 单 pin 角色默认对齐；③ 同模块内去重（`used` 集），不跨模块全局扫描，显式 pin 覆盖优先且入 `used`（后续自动分配不撞它）。上限守卫 = `SelectionError`（已登记 error_to_http 表 → 400 中文），未新增异常类。空实例清单 → 空计划（单默认实例旧行为），非 multi_instance manifest + 非空清单 = 调用方错误。防御：`occurrence=0` 兜底首实例非内置（否则 NameError）、`(variant or "").strip()` 兜底 None。35 passed（本文件）+ 全库 1651 passed + mypy src 干净（43 文件）。code-review 技能本会话不可用（disable-model-invocation），改用手动双轴 + 独立 review agent——agent 结论「无 correctness bug、无 spec 偏差」，4 条 minor 全为 by-design / 上游已校验 / 已修。
