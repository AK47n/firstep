# 10 — 模块独立性结构门禁：跨模块 include = 声明依赖 + 依赖无环

**What to build:** 把「模块尽量独立、不互相牵连」从人工审计变成结构测试：扫描 `library/modules/*/` 全部 .c/.h（注释剥离后提取引号 include）——① 引用了其他模块的头，该模块 manifest.dependencies 必须声明对方；② manifest 依赖图无环、依赖目标都存在；③ 已声明的依赖必须有实际 include（禁止死依赖拖拽）。

**Blocked by:** 09

**Status:** resolved（2026-08-15）

- [x] 新测试 `tests/test_module_independence.py`：真实库全绿（当前审计 0 未声明依赖 / 0 环 / 0 死依赖）

## Comments

- 这是收尾门禁工单：测试先行建立后直接绿（当前库已满足——之前人工审计结果被机械钉死），没有可构造的红证阶段。
- 覆盖三条：跨模块 include 必须声明依赖；声明的依赖必须有实际 include（死依赖拦截）；依赖目标存在 + 无环。头文件归属按全库实际 .h 基名唯一映射（先断言无歧义）。
- 未改任何模块代码 / manifest / 生成器行为；pytest 1608 绿 + mypy src 干净。
- [x] 测试用 clex.strip_comments + extract_quoted_includes（注释里的 include 不算）
- [x] pytest 全绿 + mypy src 干净
- [x] 不碰任何模块代码与生成器行为
