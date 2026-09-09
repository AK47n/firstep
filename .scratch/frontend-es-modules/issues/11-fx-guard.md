# 11 — 收尾：防回退护栏 + 词表 + 全量双绿

**要做什么：** 阶段 1 的收尾切块：一张结构护栏测试令「已搬函数双源回退」不可能发生；CONTEXT.md 词表记录模块化约定；全量回归（JS 416 + pytest）与真浏览器冒烟确认。

**被谁阻塞：** 02-10 全部

**状态：** resolved（JS 434 全绿（416 + 护栏 18）+ pytest 2465 全绿 + 冒烟 11/11 + diag 零 EXC）

## 实施记录

- tests/js/fx-guard.test.mjs：DOMAINS 表枚举 01-10 全部 167 个已搬名称（18 个 fx 模块：函数 163 + 常量 4——ENV_BADGE_GLYPH / CONFLICT_MSG_PREFIX / SETTINGS_COLLAPSE_KEY / SETTINGS_DEFAULT_COLLAPSED，常量按期望 typeof 校验）；每模块一个 test：①从 fx 模块 import 断言存在且类型符（fn = function，含 async parseSSE）；②断言 index.html 不含 `function <name>(` / `const <name> =` 定义（双源回退即红）。后续迁移批次把新名称登记进 DOMAINS 表。
- CONTEXT.md「架构要点」新增前端模块化 bullet（纯函数单源 static/js/fx/*.js、0 构建、window 同名桥 = 兼容层、DOM 胶水属阶段 2 迁移对象、fx-guard 兜底回退）。
- 全量回归：node --test 434 全绿；pytest 2465 全绿；冒烟 11/11；diag 零 EXC（favicon 404 为既有噪音）。
- 阶段 1 完成态：18 个 fx 模块 + 167 个已搬名称；index.html 内联脚本 8900 行 → 9171 行（含标点/注释）；被测试纯函数零字符串提取（44 个 .test.mjs 全部直接 import）。

- [x] 新建 tests/js/fx-guard.test.mjs：DOMAINS 枚举全部已搬函数名（esc / formatSize + 各域 + 4 常量）；断言 index.html 不含 `function <name>(` / `const <name> =`（防双源回退）；由已迁 fx 模块 import 断言存在与类型
- [x] CONTEXT.md「架构要点」新增前端模块化 bullet（纯函数单源 static/js/fx/*.js、0 构建、window 同名惰性桥、DOM 胶水仍在 index.html 属阶段 2 迁移对象）
- [x] `node --test "tests/js/*.test.mjs"` 434 全绿（416 + 18 护栏）；pytest 2465 全绿
- [x] 浏览器冒烟：smoke.mjs 11/11（8 个 tab 全部正常 + 主体执行 + window 桥 + 高亮）+ diag 零 EXC
- [x] 提交（中文信息）与 CHANGELOG 记录

- [ ] 新建 tests/js/fx-guard.test.mjs：枚举全部已搬函数名（esc / formatSize + 各域），断言 index.html 不含 `function <name>(` 定义（防双源回退；由已迁 fx 模块 import 断言其存在）
- [ ] CONTEXT.md「架构要点」新增前端模块化 bullet：纯函数单源在 static/js/fx/*.js（0 构建、window 同名惰性桥、DOM 胶水仍在 index.html 属阶段 2 迁移对象）
- [ ] `node --test "tests/js/*.test.mjs"` 416 全绿；pytest 全绿
- [ ] 浏览器冒烟：全部 8 个 tab 正常（生成流程走一次到骨架生成前）
- [ ] 提交（中文信息）与 CHANGELOG 记录

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
