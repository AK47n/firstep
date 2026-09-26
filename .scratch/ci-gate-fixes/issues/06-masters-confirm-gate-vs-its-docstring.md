# 06 — 蒸馏确认的闸门与它自己的 docstring 不一致（「无归档动作不要求 AI」）

**要做什么：** 让 `POST /api/masters/confirm` 的实际行为与它 docstring 写的判据一致：
**没有归档动作的确认不该要求 AI 配置**；有归档动作时，缺 key 要**在动手之前**中文拒绝
（而不是先落一批母版文件、走到归档那一步才 400）。

**被谁阻塞：** 无——可立即开始。**但它不是 `ci-gate-fixes/04` 的遗漏**：04 的射程
（库浏览/读取不被 key 闸住）与这条无关，是 04 盘点时**顺带量到**的既有不一致，
按「发现的真问题开单」记在这里（04 的 Comments「几处判断」表里点名了它）。

**状态：** resolved

- [x] 先定性：读出 `masters_confirm` 的两个分支——**无归档动作**（报告里没有 archive 条目）
      与**有归档动作**——各自现在走到哪儿才碰 `llm_factory`（见 Comments「定性」表：
      无归档 = 永不；有归档 = 事务内部、`apply_distillation` 之后 / `import_master` 之前）
- [x] 无归档动作那条路：改成不要求 key（闸门判据 = "库在哪"，与 04 抽出的
      `_resolve_library_config` / `_library_config` 同源），并保留一条用例钉住
      「空 key + 确认不归档 → 200，母版真的入库」
      （`test_confirm_without_archive_needs_no_ai_key_and_really_imports`，两种 wire 形状）
- [x] 有归档动作那条路：缺 key 时**在事务开始前**就 400 中文（现状是懒取
      `llm_factory`，400 可能落在半途）——判据 = 事务原子性（失败时磁盘零变化）
      ＋「那声 400 是闸门给的」＋「事务函数一次都没被进过」三条
- [x] 反向用例：有归档动作 + 空 key → 400 中文「未配置 AI API」，且**磁盘零变化**
      （母版库与参考库逐文件字节比前后）；反向的正常路（有归档 + 有 key）由既有
      `test_confirm_route_passes_archive_wiring` 继续钉着，本单未动
- [x] 中文提交

## Comments

### 立项事实（2026-09-25，量自 `ci-gate-fixes/04` 的盘点）

`src/contest_generator/webapp.py` 的 `masters_confirm`：

- docstring（函数级）写着「报告含归档动作（工单 02）时，归档条目随确认事务一起提交
  （LLM 判定 + 复制入库、锚定该题）；AI 服务与参考文件库目录按需取用——**无归档动作的
  确认不要求 AI 配置（与现状一致）**」；
- 代码却在函数开头**无条件** `config = _require_config(context)`（闸门判据 = 有非空
  `api_key`），随后才把 `llm_factory` 交给 `confirm_distillation`（也就是"按需"那一半
  确实做对了，`_llm` 只在归档时被调）。

于是：**没配 key 的机器上，一个不归档的确认也答 400**——与 docstring 相反。

为什么 04 没顺手改（`04` 的 Comments 有同一段）：把闸门放开会把缺 key 的 400 从
"动手前"挪到"归档那一步"，而那时事务可能已经写了一批母版文件——**事务语义要重新论证**，
不是一行替换。这正是本单第一条验收标准的由来。

### 定性：两个分支各自走到哪儿才碰 `llm_factory`（2026-09-26，动手前读码 + 反证）

| 分支 | 事务里的走法 | 什么时候碰 `llm_factory` |
|---|---|---|
| **无归档动作**（`report.archive == ()`） | `scan → compare → from_dict → apply_distillation(暂存) → import_master(真写盘)`；两处 `if report.archive:` 都不进 | **永不**——`llm_factory` 与 `reference_library_dir` 都不被取用 |
| **有归档动作** | 同上，但在 `apply_distillation` 之后多一步 `prepare_archive(...)`，其内部 `llm_factory()` → `LLMRun.llm()` → `_llm()` → `_require_config()` | **事务内部**：`apply_distillation` 已把整棵母版候选树写进暂存目录、`scan`/`compare` 也已真跑过；位置在 `import_master`（真写盘）**之前** |

所以两句话都要分清楚：

- **现状（无条件闸门）**下，缺 key 是"任何真写盘之前就整体中止"——**但那是靠函数第一行
  兜住的**，不是靠事务自己的原子性；
