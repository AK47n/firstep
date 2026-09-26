# 07 — 多实例只验首路：页面上如实说

**要做什么：** 学生装了 4 个 LED（或 4 个按键）时，页面**明说**"多实例只验第一路"——
不再让"回显了通道数"看起来像"每一路都验过了"。

**被谁阻塞：** 无——可立即开始。执行纪律：本单与 08 都改配方数据文件
（`library/hwcheck_recipes.json`，盘上 **LF**、`core.autocrlf=true`——按 `hwcheck-hardening` 的
先例逐字节读写，别让文本模式换行归一制造整档重写）。按编号顺序落地。

**状态：** resolved

**来源**：评审 P2-13（Y3）。**本轮只做如实说明**，不按实例展开（展开要动配方 schema，见 spec「范围外」）。

## 现状（实测）

- `led` / `key` 声明 `multi_instance.max = 8`，而配方只调 `led_init(LED_RED)` /
  `get_key_state(KEY_START)`——**8 路只验第一路**；页面上另行回显通道数。
- 配方 schema 里没有"实例"这一维，`hwcheck.py` 内也没有实例展开——所以这不是配方写漏，
  是**能力缺口**；本轮把这句缺口如实写出来。

## 验收标准

- [x] 每一格凡声明多实例（`multi_instance.max > 1`）的配方，**页面渲染出来的文本里**必须有一句
      如实说明"只验第一路"（措辞自定，但要含"第一路 / 首路"这一层意思，且不夸大——
      **不许**写成"已验全部"或含糊的"支持多实例"）。
- [x] 守卫：全量配方里凡 `multi_instance.max > 1` 的格，渲染产物必须含该自述
      （判据按渲染输出而不是按 JSON 字段——照 `hwcheck-hardening/02`「未上板」那条守卫的先例）。
- [x] **反证**：撤掉其中一句自述 → 用例红；复原后配方文件**逐字节相同**
      （`.scratch/hwcheck-hygiene/probe-07-red.py` / `probe-07-red.txt`）。
- [x] 页面顶部那句总口径（`hwcheck-hardening/02` 立的"未上板"总口径）与这条**不重复、不打架**：
      一个是"没上过板"，一个是"只验了第一路"，两句各自说自己那件事。
- [x] 读法守卫：改配方后 `python -m pytest -n auto -q` 全套绿；配方文件的换行形态与
      `hwcheck-hardening/04` 定的口径一致（**LF**，别按 CRLF 处理）。

## 结论（读数与账）

**这笔做了什么。** 库内声明多实例（`multi_instance.max = 8`）的只有 `led` 与 `key` 两件、
× 两平台共 **4 格**。四格的平台说明里各补一句如实自述（**只验第一路**），并把它立成
**渲染产物级**的守卫。**不按实例展开**（要动配方 schema，spec 已划到范围外）。

**四格的措辞**（数据在 `library/hwcheck_recipes.json`，改法见下）：

| 格 | 那句自述落在哪条 note |
|---|---|
| `led × stm32` | 首条（讲 PC13/14/15 那条）末尾：「多实例只验第一路：工程里配了 4 路 LED 时…检测程序这一趟只驱动第一路（LED_RED）——通道数不是「每一路都验过」的意思」 |
| `led × mspm0` | 第二条（讲 `LED_CHANNEL_COUNT` 那条）中间：同上口径，并点明「回显的通道数说的是本工程有几路」 |
| `key × stm32` | 多通道那条（讲 `KEY_CHANNEL_COUNT`）：原句「本件只读首通道」之后补「多实例只验第一路（这一趟只驱动第一路，另外几路一个动作都没有）」 |
| `key × mspm0` | 同上（两平台那条多通道说明本来就同一句，替换按 2 处做） |

**数据怎么改的（逐字节）。** `library/hwcheck_recipes.json` 盘上是 **LF**（实测 3857 LF / 0 CRLF），
`json.dump` 整档重写会把缩进 / 键序 / 换行全排一遍——所以走 `.scratch/hwcheck-hygiene/`
里两支幂等脚本按**字节**锚点替换：`apply-07-notes.py`（补四句）、`apply-07-unmark.py`
（见下「评审整改」）。共用小工具 `patch_bytes.py`（评审整改时从两处重复实现里提出来）。

