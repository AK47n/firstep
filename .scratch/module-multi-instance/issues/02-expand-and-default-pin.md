# 02 — 展开 + 默认脚分配（纯函数，重测）

**What to build:** 给定「led × N 实例清单」，一个纯函数产出 `(通道宏名, 默认脚)` 计划：
红/黄/绿 → `LED_RED/YELLOW/GREEN`，重复内置色 → `LED_RED_2`，非内置色按创建顺序 →
`LED_1..n`；默认脚确定性分配（stm32 红/黄/绿 PC13/14/15、其余按 board 顺序首个可用 io；
mspm0 首个 PA15、其余同），同模块内去重。超出 `max` 大声失败。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 展开纯函数：实例清单 → `(slug, 实例号, 宏名, 默认脚)` 计划，输入输出确定性（同输入同输出）
- [ ] 通道宏命名规则全落地：内置色、重复内置色 `_2`、非内置色 `LED_1..n` 按创建顺序
- [ ] 默认脚分配：stm32 PC13/14/15 优先、mspm0 PA15 优先，其余按 board 顺序首个可用 io 脚（`board_pin`/`pin_supports`/`pin_capability_instances` 复用），同模块内去重，不跨模块全局扫描
- [ ] 上限守卫：实例数 > `max`（8）抛错，中文可读
- [ ] 新测试 `tests/test_module_multi_instance.py`：命名 / 去重 / 后缀 / 默认脚 / 上限 全覆盖；pytest 全绿 + mypy src 干净
