# 02 — 门禁误判：`#if defined(...)` 预处理行被报为「未定义函数 defined」

**What to build:** 生成门禁把预处理行上的预处理器操作符 `defined` 误判为函数调用，连续 3 次 400 拒绝生成——检测侧（`find_undefined_calls`）与替换侧（`_replace_undefined_calls`）对「预处理行算不算代码」答案相反，检测侧裸奔。

**Status:** resolved

## 现象（2026-08-14 真机，2026C 20 条全量映射验证途中）

- generate 门禁连续 **3 次 400**，点名「函数」是 `defined`——3 个骨架恰好都写了 `#if defined(...)` 形态（模型波动，可能与新增模块头文件风格有关）。`_check_main_calls` 是生成公共门禁，**web 端 /api/generate 同路径同样中招**。
- 骨架阶段（`sanitize_skeleton`）同一形态却报 0 拦截：`_replace_undefined_calls` 走 clex 区域扫描，预处理行原样透传不替换，`blocked` 列表为空——同一份检测、两种出口（骨架改占位 / 门禁抛错），只有抛错出口可见。
- 收尾方式：第 4 个真实骨架（9180 字符，无 defined）用镜像 generate_check 载荷的脚本直跑 /api/generate → 200 → 产物门禁全过 → UV4 0 错。旁路脚本与证据留档 `.scratch/real-run/`：`_capture_skel.py` / `_finish_2026C.py` / `_uv4_only.py` + `evidence_2026C_skel_main.c`；日志 `check_2026C_20条_补跑3.log`（generate/门禁段）、`uv4_2026C_20条.log`。`src/tests/generate_check.py` 零改动。

## 根因链（已读码核实）

1. `skeleton.py:49` `_IDENT_CALL_RE = \b([A-Za-z_]\w*)\s*\(` 全文本匹配——`#if defined(SOME_MACRO)` 的 `defined(` 命中。
2. `skeleton.py:35-40` `_CONTROL_KEYWORDS` 无 `defined`。
3. `skeleton.py:218` `find_undefined_calls` 用 `strip_comments(main_c)`（默认 `keep_preprocessor=False`，`clex.py:157-176`）——`#` 行按普通文本处理，`defined(` 存活进 calls。
4. `generator.py:747-753` `_check_main_calls` → `verify_main_c_interfaces` → `UndefinedCallsError` → 400。
5. 与 `_replace_undefined_calls`（`skeleton.py:243-257`，`iter_c_regions(code, preprocessor_indented=True)` 非 code 区域透传）的 clex 语义不一致。

## 修复建议（A 必做；B 视评审定夺）

- **A（1 行 + 测试）**：`defined` 入 `_CONTROL_KEYWORDS`。C 预处理器操作符，永不可能是模块导出的函数名，误伤风险≈0。只修观察到的形态。
- **B（语义对齐，修同类）**：`find_undefined_calls` 按 clex 语义把预处理行剔出调用提取——`#if fn(...)` 条件调用是同族误判。**陷阱**：`_known_local`（`skeleton.py:394-401`）依赖 `_DEFINE_RE` / `_MACRO_DEF_RE` 在 `#define` 行上识别 main.c 本地宏——把 `#` 行整段剥掉会让 `#define FOO(x) … FOO(1)` 函数式宏误报为未定义。修法需保留 `#define` 行（只剔 `#if/#ifdef/#ifndef/#elif/#else/#endif` 等非 define 指令），或宏识别改吃未剥离文本。

## 实施边界

- src：只动 `src/contest_generator/skeleton.py`（A：`_CONTROL_KEYWORDS`；B：`find_undefined_calls` / `_extract_calls` 或 strip 处理）。`generator.py` / `errors.py` 零改动。
- tests：`tests/test_skeleton.py`（新用例 + 既有不变量）。红证先写：`#if defined(X)` fixture 修复前跑红（返回 `("defined",)`）。

## 验收标准

- [x] 红证：fixture 复刻 `#if defined(X)` → 修复前 `find_undefined_calls` 返回 `("defined",)`，修复后为空
- [x] 既有测试全绿 + `mypy src` 干净
- [x] 回归不变量：真实模块调用仍被检出；main.c 本地函数式宏（`#define FOO(x) … FOO(1)`）不被误报（B 陷阱守护，A 单独做也要跑）
- [x] （可选）真机：/api/generate 用含 `#if defined` 的骨架 → 200 不 400（HTTP 层复刻闭环，见 Comments；真实服务进程 + DeepSeek 全流程留用户复核）