**判据（本单新造 4 条用例，都自带自证）。**

| 用例 | 判据 |
|---|---|
| `test_every_multi_instance_recipe_cell_discloses_it_only_tests_the_first_channel` | 凡 `max > 1` 的格，`sections_payload`（页面读的那份）与 `render_recipe_section`（产物那份）**都要**含「第一路」；格的清单**精确等于**四格（多一格少一格都红）；自述那句不许带 markdown 标记 |
| `test_multi_instance_overclaim_predicate_accepts_the_honest_negation` | 判据本体自证①：**否定式**（"通道数不是「每一路都验过」的意思"）不许被判违规 |
| `test_multi_instance_overclaim_predicate_rejects_the_positive_claim` | 自证②：**肯定式**（"已验全部" / "每一路都验过了" / "每一路都测过了"）必须报出来 |
| `hwcheckSectionNoteHTML：多实例的实话说进 DOM…`（**前端门禁**） | 载荷 → HTML 那最后一跳：真配方那句要印进 `.hwcheck-hint`，换个 note 就不该有 |

**反证（`probe-07-red.py` / `probe-07-red.txt`，三处注入各自复原）。**

| 处 | 注入 | 结果 |
|---|---|---|
| A | 撤掉 `led × stm32` 那句自述（= 开单前的老形态） | pytest 守卫 **1 failed**（点名那条）→ 复原 sha256 `2519a0bf…f7e9df` 逐字节相同 → 回绿 |
| B | 自述反过来（"多实例每一路都验过了"，2 处） | 同上 **1 failed** → 复原逐字节相同 → 回绿 |
| C | 撤掉自述 → **真浏览器** `tests/browser/hwcheck.spec.mjs` | **fail 1**（`test at tests\browser\hwcheck.spec.mjs:628`，AssertionError 就是那句"要在页面上如实说「只验第一路」"）→ 复原逐字节相同 → 回绿 |

> ⚠ 探针 C 第一版**报 FAIL**：它在注入态确实红了（`ℹ fail 1`、退出码 1），但我的失败行解析
> 面写窄了（只认 pytest 的 `FAILED` 与两行前那次误判留下的 `not ok`，node 的 spec reporter
> 用的是 `✖ 用例名 (1234ms)`）——**这不是判据没强度**。原始输出旁证落在
> `probe-07-capture-c.txt`（连"临时量具" `probe-07-capture-c.py` 一起留档，两件都是这次
> 定位的证据），解析改成认 `✖` 并读堆栈行号后三处全 PASS。
> 记账在此，因为"红在哪"和"解析器认没认出来"是两件事——本批的先例（`ci-gate-fixes` 的读数
> 纪律）就吃过一次"没被看见触发过的诊断不算证据"。
>
> ⚠ 另一条同源纪律：**探针不许与任何读数并行**（它会让配方文件在读数窗口内处于注入态——
> 本轮实测撞过一次：浏览器门禁与探针 C 同时跑，读数红在"页面上没有那句话"）。
> `hwcheck-specialize` 的第五条量具纪律早有同款（"会让配方文件变的探针不许与任何读配方的
> 验证并行"），本轮是它的第二次现场。

**读数（本机实跑，落盘在本目录）。**

| 闸门 | 读数 | 文件 |
|---|---|---|
| 全套 pytest | **5603 passed + 11 skipped**（基线 5600 + 11；+3 = 本单三条用例） | `probe-07-pytest-full.txt` |
| 前端门禁 | **1819 / 0**（基线 1818 / 0；+1 = 渲染那一跳） | `probe-07-js.txt` |
| 浏览器门禁 | **48 / 0**（条数不变：新断言落在既有那条用例里） | `probe-07-browser.txt` |
| 两平台真编译矩阵 | `led` / `key` × 两平台 **4 格全 PASS**（编译器 0 error / 0 warning，无链接器告警；页面标记都 `[专精]`） | `probe-07-compile-matrix.txt` |
| 双轴 code-review | Standards **无硬性违反**；Spec 4 条缺口 | 见下 |

