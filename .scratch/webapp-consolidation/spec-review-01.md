# 工单 webapp-consolidation/01 — Spec 轴评审（固定点 HEAD 6fc01208，工作树）

评审对象：`git diff HEAD` 中 `webapp.py` / `hwcheck_board.py` / `hwcheck_recipe.py` /
`tests/test_hwcheck*.py` / `tests/js/hwcheck.test.mjs` / `CONTEXT.md`
（忽略另一会话在途的 `docs/agents/local-environment.md` 与 `.scratch/pdf-dup-verify/`）。

结论：**搬运主体忠实**——无 ctx 适配层残留（4 个私有 helper 已删，四端点各自
`_hwcheck_library_config(context)` + 直调 `hwcheck_view`）、`hwcheck.py` 零改动、域层签名不吃
`AppContext`、`recipe_path` 注入面保留、`require_pins` 语义与四个端点取值照旧、既有断言零改动
（只 docstring 里的旧符号名改写）。评审时读数：hwcheck 面 360 passed / 全量 4994 passed,
1 skipped / `node --test` exit 0。

## (a) 缺失 / 半成品

- 验收「新直测缝（不经 HTTP，真库 + 真母版）：… **库外 slug 仍 400**」没做：新增直测只盖
  五字段 / `require_pins=False` / 坏配方；库外 slug 只有旧端点用例与 `hwcheck_board_view_for`
  的旧钉，`hwcheck_view` 这条新缝上没有。
- 验收「`board` 六键齐全」按字面未做（见 (c)1）。

## (b) 范围蔓延

- `read_master_syscfg` / `sections_payload` 新进各自模块的 `__all__` 成公开面。
- `load_library_recipes` docstring 自称「检测页与**生成侧**共用的入口」，而 `load_recipes`
  在 `src/` 里的唯一调用者就是它自己（生成侧无调用）。
- `tests/js/hwcheck.test.mjs` 注释改动，与工单「前端零改动」的字面口径相抵。

## (c) 实现有问题

1. **判据被改写、未回改工单**：工单判据写「`board` 的六个键（… / `pin_fixes`）」，而 HEAD 与
   工作树都只有 5 个顶层键（`pin_fixes` 在 `wiring` 内，前端读的也是
   `static/js/ui/hwcheck.js` 的 `wiring.pin_fixes`）；实现按五键写对了，但工单未更正。
   `tests/test_hwcheck.py` 的端点对账用例只做子集断言却写「载荷六键必须原样出现在响应里」
   ——断言弱于判据。（载荷值本身逐字未变。）
2. **错误时机**：`/api/hwcheck/project` 里取配置 + `hwcheck_view` 由 return 字典末位提前到
   `read_project_main_c` / `render_checklist` / `read_hwcheck_record` 之前 —— 同一请求里两个
   400 的先后被换（评审推断："坏记录文件 + 未配库时，报错从「检测记录…损坏」变成「还没配置
   模块库」"）。
3. **自记验证读数不自洽**：`verify-01-homing.txt` 称 `tests/test_hwcheck*.py` 354 passed
   （本单新增用例后实测 360）、board 文件「直调 4 条 + 结构钉 2 条」（实为 3+2）、全量 4993
   （实测 4994）。红证本身成立：`probe-01-pin-red-proof.py` 用 `git show HEAD:` 的源码喂同一
   判据输出 11 条泄漏 → 工作树 0 条，支持其结论。

## 处置（实施者回填，2026-09-20）

- (a)1、(c)1：补 `test_hwcheck_view_rejects_a_slug_outside_the_library`；用例断言收紧为
  **键集合全等**；工单判据/计划/验收三处的「六键」按实现更正为五键（并写明这是原口径的更正）。
- (b)：`read_master_syscfg` 撤出 `__all__`；`sections_payload` 保留（跨模块缝，
  `hwcheck_board` 导入它）；`load_library_recipes` docstring 改「检测页装配的装载入口」并点明
  「**提取**与生成门禁同一套 ≠ 生成侧也读配方」；`tests/js` 注释改动如实记账（产品
  `static/` 零改动）。
- (c)2：**代码已改回从前的求值顺序**，并加一条能分辨的用例
  `test_project_endpoint_reads_main_c_before_taking_the_library_config`（桩让 main.c 先抛：
  顺序错 → 报「还没配置模块库」→ 实测变红；改回即绿）。**评审推断的那一半经核对不成立**：
  取配置在两种顺序里都早于读记录，所以"坏记录 + 未配库"两种顺序都报配置那句——已在用例
  docstring 里写明，避免后人照错误推断再改一遍。
- (c)3：`verify-01-homing.txt` 已按最终读数重写（363 / 4996 并列出新增 9 条）。
