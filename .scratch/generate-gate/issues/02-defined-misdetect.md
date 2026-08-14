# 02 — 门禁误判：`#if defined(...)` 预处理行被报为「未定义函数 defined」

**What to build:** 生成门禁把预处理行上的预处理器操作符 `defined` 误判为函数调用，连续 3 次 400 拒绝生成——检测侧（`find_undefined_calls`）与替换侧（`_replace_undefined_calls`）对「预处理行算不算代码」答案相反，检测侧裸奔。

**Status:** 待实施（实施提示词见文末）

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

- [ ] 红证：fixture 复刻 `#if defined(X)` → 修复前 `find_undefined_calls` 返回 `("defined",)`，修复后为空
- [ ] 既有测试全绿 + `mypy src` 干净
- [ ] 回归不变量：真实模块调用仍被检出；main.c 本地函数式宏（`#define FOO(x) … FOO(1)`）不被误报（B 陷阱守护，A 单独做也要跑）
- [ ] （可选）真机：/api/generate 用含 `#if defined` 的骨架 → 200 不 400

## 实施提示词（新会话粘贴）

> 工单：`.scratch/generate-gate/issues/02-defined-misdetect.md`（先读全文）。
> 任务：修 `find_undefined_calls` 对 `#if defined(...)` 预处理行的误判（A 必做；B 视判例定夺，注意 `_known_local` 依赖 `#define` 行的陷阱）。
> 文件边界：只动 `src/contest_generator/skeleton.py` + `tests/test_skeleton.py`；`generator.py` / `errors.py` 零改动。
> 验收：红证先写（defined fixture 修复前跑红）→ 修复后绿 + 既有全绿 + `mypy src` 干净；B 若做需守护「main.c 本地函数式宏不误报」回归。完成后把证据写入工单 Comments，Status 改 resolved。

## Comments
