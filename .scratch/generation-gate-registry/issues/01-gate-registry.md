# 01 — 生成门禁装配表驱动化（六道手写调用收进一张表）

**What to build:** `generate()` 里的六道门禁是手写线性调用（generator.py:541-546，顺序靠注释约定），加一道门要手抄四件套（异常类 → `_check_*` 谓词 → 调用行 → 测试），全貌只在调用行一处可见，文档已漂移（两处注释引用不存在的 `_check_platform`）。目标：照 `categories.RULE_CATEGORIES` 先例，门禁装配收进 `GENERATION_GATES` 表 + `run_generation_gates` 一个 runner——顺序、输入依赖、门禁全貌一处可见，新增门禁 = 表加一条 + 谓词。

**Status:** implemented（2026-08-11 已实施，验收全勾）

## 现状（已核实，2026-08-11 架构评审）

- 六道门禁（generator.py）：`_check_module_files`(575) / `_check_file_path_conflicts`(750) / `_check_main_calls`(587) / `_check_module_self_include`(679) / `_check_unresolved_includes`(631) / `_check_macro_conflicts`(711)，在 `generate()` 541-546 手写顺序调用，全部在 `output_dir.mkdir`（548）之前——"所有校验失败都在落盘前发生"不变量（模块 docstring 第 10 行）。
- 谓词签名两形状：5 道吃 `corpus`（纯谓词，内存直构可测），1 道（file_path_conflicts）吃 `(manifests, platform)`（manifest 声明，不读盘——ModuleCorpus docstring 435-436 有记载）。
- 顺序有语义：`_check_file_path_conflicts` 跳过无平台版本条目（注释 770："由 _check_module_files 报"），必须先跑 module_files。
- `_check_main_calls` 一门两异常：`FencedMainCError` + `UndefinedCallsError`。
- 错误登记：六个异常全部已登记 errors.py（GeneratorError → 400；DuplicateFilePathError 显式行）；test_errors.py 反射全部异常类防漏登。
- 文档漂移：generator.py:250 与 selection.py:244-245 注释引用 `_check_platform`——函数不存在，真实平台门 = `patcher_registry.get(platform)`（generator.py:530，未知平台在此失败）。
- 先例：categories.py `RuleCategory` frozen dataclass 表（206-275）+ 单一 dispatcher `classify`（278-295）——表加一条即新增类别。

## 实施

1. **generator.py 加表 + runner**（唯一 src 改动文件）：
   - `GenerationGate` frozen dataclass：`key: str` + `check: Callable[[ModuleCorpus, Sequence[ModuleManifest], str], None]`。
   - `GENERATION_GATES` 表：六条，顺序 = 现状调用顺序（module_files → file_path_conflicts → main_calls → module_self_include → unresolved_includes → macro_conflicts）；每条 `check` 是小型闭包选择该门的自然输入（5 道取 corpus、1 道取 manifests+platform）——**谓词函数签名与实现零改动**，表内闭包只做输入选择；表上方注释说明顺序语义（file_path_conflicts 依赖 module_files 先报缺平台条目）。
   - `run_generation_gates(corpus, manifests, platform)`：`for gate in GENERATION_GATES: gate.check(corpus, manifests, platform)`——首个失败即抛，装配唯一出处。
   - 541-546 调用行替换为 `run_generation_gates(corpus, manifests, platform)`。
2. **文档漂移修复**（同批）：
   - 模块 docstring（5-8 行）：门禁清单改为引用 `GENERATION_GATES` 表（现状漏列 missing-files / self-include / macro-conflicts 三道）。
   - generator.py:250 注释：`_check_platform 是兜底不动` → `未知平台在 generate 入口经 patcher_registry.get 失败`。
   - selection.py:244-245 注释：同款改正。
   - ModuleCorpus docstring（435-436）："见 _check_file_path_conflicts" → 引用表（输入依赖在表内声明）。
3. **测试**（tests/test_generator.py 新增一组，放既有门禁测试旁）：
   - `test_generation_gate_table_complete_and_ordered`：`[g.key for g in GENERATION_GATES] == ["module_files", "file_path_conflicts", "main_calls", "module_self_include", "unresolved_includes", "macro_conflicts"]`——钉死顺序与完整性，新增/删除/换序即红。
   - `test_run_generation_gates_invokes_all_in_order`：monkeypatch `generator.GENERATION_GATES` 为两个记录型假门（记录调用序 + 透传参数），断言 runner 按表序全调、同一 (corpus, manifests, platform) 透传、中途抛异常即传播（首个失败即停）。
   - 红证：实施时临时从表移除一道门禁 → 完整性测试即红，恢复复绿。
   - 既有门禁测试（直接调 `_check_*` 的 ~8 处）不动、保持绿。