## 实施提示词（新会话粘贴）

> 工单：`.scratch/generate-gate/issues/02-defined-misdetect.md`（先读全文）。
> 任务：修 `find_undefined_calls` 对 `#if defined(...)` 预处理行的误判（A 必做；B 视判例定夺，注意 `_known_local` 依赖 `#define` 行的陷阱）。
> 文件边界：只动 `src/contest_generator/skeleton.py` + `tests/test_skeleton.py`；`generator.py` / `errors.py` 零改动。
> 验收：红证先写（defined fixture 修复前跑红）→ 修复后绿 + 既有全绿 + `mypy src` 干净；B 若做需守护「main.c 本地函数式宏不误报」回归。完成后把证据写入工单 Comments，Status 改 resolved。

## Comments

**2026-08-14 实施闭环（红证 → 修复 → 绿 + HTTP 层 400→200 复刻）**

### 红证（修复前实跑）

- 单测层（tests/test_skeleton.py 新 5 条先写后跑）：
  - `#if defined(USE_EXTRA)` fixture → `find_undefined_calls` 返回 `("defined",)`（验收红证逐字命中）；
  - 同族 `#if has_extra(1) && mode_ok()` + `#pragma pack(push, 1)` → `("has_extra", "mode_ok", "pack")`；
  - 跨行续行 `#if defined(USE_A) && \` + `    defined(USE_B) && \` + `    has_extra(1)` → `("defined", "has_extra")`。
- HTTP 层（一次性脚本 tests/_tmp_defined_gate_check.py，跑完已删，未入库）：POST /api/generate 直灌含 `#if defined(USE_EXTRA)` 的 main_c（真机旁路 _finish_2026C.py 同形态，main_c 走载荷不经过 LLM）——修复前 400，detail 与真机逐字一致：「main.c 调用了所选模块头文件中不存在的函数：defined —— 请改用真实接口，或让骨架阶段自检改写为注释占位」（对应 .scratch/real-run/check_2026C_20条_补跑.log / 补跑2.log 第 57 行，两处已复核）；修复后 200。

### 修复（src/contest_generator/skeleton.py；generator.py / errors.py 零改动）

- **A**：`defined` 入 `_CONTROL_KEYWORDS`（1 行 + 注释）——C 预处理器操作符，兜底任何漏进提取文本的形态。
- **B**：`_strip_preprocessor_directives`——`find_undefined_calls` 在 `strip_comments` 后、调用提取前剔除非 define 预处理指令行，与 `_replace_undefined_calls`（iter_c_regions 对预处理行整行透传）对齐 clex 语义。整行剔除含跨行条件的 `\` 续行（含末条，续行行首无 # 单独剥不掉）；`#define` 判定用新 `_DEFINE_LINE_RE`（`#\s*define\b`，`\b` 挡 `#defineFOO` 这种非指令残行）。
- **B 选型（保留 #define 行，而非宏识别改吃未剥离文本）**：全剥 # 行的坏修法已实跑复现陷阱——`#define FOO(x) ((x) * 2)` + `FOO(1)` 误报 `['FOO']`。保留 #define 行同时保住两件事：`_known_local` 的本地宏识别（陷阱守护），以及宏体内调用的审计（`#define TOGGLE() fake_gpio_set(1)` 一旦展开即链接期必炸，仍被检出）——检测侧不因对齐 clex 而弱化门禁。

### 测试 +5（1356 全绿 + mypy src 37 文件干净）

- `test_find_undefined_calls_ignores_defined_in_preprocessor_condition`（A 判例）
- `test_find_undefined_calls_ignores_calls_in_preprocessor_directives`（B 同族：#if fn() / #pragma pack）
- `test_find_undefined_calls_strips_multiline_preprocessor_conditions`（\ 续行）
- `test_find_undefined_calls_accepts_param_macros_defined_in_main_c`（B 陷阱守护：FOO(x) + FOO(1) 不误报）
- `test_find_undefined_calls_audits_calls_inside_define_bodies`（保留 #define 行的刻意后果：宏体未定义调用仍检）

### 回归不变量

真实模块调用仍被检出（既有 test_skeleton 全用例 + test_generator 门禁用例全过）；main.c 本地函数式宏不误报（既有 LED_ON 用例 + 新 FOO(x) 用例）。

### 未做

真实服务进程 + DeepSeek 全流程 UV4 复编未重跑（可选真机项已以 HTTP 层复刻闭环）；用户验收时可取含 `#if defined` 骨架直发 /api/generate 复核。
