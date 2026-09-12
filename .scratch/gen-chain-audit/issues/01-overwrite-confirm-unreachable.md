# 01 — 修：桌面「同名工程 → 覆盖确认」链路不可达（HTTP 前缀把判据打掉了）

**要做什么：** 桌面上已有同名工程时，点「生成工程」必须弹出**覆盖确认弹窗**
（说明旧工程会备份为 `<name>.bak`）；确认后自动重发 `overwrite:true`，取消则原样
显示 400 文案。修前实测：**弹窗永不出现**——`isConflictError` 吃到的 message 已被
统一加了 `请求失败（HTTP 400）：` 前缀，`indexOf(prefix) === 0` 恒 false。

**被谁阻塞：** 无。

**状态：** resolved

- [x] **真机复现（现成）**：审计脚本 W 节 —— 注入与 `webapp.GenerationConflictError`
      模板逐字同形的 400 文案（`detail = "桌面上已有同名工程「W-inject」：…"`，闸门
      命中已证：该次请求 `output_dir` 就是注入目录），前端**没有**出现
      `.ref-files-overlay [data-confirm-ok]`，#generate-msg =
      `请求失败（HTTP 400）：桌面上已有同名工程「W-inject」：…`。
- [x] **根因（源码确认，链路三处对齐）**：
      1. `app.js` 的 `handle()`：`throw new Error(parseHttpError(resp.status, data).text)`；
      2. `fx/errors.js` 的 `parseError`：**非 5xx 也统一加** `请求失败（HTTP N）：` 前缀
         （`if (status && !text.startsWith("请求失败（HTTP")) text = "请求失败（HTTP " + status + "）：" + text`）；
      3. `fx/generate.js` 的 `isConflictError`：`message.indexOf(CONFLICT_MSG_PREFIX) === 0`
         —— 而 `CONFLICT_MSG_PREFIX = "桌面上已有同名工程「"` 只在前缀被剥掉时才在开头。
      → `generate-core.js:663` 的 `if (isConflictError(e.message))` 恒假，整个
      「识别冲突 → confirm → 重发 overwrite:true」分支是**死代码**。
      引入时点：`5d636400`（工单 11 评审整改「handle 与流内 error 终态统一走
      parseError」）给 handle 加了统一前缀；覆盖保护（`fa91c90f`）当时的 handle 是
      `throw new Error(data.detail || …)`（**无前缀**），所以那时是对的。
      **为什么测试没拦住**：`tests/js/generate-overwrite.test.mjs` 直接把**没前缀**的
      原始文案喂给 `isConflictError`；原 headless 冒烟把 `apiPost` 整个 mock 掉，
      绕过了 `fx/errors` 这层。判据守的是「函数对某种输入的行为」，而**唯一真实输入
      是带前缀的那份**。
- [x] **修法（一处，判据从「打头」改「包含」）**：`isConflictError` 用
      `message.includes(CONFLICT_MSG_PREFIX)`。不放松守卫：前缀本身（含 `「`）够独特，
      不与其它 400 文案相撞；也不改 `parseError` 的统一前缀（那是**刻意**的展示口径，
      改它会连带影响全站错误文案）。
- [x] 测试守卫：
      * `tests/js/generate-overwrite.test.mjs` 新增三条——真机 message 形态（用**真的**
        `parseHttpError` 造，并前置断言它确实**不**以冲突前缀开头）→ `isConflictError`
        必须为 true；前缀在中段仍能 `conflictDirName` 提取目录名；**结构守卫**钉死
        实现只能 `includes`，不得回退成 `indexOf(...)`；
      * `tests/browser/gen-chain-audit.mjs` W2b：注入真冲突 400 → 必须弹确认弹窗 →
        取消支路（不重发 + 原 400 文案留在界面）→ 确认支路（重发带 `overwrite:true`
        且真写盘）。
- [x] **反向验证（本单关键）**：把判据临时改回 `indexOf(CONFLICT_MSG_PREFIX) === 0`
      → `tests/js/generate-overwrite.test.mjs` **当场变红**
      （`isConflictError 必须识别带 HTTP 前缀的真机 message…`：fail 1 / pass 8）；
      改回后 9/9 绿，grep 确认无 `TEMP 反向验证` 残留。
- [x] 归零回归（修后实测）：全量 pytest 绿、`node --test "tests/js/*.test.mjs"`
      **1499 pass / 0 fail**。

**没做（如实记录）：**
- 不加 `role="dialog"` / `aria-modal`（全仓遮罩都还没有，上一轮已记为全仓欠账）。
- 不动 `parseError` 的统一前缀（它是展示口径，且被全站错误路径依赖）。
- **桌面模式的真机端到端**（真在桌面造同名工程）没跑：本仓禁止往用户桌面写东西，
  故用「注入逐字同形的冲突文案 + 第二次请求放行到真后端（写临时目录）」替代——
  前端「识别冲突 → 弹确认 → 重发」三步全真，只有 400 的来源是注入的。
  后端那半边（`GenerationConflictError` → 400 文案、`overwrite is True` →
  `backup_project_dir` → `.bak`）由 `tests/test_webapp.py` / `test_generation_output.py`
  的既有用例守着。