- 只把闸门摘掉（"只做按需那一半"）就会变成 400 落在**事务内部的中途**。本单要的是
  "动手之前"，所以闸门不能只是"按需"，还得**带判据地前置**：判据 = 这份请求里有没有
  归档动作。

判据单源：`report.parse_archive_section`（`DistillationReport.from_dict` 与下面这个
排雷判据共用同一段解析）+ `master.requests_archive`（确认请求 → bool，形状非法翻成
`MasterError`）。**没有新造闸门**：无归档那支用的就是 04 抽出的 `_library_config`。

> **一句如实的话**：当前页面上「提炼 → 确认」是连着的，而**提炼那一步本来就要 AI**
> （`/api/masters/distill` 起手就 `llm_run.llm()`）。所以"没配 key 也能确认不归档的报告"
> 在**现成的 UI 路径**上多半看不到差异——它的价值是 ① 判据一致（docstring 说的就是行为）、
> ② 端点契约（报告是客户端回传的无状态载荷，脚本 / 别的前端照样能打）、
> ③ 04 那批"库在哪"的闸门不再被确认端点留一个破口。

### 落地（2026-09-26）

- `report.parse_archive_section`：从 `from_dict` 的内联闭包抽出（语义逐字不变，缺键
  仍 = 空段）；`from_dict` 改调它。
- `master.requests_archive(payload) -> bool`：新排雷判据，放在 `confirm_distillation`
  之前；形状非法翻 `MasterError`（`ReportError` 是模型层内部异常、未登记错误表，
  不能从路由漏成 500）。
- `webapp.masters_confirm`：`if requests_archive(payload): config = _require_config(...)`
  + 推参考库根；`else: _library_config(context)`（只看"库在哪"，**不看 `api_key`**）、
  参考库根传 `None`（无归档时事务根本不取它）。**两处判据都是同一个
  `requests_archive`**，所以"闸门放行 / 事务却认出归档"这条漂移路径被关掉。
- `AI_GATED_FUNCTIONS` **未改表**：`masters_confirm` 体内仍真调 `_require_config(`
  （挪进有归档那条分支），结构判据两个方向都照旧成立——判据没漂，不需要改表。

### 读数（本机 2026-09-26；检出形态：`webapp.py` / `master.py` / `report.py` 与
`tests/test_webapp.py` 是 **CRLF**，`tests/test_library_gate.py` 是 **LF**）

- **全套 pytest**（`-n auto`，LF 检出）：**5564 passed + 11 skipped**（收集数
  **5575**）。同机基线（把本单的测试文件还原到 HEAD 再收集）：**5565 collected**
  → 本单净增 **10** 条用例（本文件 **13 → 23**，两个口径对齐），既有用例一条没改。
  > 这条读数是**评审纠过一次的**：第一版按早期的收集数写成"净增 8"（那会儿测试
  > 文件只有 8 条新用例，且我当时把 5565→5573 串了行）；Spec 轴评审逐条数了文件
  > （13→22 → +9）当场对不上，于是重新量了一遍基线并把两个口径（全套收集数 /
  > 本文件用例数）对齐后才写下这个数。
- **相关面**：`test_library_gate.py + test_reference_library.py` = **190 passed**；
  `test_library_gate.py + test_reference_library.py + test_master.py + test_report.py +
  test_autocommit.py` = **278 passed + 1 skipped**；`test_webapp.py -k master`
  = **28 passed**；`test_library_gate.py` 单文件 = **23 passed**。
- **反向用例（别把正常路堵了）**：有归档 + **有** key → 照旧走通
  = `test_reference_library.py::test_confirm_route_passes_archive_wiring` **1 passed**
  （既有用例，本单未改；归档条目真进了参考库）。
- **判据强度反证**（`.scratch/ci-gate-fixes/probe-06-gate-red-proof.py`，读数
  `probe-06-red-proof.txt`；注入 → 跑 4 条用例（5 个实例：无归档那条两个参数）
  → 逐字节复原）：
  - 注入 **A**（= 本单开工前的形状：无条件 `_require_config`）→ 「无归档 + 空 key → 200」
    **两条参数（键不在 / 空列表）全红**（答 400），另三条绿；
  - 注入 **B**（= 只做"按需"那一半：闸门摘掉）→ 「那声 400 是闸门给的」与「事务函数
    一次都没被进过」**两条都红**（报的是事务自己的「工程目录不存在」/ 替身记到了那次
    调用），另三条绿 —— **磁盘零变化那条分辨不出 B 与修好后**（事务中途的 400 也不
    留痕），所以"什么时候拒绝"由另外两条单独钉；
  - 复原后 sha256 与注入前**逐字节相同**、四条全绿。
