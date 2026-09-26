# 07 Spec 轴评审（工单 07-multi-instance-honest）

固定点 HEAD；仅评规格，不评编码规范。所有结论均按代码/数据实读，未采信工单自述。

## 逐项核实

1. **多实例格是否都带上自述、集合是否完整** —— 是，完整。实读
   `library/modules/*/manifest.json`：只有 `key`（`{"max":8,"variant":"function"}`）与
   `led`（`{"max":8,"variant":"color"}`）声明 `multi_instance.max > 1`（96 件里共 2 件）。
   这 2 件 × 2 平台的 4 格，`sections_payload` 与 `render_recipe_section` 两个出口都含「第一路」；
   数据里「第一路」恰好 4 处。守卫清单断言 `{"led × stm32","led × mspm0","key × stm32","key × mspm0"}`
   与实况一致（`pytest -k "multi_instance or unverified or on_board_status"` → 5 passed）。
2. **页面路径是否真被覆盖** —— 链路成立：`hwcheck_board.py:921` 把 `sections_payload(...)` 放进
   `board["sections"]` → `fx/hwcheck.js:762-764` 逐条印成 `.hwcheck-hint`。所以不是只覆盖 C 程序。
   **但守卫只走到载荷**：与先例 `test_every_real_recipe_cell_discloses_its_on_board_status` 同款
   （payload 断言），没有像 `tests/test_hwcheck_recipe.py:1201` 那种「真渲染一次」的调用。
3. **与页顶「未上板」总口径是否重复/打架** —— 不重复、不打架。总口径
   （`fx/hwcheck.js:354-358`）只说"尚未在真板上验证过：现有证据只到「能生成 + 能编译」"；
   新句说"只驱动第一路"。两件事，各自说自己那件。
4. **红证与逐字节复原** —— 成立。`probe-07-red.txt`：A 注入 1 处（撤句）→ 点名用例红、复原
   `2cbf88bc…d22c72c` 逐字节相同；B 注入 2 处（把只验一路说成全验了）→ 同样红、同样复原。
   实算当前 `library/hwcheck_recipes.json` sha256 = `2cbf88bc…d22c72c`，且 3857 个 LF / 0 个 CRLF
   （与 `hwcheck-hardening/04` 定的 LF 口径一致）。
5. **是否有声称而未取证** —— 见下 finding 3。

## (a) 缺失 / 半截

- 工单：「每一格…**页面渲染出来的文本里**必须有一句」，判据「按渲染输出」。守卫读的是
  `sections_payload([section])` 的返回值——是载荷，不是渲染产物：**没有调用渲染件**
  `hwcheckSectionNoteHTML`（`fx/hwcheck.js:761`），`probe-07-browser.txt` 里也 grep 不到任何
  「第一路」（该读数 23:34:04 跑，早于数据定型；且浏览器用例里本就没有这条）。工单第 4 条
  「与页顶总口径不重复、不打架」因此**没有任何用例作证**——只在 docstring 里断言。
- 判据字面比工单窄：工单要「含"第一路 / 首路"这一层意思」，实现硬编码 `"第一路" in page`，
  失败消息却写「「首通道」这类说法也算数」（`tests/test_hwcheck_recipe.py:1361-1364`）——说法与判据不符。

## (b) 未被要求的行为

- 新增 `probe-07-js.txt` / `probe-07-browser.txt`（工单只点名 `probe-07-red.py/.txt`）、
  `probe-07-pytest-full.txt` 的自制头、以及 3 条判据自证用例。规模小且对得上本批"读数落盘"习惯，
  不构成实质越界。

## (c) 实现看着对、实则有误

- `_multi_instance_overclaims` 的否定豁免有**距离 bug**：`head = text[start-6:start]`，
  只往前看 6 字。写法一变（如「回显的通道数并不能说明每一路都验过」）就会被误判为违规——
  而这条判据的存在理由正是"产品文案必须能这么写"。真库数据当前不受影响（2 处命中均为
  「…不是「每一路都验过」…」，实测 `flagged=False`）。
- `**第一路**` 会**原样印成字面星号**（`esc()` 转义、前端不解释 markdown）：页面上是
  `多实例只验**第一路**：…`。这与 `tests/js/hwcheck.test.mjs:411-414` 明写的口径相左
  （"产品串里不许带 markdown 标记"），也与本 spec 问题陈述 1 同类。**属既有惯性**
  （367 条 note 里 354 条含 `**`），不是本单引入，但本单新写的这句正是学生要读的那句，
  建议改掉标记。

## 结论

验收 1、2、3（数据完整性与两出口）、红证与逐字节复原、全量 pytest 均**成立**；
全量 pytest 读数尾部为 `5603 passed, 11 skipped, 32 warnings in 237.45s`、退出码 0，
JS 1818 pass / 浏览器 48 pass，未见红或漏跑。**主要缺口**：页面渲染这一环只有载荷级断言、
工单第 4 条无用例、判据字面与工单措辞不符。