**双轴评审（Standards / Spec，2026-09-26）与整改。**

| 评审发现 | 处置 |
|---|---|
| Spec 硬：工单要的是「**页面渲染出来的文本**」，守卫只读到 `sections_payload`（载荷），没走渲染那一跳 | 前端门禁补一条真调 `hwcheckSectionNoteHTML` 的用例（真配方数据）；反证补 C 段——撤掉自述 → 真浏览器那条用例红 |
| Spec 硬：工单第 4 条（与页顶「未上板」总口径不重复、不打架）无用例作证 | 判据的 docstring 说清二者分工，并把"页顶那条一个字都不含`第一路`"写成前提；**不加**"两份文案互不相似"这类弱断言（那种断言谁也不敢改文案） |
| Spec 硬：失败话术写「「首通道」这类说法也算数」而判据只认「第一路」——文档、代码、话术三处对不上 | 判据与话术统一到 `_MULTI_INSTANCE_MARKER` / `_MULTI_INSTANCE_PHRASE` 两个常量；常量注释里记下这次自相矛盾 |
| Spec 判：`_multi_instance_overclaims` 的否定豁免只看前 6 字（"并不能说明每一路都验过"会误报） | 窗口放宽到 12 字并单列常量；两条自证用例各补一种写法；函数 docstring 明说**它是绊线不是语义判据** |
| Spec 判：`**第一路**` 会原样印成字面星号（前端不解释 markdown） | **数据侧去掉标记**（`apply-07-unmark.py`，4 处）；判据补"本单新写的那句不许带标记"（只判这一句，存量 354 条是另一张单的账，见下） |
| Spec 判：`if not section.usable: continue` 静默跳过 | 记为**判据面的边界**并写进 docstring（与「未上板」那条同款门；不可用 = 配方残缺，加载期就红）；不加"至少 4 格"的地板——精确清单断言已经把四格钉死 |
| Spec 判：`probe-07-js/browser/pytest-full` 超出工单点名的读数文件 | 不处置：本批 spec「测试决策」要求 ui 行为由真浏览器作证，读数落盘是本目录的既有习惯 |
| Standards 判：`apply-07-notes.py` 的 `newline` 算完没用（死变量） | 删除，换行形态改由 `patch_bytes.newline_of()` 统一判定（两处漂移的写法一并收拢） |
| Standards 判：两份新脚本里"锚点校验 → 替换 → 落盘"是两份拷贝 | 提成 `patch_bytes.patch()`（**先全查后全写**：命中数对不上就整体不动） |
| Standards 判：`start - 6` 是无出处的魔数 | 改名 `_NEGATION_WINDOW = 12` 并写明"为什么是 12、为什么宜紧不宜松" |
| Standards 判：`apply-07-notes.py` 的复核只查四格（先例是全档复算） | 不处置：本单只改这四格，全档复算属 `test_hwcheck_recipe.py` 的活（那里已有 57/57 的地板） |

**记而不修（下一轮的账，别当已解决读）：**

1. **配方 note 里的 markdown 标记是存量**：`library/hwcheck_recipes.json` 的 367 条 note 里
   354 条含 `**…**`，而 `fx/hwcheck.js` 的 `hwcheckSectionNoteHTML` 只做 `esc()`——
   **页面上就是字面星号**。工单 02 立的口径（产品串不许带标记）当时只扫了
   `static/js/{fx,ui}/**` 的字符串字面量，**没有扫库内数据**。本单只保证**自己新写的那四句**
   不带标记，存量与判据面归**另开一张单**（要动 354 条 note 与既有的「未上板」守卫措辞）。
2. **多实例按实例展开**（一条 LED 一路一验）仍不在本批：要动配方 schema，spec「范围外」。
3. **07 这一跑浏览器门禁零 `[afterEach]` 告警**（三次读数都没有）——按 08 的口径这不是
   "告警无害"的结论，只是这次没复现；诊断归 08。

**未上板**：本单只改文案与判据，**没有任何板上行为被验证**（本机没有板子）。
四格自述本身说的就是"这一趟只驱动第一路"——那是**代码事实**（配方只调
`led_init(LED_RED)` / `get_key_state(KEY_START)`），不是板测结论。
