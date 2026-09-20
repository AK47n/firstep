# 工单 webapp-consolidation/01 — Standards 轴评审（固定点 HEAD 6fc01208）

范围：`git diff HEAD` 中的 `webapp.py` / `hwcheck_board.py` / `hwcheck_recipe.py` /
`tests/test_hwcheck_board.py` / `tests/test_hwcheck.py` / `tests/js/hwcheck.test.mjs` / `CONTEXT.md`。
（忽略 `docs/agents/local-environment.md` 与 `.scratch/pdf-dup-verify/`。）

## (a) 硬违规 / 文档一致性

无。逐条核过：语言规范（中文 docstring / 工单，未引入英文）；PowerShell 无涉及；
`webapp.py` 无残留未用 import（`Sequence` 等仍被别处用）；`_hwcheck_library_config` 的
400 触发位置按工单判据保持不变（四个端点都显式调它——回读/排障端点是**新增**调用，
但工单第 57 行要求如此，且 152 条聚焦用例全绿）。

文档失准一处（非硬违规）：工单 `issues/01-hwcheck-view-homing.md:14,25,58,59` 与
`verify-01-homing.txt` 沿用「board 六键（… / `pin_fixes`）」，而实现与
`hwcheck_recipe.sections_payload`… 实为**五键**（`pin_fixes` 住在 `wiring` 里）——
代码是对的（`HwCheckView.__doc__` 与新增测试已按五键写），是工单/验证读数这一版
口径没同步（六键是 09-19 改之前的形状）。

## (b) smell 基线

1. **Divergent Change / 错位的结构钉** — `tests/test_hwcheck_board.py:542-626`
   （`WEBAPP_PATH` / `_ALLOWED_HWCHECK_IMPORTS` / `test_webapp_import_surface_keeps_the_assembly_in_the_domain`）。
   「板侧投影」的用例文件里长出一张 **webapp import 白名单**：改 webapp 的 hwcheck import、
   或改 `hwcheck_recipe` 的 `__all__`，都要回来动这个板模块的用例文件。白名单表的位置
   就是它真正的归属（另起 `tests/test_webapp_hwcheck_surface.py` 之类）。
   证据：
   ```
   WEBAPP_PATH = REPO / "src" / "contest_generator" / "webapp.py"
   _ALLOWED_HWCHECK_IMPORTS: dict[str, frozenset[str]] = { ... "hwcheck_recipe": frozenset(), ... }
   ```

2. **Duplicated Code（数据）** — `tests/test_hwcheck.py:1078-1094` 新增用例里
   `repo / "library" / "modules"`、`repo / "library" / "masters"` 手抄了一遍，
   而 `real_library_client`（同文件 `:774-783`）就在同一个测试里提供了
   `ctx.config.module_library_dir` / `ctx.config.masters_dir`——本单刚把路径收成接口
   参数，测试却绕过那条缝自建第二份。
   证据：
   ```python
   module_library_dir=repo / "library" / "modules",
   masters_dir=repo / "library" / "masters",
   ```

3. **Feature Envy（判断题，已被工单认可）** — `hwcheck_board.py:444-544` `hwcheck_view`：
   六个依赖里四个是别人的域（recipe / console / generic / manifest），板侧只用到
   `hwcheck_board_view` + `hwcheck_pin_plan`；模块 docstring 第 21-24 行「它的三块输入
   分别住在 wiring / pin_bindings / readme 三个模块里」现在已不成立（真输入是
   library / masters / 配方）。工单第 24 行明确指定了落点，故按「文档明确认可压过基线」
   处理——但下次再有人往这函数加一段装配，就是该拆独立装配模块的信号。

4. **Mysterious Name（小）** — `tests/test_hwcheck_board.py:576-590`
   `_hwcheck_imported()` 返回的其实不是 import 到的名字，而是 `模块末段.名字` 形式的
   限定串（`item.split(".", 1)[1]` 反解两次）；`hwcheck_recipe.sections_payload` 也
   不点明它出的是**页面**载荷（同模块另有 `render_recipe_section` 出 C 代码）。
   证据：
   ```python
   out.add(f"{module}.{alias.asname or alias.name}")
   ...
   if item.split(".", 1)[1] not in _ALLOWED_HWCHECK_IMPORTS[item.split(".", 1)[0]]
   ```

5. **Speculative Generality（判断题）** — `hwcheck_board.py:93` 把 `read_master_syscfg`
   放进 `__all__`，但全仓无外部调用点（只有本模块 `:485` 用）；`sections_payload`
   的 `include` / `locals` / `prereq` / `platform` 字段页面不读，其 docstring
   （`hwcheck_recipe.py:1157-1165`）自陈「留着不算投机抽象」——理由是为下一张工单，
   可判为投机，也可判为配方契约（基线让位于文档，倾向后者）。

6. **不一致的失败策略（判断题）** — `hwcheck_board.py:124-141` `read_master_syscfg`
   吞掉 `OSError`（注释给了理由：判不了就不判），而同一批母版文件的读法在
   `hwcheck_recipe.load_library_recipes`（`:1012-1016`）里让异常往上走。两处都是有意
   选择、各有注释，仅提示「母版目录怎么读」现在有两个口径。

## 结论

无硬违规；(b) 1 与 2 值得当场修（都在测试里，改动小），3-6 是判断题。