4. **CONTEXT.md**：校验语料词条补一句——"门禁装配唯一出处 = generator.GENERATION_GATES 表 + run_generation_gates（照 categories.RULE_CATEGORIES 先例）：顺序 / 输入依赖 / 全貌收进表，新增门禁 = 表加一条 + 谓词"。

## 文件边界

- src/contest_generator/generator.py —— 唯一 src 改动（加表 + runner + 3 处注释/docstring）
- src/contest_generator/selection.py —— 仅 1 行注释改正（244-245）
- tests/test_generator.py —— 新增结构测试组
- CONTEXT.md —— 词条一句
- **不动**：errors.py（已有登记）、keil.py / ccs.py / patchers.py、谓词函数签名与实现、tests/test_generate_collision_gate.py 等既有测试、generate_check.py（与门禁同源 = 另一工单）

## 验收

- pytest 全绿（1066 基线 + 新增结构用例，无回归）+ `mypy src` 干净。
- 结构测试钉死：表 6 键有序完整、runner 按序全调并透传参数、首个失败即抛。
- 红证已验：临时移除表内一道门禁 → 结构测试红，恢复复绿（记录在实施记录）。
- 文档漂移清零：`grep -rn "_check_platform" src/` 零命中。
- CONTEXT.md 词条已更新。
- 生成侧 e2e 测试照常全绿（纯装配重构，行为零变化；如需真机，generate_check 一跑即可）。

## 实施记录（2026-08-11）

- generator.py：`GenerationGate` frozen dataclass（key + check，check 签名
  `Callable[[ModuleCorpus, Sequence[ModuleManifest], str], None]`）+ `GENERATION_GATES`
  表（六条，顺序 = 现状调用顺序 module_files → file_path_conflicts → main_calls →
  module_self_include → unresolved_includes → macro_conflicts；每条 check 是选择
  各自输入的小闭包——谓词签名与实现零改动）+ `run_generation_gates` runner（首个
  失败即抛）。表置于六个 `_check_*` 之后、`_copy_module_files` 之前（运行时名字
  解析，generate 调用不受定义位置影响）。541-546 六行手写调用 → 一跑。
- 同批修 3 处文档漂移：模块 docstring 门禁清单改引用 GENERATION_GATES 表（顺带
  补全漏列的 missing-files / self-include / macro-conflicts 三道）；generator.py:250
  注释 `_check_platform 是兜底不动` → `未知平台在 generate 入口经
  patcher_registry.get 失败`；ModuleCorpus docstring "见 _check_file_path_conflicts"
  → "输入依赖在 GENERATION_GATES 表内声明"。
- selection.py：244-245 注释同款改正（`_check_platform` 不存在 → patcher_registry.get）。
- tests/test_generator.py：新增两组结构测试（放既有门禁测试旁）——
  `test_generation_gate_table_complete_and_ordered`（6 键有序完整钉死）+
  `test_run_generation_gates_invokes_all_in_order_and_stops_on_failure`
  （monkeypatch 假门三枚：记录门 ×2 + 中段抛异常门，断言按表序全调、同一
  (corpus, manifests, platform) 原样透传、首个失败即停）。既有 ~8 处直调
  `_check_*` 的测试未动。
- CONTEXT.md 校验语料词条补"门禁装配唯一出处 = generator.GENERATION_GATES 表 +
  run_generation_gates"一句，并顺带修正词条内"五道门禁"过期计数 → 六道（同条
  同源漂移，一行内修）。

## 验收

- [x] pytest 全绿 1068（1066 基线 + 2 新增结构用例，无回归）+ `mypy src` 干净
  （Success: no issues found in 32 source files）。
- [x] 结构测试钉死：表 6 键有序完整、runner 按序全调并透传参数、首个失败即抛。
- [x] 红证已验：临时从表移除 macro_conflicts 条目 →
  `test_generation_gate_table_complete_and_ordered` 即红（AssertionError，6 键变
  5 键），恢复复绿，全绿照旧。
- [x] 文档漂移清零：`grep -rn "_check_platform" src/` 零命中。
- [x] CONTEXT.md 词条已更新。
- [x] 生成侧 e2e 测试照常全绿（纯装配重构，行为零变化；如需真机，generate_check
  一跑即可）。
