# 04 — 架构深化 v3：错误映射归位（C6）

**What to build:** 第三轮架构深化（2026-08-08 报告，候选 C6，Worth exploring；实证摩擦已复现）。"新异常必须登记否则 500"的纪律没有结构保证——`UnknownPlatformError`（patchers.py:18）未登记，`POST /api/generate {"platform": "foo"}` 得 500 "服务器内部错误"而非可修复的 400（用户可控输入打在"真 bug"路径上）。本工单：表住进独立模块 + 结构测试让漏登从此是测试红，不是线上 500。

1. **新模块 `src/contest_generator/errors.py`**：error_to_http 表从 webapp.py:206-242 平移（11 条映射 + "未登记 = 真 bug → 500 大声失败"政策注释 + `error_entry(exc) -> (status, message)` 唯一实现）；webapp 的 `_error_message` / `_error_response` / SSE 侧取值（246-266）改为从 errors.py 调用——单表政策不变（CONTEXT.md 架构要点），只是表的居住地从 web 壳移到独立模块，webapp 只剩取值与包装。
2. **修实证 bug**：`UnknownPlatformError` → 400 中文（"未知平台，支持：stm32 / mspm0" 风格，照 error_to_http 表既有措辞风格），HTTP 测试：`{"platform":"foo"}` 得 400 中文而非 500。
3. **结构防漏登**：新测试（test_errors.py 或 test_webapp.py）反射枚举 `contest_generator` 包下全部异常类（排除内置/基类与明确允许 500 的白名单）断言已登记——登记遗漏从此测试红。反射按模块树扫（inspect.getmembers + __subclasses__ 收敛），白名单只放"刻意按 500 暴露"的类并注释理由。
4. **行为契约不变**：未登记异常仍 500（政策不动）、HTTP 状态码与中文 message 逐字不变（既有错误映射测试原样过）；SSE 侧 error 事件自动随同一表生效。

**明确不动的（边界，勿越）**：各模块异常类定义本身（分类语义不动，不引入类级 http_status 属性——单表 + 结构测试即可达同样保证，改动面小一半）、`_map_errors` 路由包装、HTTPException 穿透、webapp 其余部分、llm.py / master.py 等核心模块（只读）。

**Status:** resolved（2026-08-08 合入 main a004610，727 绿 + mypy 干净）

## 验收

- [x] 全量 pytest 绿（727）+ mypy 干净；既有错误映射测试原样过（状态码/文案逐字不变）
- [x] `POST /api/generate {"platform": "foo"}` 400 中文（新增测试）；`grep UnknownPlatformError src` 出现在 errors.py 表内（patchers.py 定义处不动）
- [x] 结构测试：临时新增一个未登记异常类（测试内定义）→ 测试红；删除 → 绿（防漏登生效）
- [x] error_to_http 表唯一出处 = errors.py（webapp 无映射表定义）；CONTEXT.md"错误映射"词表行补"表住 errors.py + 结构测试防漏登"

## Comments

（2026-08-08 立项，架构评审 C6。备选方案：异常类定义处带 http_status 类属性（分类与定义同源）——本工单取单表 + 结构测试，改动面小、保证相同；若评审后觉得类属性更优可提新工单。与 C1 重叠：webapp.py（C1 只改导入行，C6 只改错误区）——并行合入冲突极小。）
