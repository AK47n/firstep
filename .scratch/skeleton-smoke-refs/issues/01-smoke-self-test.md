# 01 — 自检冒烟 main.c（OLED 为主 / 串口为辅）

**What to build:** 步骤 8 新增「生成自检骨架」按钮 → `/api/skeleton` 带 `main_mode: "smoke"` → 后端走新纯函数 `skeleton.generate_smoke_main` 生成"初始化每个模块 → 读一次/动一次 → OLED/串口打印结果"的自检 main.c，`sanitize_skeleton` 同款静态自检兜底；OLED 与 debug_uart 都没选 → 400 中文。

**Blocked by:** 无（spec `.scratch/skeleton-smoke-refs/spec.md` 已定稿）

**Status:** resolved（2026-08-15）

## 需求

1. **`skeleton.generate_smoke_main(llm, problem_text, manifests, platform, library_dir, master_project_dir=None)`**：与 `generate_skeleton` 同构——`build_skeleton_interfaces` 出接口块 → LLM 出稿 → `sanitize_skeleton` 兜底 → 返回 `(main_c, intercepted)`。冒烟 prompt 要求：只自检不写题逻辑；每个选中模块一段"初始化 → 读一次/动一次 → 打印结果"；输出通道按所选模块——选中 `oled` 时 OLED 为主输出（初始化 OLED、逐段打印模块名 + 结果），选中 `debug_uart` 时串口回显（printf 同一行）；两个都没选由 webapp 层 400（纯函数不校验，保持内存直测）。模块无当前平台版本 → 留注释"该模块无 <platform> 版本，未自检"。
2. **`llm` 协议与实现扩展**：协议加 `generate_smoke_main(problem_text, module_interfaces) -> str`；`DeepSeekLLM` 实现走新 prompt（`_smoke_user_prompt` 或同款）；`FakeLLM`（tests/fakes.py）同步。
3. **`webapp /api/skeleton` 扩展**：请求体加可选 `main_mode`（`"skeleton"` 缺省 / `"smoke"`；非法值 400 中文）。`smoke` 分支：若 `oled` 与 `debug_uart` 都不在所选 slugs → 400 中文（"自检骨架需要 OLED 或 debug_uart 模块"）；否则调 `generate_smoke_main`。`skeleton` 分支现行为逐字节不变。
4. **前端步骤 8**：`btn-skeleton` 旁加 `btn-smoke`「生成自检骨架」；共用 `main-c` 文本框与 `intercepted`/`skeleton-msg`；点击发送 `main_mode: "smoke"`；按钮禁用逻辑与现「生成骨架」一致（题面/平台/模块齐备）。
5. **测试（红证先行）**：
   - `tests/test_skeleton.py`：FakeLLM 冒烟出稿 → `generate_smoke_main` 返回可编译 main.c + 不存在调用被拦截（sanitize 兜底）；prompt 含全部模块 slug 与 OLED/串口通道指令；无平台版本模块留注释。
   - `tests/test_llm.py`：协议/实现/FakeLLM 三端冒烟方法同步（结构钉）。
   - `tests/test_webapp.py`：`/api/skeleton` `main_mode="smoke"` 透传 + 两个通道模块都没选 400 + 非法 main_mode 400 + 缺省仍走 skeleton（现行为回归）。
   - 前端改动无独立 JS 测试，靠浏览器人工验收。
6. **真机（工单验收）**：2026C 或 2021F 选中 oled + motor + pid → `generate_check` 冒烟路径 UV4/CCS 0 错 0 警；生成 main.c 含 oled_init/oled_show 调用与逐段自检注释；未选 oled/debug_uart 的 HTTP 400 零产物。

## 文件边界

- `src/contest_generator/skeleton.py`（新 `generate_smoke_main`）
- `src/contest_generator/llm.py`（协议 + DeepSeekLLM + prompt）
- `src/contest_generator/webapp.py`（`/api/skeleton` 分支）
- `src/contest_generator/static/index.html`（步骤 8 按钮）
- `tests/test_skeleton.py`、`tests/test_llm.py`、`tests/test_webapp.py`、`tests/fakes.py`（若在 tests 目录）

## 验收

- [x] pytest 全绿 + mypy src 干净
- [x] 红证已验（FakeLLM 出稿含未定义调用被拦截 / 缺通道模块 400 / 非法 main_mode 400）+ 绿证（prompt 含全部模块与通道指令 / 无平台版本注释）
- [ ] 真机：冒烟路径 UV4/CCS 0 错 0 警 + HTTP 400 零产物（用户浏览器/真机自验）
- [x] 提交（post-commit 钩子自动补 CHANGELOG）

## Comments

- **实施留痕（2026-08-15）**：prompt 平台措辞不用 `<平台>` 字面量——改为「接口块里标注『无平台 XX 版本』的模块，留注释『该模块无 XX 版本，未自检』（XX 照接口块里的平台名写）」，LLM 从接口块占位块拿到具体平台名，避免生成物出现字面 `<平台>`。
- **code-review 双轴**：Standards 指出 CONTEXT.md 未更新词条（已补「自检冒烟」行）、三处重复代码（skeleton 出稿管线 / llm 接口块引导语 / webapp 分支实参）与前端双按钮重复（已全部去重为共享 helper：`_generate_main_c`、`SKELETON_INTERFACES_HEADING`、webapp 单 `generate` 分发、index.html `generateMain(mode)` + `SKELETON_MODES`）。Spec 指出 `main_mode` 空串被缺省化（已改为显式出现即必须合法值）与 test_skeleton 缺 prompt 断言（prompt 断言落在 test_llm——prompt 唯一出处是 llm.py，比 test_skeleton 更贴接缝，记此偏差）。
- 真机验收项留待用户在浏览器里点「生成自检骨架」跑一次真实 LLM + UV4/CCS 自验（本会话无 GUI/工具链）。
