# 03 — rewrite 写侧切到文件模型（contract）

**What to build:** pinwriter 的 mspm0 写侧（`rewrite_syscfg` / `_locate_mspm0_site` / `_mspm0_path_matches`）委托给文件模型，删除 pinwriter 的 `$assign` 文法与路径匹配；stm32 写侧（`render_pin_config`）不动。

**Blocked by:** 02

**Status:** resolved

- [x] 绑定改写（换 `$assign` 引脚值 + uart/i2c/pwm 的 peripheral 行）产出与迁移前逐字节一致（test_pin_unlock_mspm0_same / _cross 绿）
- [x] 默认重叠布局的槽位定位（STEP_MOTOR SLP2 vs HUIDU R3 同 PB6/PB7）行为不变
- [x] pinwriter 不再持有 `$assign` 正则；只保留 stm32 写侧 + 写侧统一入口

**Resolution notes:**
- `rewrite_syscfg` 变薄委托 `parse_syscfg(master_text).rewrite(resolved).to_text()`，捕获 `SyscfgModelError` → `PinBindingError(str(exc)) from exc`（消息文案与旧实现逐字一致，写侧错误契约不变）。
- 删 pinwriter 8 个旧符号：`_SYSCFG_ASSIGN_RE` / `_MSPM0_PERIPHERAL_TYPES` / `_PERIPHERAL_PIN_FIELDS` / `_locate_mspm0_site` / `_mspm0_path_matches` / `_peripheral_path` / `_mspm0_instance_for_binding` / `_mspm0_peripheral_of`，顺带删 `INSTANCES_BY_SLUG` import；保留 stm32 侧 + `apply_pin_bindings` 分派 + `MSPM0_SYSCFG_FILENAME`（04 再迁）。
- 测试：test_pin_bindings.py 改指 `syscfg_model.syscfg_path_matches`；test_syscfg_model.py 删等价对照 `test_slot_path_matches_agrees_with_legacy_on_all_master_paths`（只剩一个实现后对照失义）+ spot 判例删旧断言；instance_render.py:113 注释里 `pinwriter._SYSCFG_ASSIGN_RE` → `syscfg_model._SYSCFG_ASSIGN_RE`（删除后悬空引用）。
- 验证：全量 pytest 1714 passed（较工单 02 的 1715 少 1 = 删掉的等价对照测试）；mypy src 45 文件干净。
- 评审遗留（不属本工单，留痕工单 04 或单独）：instance_render.py 的 `_LED_BEEP_ASSIGN_RE` 是 $assign 文法的专用副本（LED_BEEP 通道 0 落点），尚未收敛进文件模型——syscfg_model 独占文法声明未覆盖此副本。

**Notes（实施要点）:**
- `rewrite_syscfg` 变薄委托 `parse_syscfg(master_text).rewrite(resolved).to_text()`，捕获 `SyscfgModelError` 翻译回 `PinBindingError`（写侧错误契约不变；SyscfgModelError 是白名单、漏到 web 层会 500）。
- 删 pinwriter 的 `_SYSCFG_ASSIGN_RE` / `_MSPM0_PERIPHERAL_TYPES` / `_PERIPHERAL_PIN_FIELDS` / `_locate_mspm0_site` / `_mspm0_path_matches` / `_peripheral_path` / `_mspm0_instance_for_binding` / `_mspm0_peripheral_of`（模型内已有逐字节等价副本）。
- 保留 stm32 侧（`render_pin_config` + 宏尾形派发 + `_regroup_irq_calls` + 共享端口宏门禁）+ `apply_pin_bindings` 分派 + `MSPM0_SYSCFG_FILENAME`（04 再迁）。
- 测试波及：`test_pin_bindings.py:49/324` 与 `test_syscfg_model.py:22` 直接 import `_mspm0_path_matches`——改指 `syscfg_model.syscfg_path_matches`，或删等价对照（只剩一个实现后对照失义）。