- **结构闸门**：`test_ai_gate_registry_matches_source` 绿（`masters_confirm` 仍在表里、
  仍真调 `_require_config(`）；`test_library_accessors_never_consult_the_api_key` 绿。
- **换行纪律**：探针按 webapp.py 的 **CRLF** 做区域手术（按标记行切、不锚注释），
  注入前 / 后 sha256 自检相等（探针自己打印；读数文件本身由 Python `write_text`
  写出，故是 CRLF——与 `probe-05/07/08/10` 那几份读数同形）。
- **前端 / 浏览器门禁不涉及**：本单没动 `static/`、`tests/js/`、`tests/browser/`——
  `python tools/prepush.py --changed src/contest_generator/{webapp,master,report}.py
  tests/test_library_gate.py --dry-run` 只选到 **pytest 整套**（改动落在公共面且在
  ≥10 个文件的 import 闭包里）。

### 双轴评审处置（2026-09-26）

- **Standards 轴**（固定点 `efa819de`，未提交工作树）：**成文标准无硬违规**；
  四条判断题，处置如下。
  - 《Duplicated Code：`parse_archive_section` 与 `from_dict` 里 `decisions(key)`
    逐行同形，"抽取只做了一半"》——**不改，已在 docstring 里写明理由**：两段只差
    "键不在算不算合法"（keep/merge/exclude 必填段缺键 = 400；archive 缺键 = 无归档
    动作），参数化共享要添一个布尔开关把这个语义差藏进参数里。本仓在语义确有差异时
    取清晰重复（CONTEXT「条目库原语」同款取舍，评审自己也引了这条），而**必须单源的
    是 archive 这一段**（闸门 + 事务两个消费方），它已经是单源。
  - 《`tests/test_library_gate.py` 是第三份 `_confirm_payload`》——**不改**：与
    `test_webapp.py` / `test_reference_library.py` 的既有先例一致（评审也倾向不改）。
  - 《`requests_archive` 薄但含错误翻译，不算 Middle Man》《`reference_dir=None` 有
    注释且事务只在 `report.archive` 分支消费》——评审判定**不是问题**，未动。
  - 《`AI_GATED_FUNCTIONS` 仍列 `masters_confirm`，条件闸与该结构判据同形，用例不会
    红但分辨不出分支》——**如实记下**：结构判据确实只判"谁真调了 `_require_config`"，
    分辨"条件式还是无条件"是**行为判据**的活，本单新增的那几条（无归档 200 真入库 /
    有归档 400 零变化 / 那声 400 是闸门给的 / 事务函数没被进过）就是干这个的；
    表不动（改表要走工单里写清理由那条路，而这里判据没漂）。
  - 《probe-06 与读数仍未跟踪》——随本单收口一并入库。

- **Spec 轴**（同一固定点；逐条核了验收标准里那六件事）：**1–5 全部成立**——
  ① 无归档 + 空 key 真断言了入库内容（模板 main.c / 保留件 / 剔除件 / 列表端点）；
  ② 400 + 母版库与参考库逐字节零变化（并先证两库为空）；
  ③ "400 在事务之前"确有独立判据、没把临时暂存目录当写盘；④ 反向用例未被改动、
  单跑 1 passed；⑤ 无归档支复用的就是 04 的 `_library_config`、四个访问器结构用例绿；
  ⑥ `webapp.py` 只有 import + `masters_confirm` 三处 hunk，`mark_page_request` /
  `exit_via` / `page_defer_until` 命中 0。scope creep：无。两条 (c) 类发现：

  1. **《闸门挪到 `confirm_distillation` 首行，三条用例仍全绿——分不出「事务之前」
     与「事务第一行」》**——**真口，已补一条判据**：新用例
     `test_confirm_with_archive_without_key_never_enters_the_transaction` 在
     路由 → 域函数那一层放替身，断言 `confirm_distillation` **一次都没被进过**
     （与"事务第一步之前"那条合起来才是工单那句"动手之前"）；红证见注入态 B
     ——那条替身记到了调用，当场红。
     > 说清分寸：把闸门放在事务函数第一行**行为上**与放在调用之前等价（都不动盘、
     > 都先于一切工作），差的是归属层；但工单的原话是"事务开始之前"，所以按原话
     > 钉死，判据不吃亏。
  2. **《读数「净增 8 条」不实》**——**是我写错了，已重新量**（见上面读数那一格的
     更正说明）：两个口径现在对齐，**净增 10**（全套 5565 → 5575 collected，本文件
     13 → 23）。这条正好说明"读数要自己数一遍，别从别处的数字串过来"。
