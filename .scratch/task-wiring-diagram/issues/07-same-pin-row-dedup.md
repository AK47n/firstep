# 07 接线行同脚去冗余（单实例单行）

Status: resolved

## 要做什么

用户实测反馈（06 交付后）：t4（声光提示）接线图「led · LED」与「led · LED_RED」两盒接同一焊盘 PA15，困惑「怎么两个 LED 接一个脚」。用户判断：只有一个 LED（默认单实例），**就应该只有一行——数据逻辑问题**（非渲染）。

根因：led 模块（mspm0）manifest 声明角色 `LED@PA15（必接）` + 默认单实例计划（1 通道 → 宏 LED_RED，pin 解析为默认 PA15）→ `_pin_row_items` 输出声明行 + 实例行，同脚双行（物理同一条线）。

**评审整改（规格轴 1521feee）**：初版按 `(slug, pin)` 全键去首重会误删「同脚多角色」合法行——与 ADR 0010（合法共享 → 不拆，返回 shared 标注；先例 `tests/test_pin_bindings.py:829`、`tests/test_webapp.py` motor MOTOR_A_DIR/DIR2 同绑 PB12 保留双行）正面冲突。已收紧为「**只删实例行与既有行同 (slug, pin) 的实例行**；声明行之间同脚多角色必须保留；解析端不去重（表格文本无法判行来源），legacy 层按模块库声明集判源」——见下方变更面（评审整改版）。

## 被谁阻塞

无（06 已提交）。

## 变更面（评审整改版）

- `src/contest_generator/readme.py`：
  - `_pin_row_items`：声明行全保留并记入已见键；实例行仅当 `(slug, pin)` 未出现过才保留（声明行先于实例行 → 保留声明行；实例通道行仅在 pin 与既有行不同时保留——如 LED_YELLOW@PA16）。README 表 / `.contest_wiring.json` rows / LLM 接线摘要（同源推导）自动一致。声明行之间的同脚多角色（ADR 0010）从不删除；
  - `parse_pin_table`：**不做去冗余**（解析 = 忠实恢复；同脚多行来源不可判，去重交给 legacy 层按模块库声明集判定）。新生成 README 已无冗余行，round-trip 仍逐行相等。
- `src/contest_generator/wiring.py`：
  - `read_wiring_snapshot_legacy(output_dir, module_library_dir=None)`：解析 rows 后，库可读时按模块库声明集判来源——`role_id ∈ 该模块声明引脚 id 集`（`library.list_modules` + `ModuleManifest.platforms[platform].pins`）＝声明行保留；否则实例行候选，仅当 `(slug, pin)` 与既有行重复才删除；库缺失 / 不可读 / 参数 None / 无该模块或该模块无声明 → 保守不去重（原样返回，宁多勿丢）。私有 `_declared_role_ids` / `_dedup_legacy_instance_rows`；
  - 模块头说明补 07 一句。
- `src/contest_generator/webapp.py`：`/api/wiring` 兜底调用传 `_current_config(context)` 的 `module_library_dir`（config 未配置 → None → 保守不去重）；docstring 更新。
- 测试：
  - `tests/test_readme.py`：`test_render_readme_multi_instance_appends_rows` mspm0 断言改单行（LED_YELLOW@PA16 保留、LED_RED@PA15 去重）；`test_pin_rows_dedup_same_pin` 扩展「同脚多角色共享保留」（同一模块两声明同脚 → 双行）；`test_parse_pin_table_dedup_same_pin` 改为 `test_parse_pin_table_preserves_duplicate_rows`（解析端双行 → 双行）；round-trip 仍逐行相等；
  - `tests/test_wiring.py`：顶部 import 补 `PinDeclaration/PlatformEntry/ExpandedInstance/PLATFORM_MSPM0`；新增 `test_wiring_rows_dedup_only_instance_rows_same_pin`（wiring_rows 层：实例行删 / 声明行共享保留）、`test_read_wiring_snapshot_legacy_dedups_instance_rows_with_library`（legacy + 模块库判源：led 双行 → 单行、motor 同脚声明共享保留）、`test_read_wiring_snapshot_legacy_keeps_rows_without_library`（库 None / 不存在 / 损坏 / 无声明 → 原样双行）；
  - `tests/test_webapp.py`：`test_api_wiring_readme_fallback_dedups_same_pin` 改为带模块库（`dataclasses.replace` 切 config.module_library_dir）→ 单行；库缺失 → 保守双行；兜底失败仍空载荷。
- 规格 `.scratch/task-wiring-diagram/spec.md`：「工单 07」节改评审整改版（规则 = 仅实例行去重；解析端不去重；legacy 用模块库声明集；缺失保守）。

## 验收标准

- [x] led（mspm0）默认单实例：接线表一行 `led | LED | PA15 | gpio_out（必接）`（无 LED_RED 重复行）；
- [x] 多实例 2 通道（LED_RED@PA15 / LED_YELLOW@PA16）：声明行 + LED_YELLOW 行（LED_RED 与声明同脚去重）；
- [x] 实例 pin 与声明默认不同（如 LED_RED@PA14）：实例行保留；
- [x] 同脚多角色（ADR 0010 合法共享，如 MOTOR_A_DIR / MOTOR_A_DIR2 同绑 PA6）：两声明行都保留；
- [x] 旧工程（README 双行盘存）+ 模块库可读：legacy 解析返回单行（21 行），前端 t4 图单个 LED 盒；模块库缺失 → 保守双行（不猜测，宁多勿丢）；
- [x] round-trip（render → parse → wiring_rows）逐行相等（新 README 无冗余行，两端不冲突）；
- [x] 全量 pytest 2801 + tests/js 662 绿；评审两轴通过后提交（中文提交信息 9212080 + CHANGELOG b7ad62e）+ 本工单 resolved。
