# 02 — LLM 工作流观测收成一处（三件套 20 处 + 视觉半套 5 处）

**要做什么：** 把散在 25 个路由里的「预算 + 观测收集器 + 客户端派发 + 结算」收成一个缝：
`LLMRun(context, workflow)` 造出观测单元，`.llm()` 现派发客户端（语义逐字照旧），收尾
`settle()` 结算进观察面板。新增路由时漏掉其中一件从此不可能——四件事只写一次。

**被谁阻塞：** 无——可立即开始（与 01 无重叠：本单只动 LLM 观测面，不动检测页装配）

**状态：** resolved

## 判据（单源不变量）

webapp.py 源码里这四件事**各恰好一处**，且都落在缝内（按**每一个调用点**数，不按所在函数
去重——"各恰好一处"是字面意思）：

| 事 | 位置 | 迁移前（HEAD）的散落处数 |
|---|---|---|
| `RetryBudget(...)` 构造 | `LLMRun.__init__` | 20 处 |
| `create_llm_observation_collector(...)` | `LLMRun.__init__` | 23 处（25 个调用点，按函数去重后 23） |
| `_llm(context, …, collector)` 派发 | `LLMRun.llm()` | 21 处（20 处三件套 + recommend/skeleton 第二次派发） |
| `recent_llm_workflows.add_completed(...)` | `LLMRun.settle()` | 23 处（25 个调用点，同上） |

*（"迁移前"一列以**实施时实测**为准：`.scratch/webapp-consolidation/verify-02-triple-red-proof.txt`；
原文写的 25/20/22/26 混了"调用点数"与"按函数去重数"两种口径，实施时按守卫量的口径更正。）*

判据写成**吃源码文本的纯函数**（返回调用点清单），既作用在真源码上，也能在合成片段上复现红
（红证不靠手改仓库文件，避免与套件并行时的中间态）。

## 计划

1. `webapp.py` 新增缝（紧邻既有 `_llm`）：`class LLMRun(context, workflow)`。`budget` /
   `collector`（构造即建）；`llm()` **每次现派发**（不缓存——既有契约要求同一趟的多次派发
   共享同一个预算与收集器对象，被两条既有用例钉着）；`settle()` 幂等；`recent_llm_workflows`
   的直接使用只剩 `settle()` 一处。
   *（实施更正：原计划是 `_llm_run(...)` 工厂 + `__enter__`/`__exit__` 让 `with` 退出结算；
   实现时按评审判据收敛为「直接构造 + 显式 `settle()`」——25 处调用点每一处本来就有明确的
   结算位置（22 处在 `finally`、3 处紧随其后），再养一套 `with` 惯用法是同一件事的第二种写法；
   纯转发的 `_llm_run` 工厂也被评审判为 Middle Man 删掉。语义与判据不受影响。）*
2. 20 处三件套改用缝（全文件一种写法）：
   ```python
   llm_run = LLMRun(context, "tasks-plan")
   llm = llm_run.llm()
   ...
   def run(emit):
       try:
           with bind_llm_telemetry(llm_run.collector, emit.progress):
               result = run_task_planning(llm=llm, ..., emit=emit)
           emit.done(result)
       finally:
           llm_run.settle()
   ```
3. 5 处只做视觉观测的工作流（上传抽取 ×2 / 拆条 / 取题面补图注 / 推荐里的按需视觉问答）改用
   同一个缝的收集器，**不调 `.llm()`**（零多余派发）。
4. `context.recent_llm_workflows` 的直接使用全部收进 `settle()`（`RetryBudget` /
   `create_llm_observation_collector` 仍由缝使用，不再出现在路由里）。
5. 新测试文件：缝的行为直测 + 单源结构守卫 + 合成片段红证 + 两条路由面用例（视觉零派发、
   推荐双收集器结算顺序与异常路径）。
6. 不动：`_llm` 的工厂兼容面（1 / 2 / 3 参数派发）与 7 处裸 `_llm(context)` 调用；端点路径 /
   事件序列 / 载荷键 / 前端。

## 验收标准

- [x] 25 处全部经缝；webapp 里四件事各恰好一处（按调用点数）且都在缝内（结构守卫断言）
- [x] 守卫带**合成片段红证**：重新长出三件套 → 判据当场认出；同一函数里写两遍 → 也红
      （`tests/test_llm_run.py` 三条守卫用例 + HEAD 版真源码红证
      `probe-02-triple-red-proof.py`）
- [x] `.llm()` 每次现派发不缓存；`settle()` 幂等（重复调用只记一条观测）
- [x] 视觉 5 处只用 `run.collector`，工厂零派发（**走真实视觉端点** `/api/extract` 用记录型
      工厂断言：`test_vision_extract_never_dispatches_the_llm_factory`）
- [x] 推荐路由：主流观测先结算、按需视觉问答后结算；**正文抛错时两者都结算**——走真实推荐
      端点断言观察面板里的两条工作流与先后
      （`test_recommend_settles_both_observations_even_when_the_body_raises`）
- [x] 直测：3 参数工厂收到共享预算与收集器 / 1 参数工厂不炸 / 不调 `.llm()` 零派发 /
      `settle()` 结算 / 零调用不记（`add_completed` 既有语义）/ `settle()` 幂等 / 工作流名
      落在收集器身份里
- [x] `tests/test_webapp.py` 的工厂契约两条用例、观察面板用例、`tests/test_fix_errors.py` 与
      `tests/test_webapp.py` 的 AST 结构钉**判据零改动**全绿
- [x] `python -m pytest -n auto` 全绿；`node --test "tests/js/*.test.mjs"` 全绿（前端零改动）
- [x] 不新增任何真机 / 浏览器项（本单不碰前端与端口）

## Comments

### 2026-09-20 实施记录（Status: resolved）

**实现**

- `src/contest_generator/webapp.py`：新增 `class LLMRun`（紧邻既有 `_llm`）——构造即建
  `RetryBudget` 与 `create_llm_observation_collector(workflow)`；`llm()` 每次现派发（不缓存）；
  `settle()` 幂等结算进 `recent_llm_workflows`。25 处调用点（20 处三件套 + 5 处视觉）全部改
  用它：`llm_run = LLMRun(context, "<工作流名>")` → `llm_run.llm()` / `llm_run.collector` →
  收尾 `llm_run.settle()`。
- `CONTEXT.md`：进度事件行的「主要实现」列补 `webapp.py（LLMRun 观测缝）`，正文补一句观测
  装配单源的口径（Standards 轴判为硬违规：新概念没进词表）。
- 新测试：`tests/test_llm_run.py`（缝直测 7 条 + 单源守卫 3 条）；`tests/test_webapp.py` 两条
  路由面用例（视觉端点零派发 / 推荐双收集器结算与异常路径）。

**机械改写**：`.scratch/webapp-consolidation/apply-02-migrate.py`（逐字形态规则 + 字符串 / 注释
区间保护，73 处替换，逐处打印供复核）；视觉那 5 处因局部变量同名，先手工改完再跑脚本。

**双轴评审（固定点 HEAD 68638782）与处置**

- Spec 轴（`.scratch/webapp-consolidation/spec-review-02.md`）：**1 处硬伤 + 3 条判据强度问题**，
  全部处置：
  ① 计划里的 `__enter__`/`__exit__`（`with` 退出结算）**没有实现**——实施中改成了「显式
  `settle()`」，但没回改 spec / 工单。**处置：改文档而不是加回协议**——25 处调用点每一处本来
  就有明确的结算位置（22 处在既有 `finally`、3 处紧随其后），再养一套 `with` 惯用法是同一件事
  的第二种写法，且会引入无人使用的 API（同轮 Standards 轴正以 Speculative Generality 判掉
  另一个未用面）。spec 与工单的对应段已按实现更正并写明理由。
  ② 守卫按**所在函数去重**，同一函数里写两遍照样绿 → 判据改成**按调用点数**（并补一条"写两遍
  要红"的用例）。
  ③ 推荐路由「双收集器 + 抛错两结算」只有间接覆盖 → 补走真实端点的用例（见上）。
  ④ 红证数字口径（工单原表 25/20/22/26 混了两种口径）→ 工单判据表按守卫实测口径更正为
  23/20/21/23 并注明。
  另：视觉零派发只有自造 run 的间接证据 → 补真实端点用例。
- Standards 轴（`.scratch/webapp-consolidation/standards-review-02.md`）：1 处硬违规（CONTEXT.md
  未更新，已补）+ 3 条判断题：`_llm_run` 纯转发（Middle Man）→ 删掉，调用点直接 `LLMRun(...)`；
  `self.workflow` 无读者（Speculative Generality）→ 删字段，用例改断言收集器身份；
  「为什么要一起做对」的理由在类 docstring / 工厂 docstring / 测试文件头重复三遍 → 收敛到类
  docstring 一处，其余指过去。

**验证读数**：`.scratch/webapp-consolidation/verify-02-homing.txt`（红证原始输出
`verify-02-triple-red-proof.txt`：HEAD 版源码喂同一判据 → 收集器 23 / 预算 20 / 派发 21 / 结算
23 处散落，工作树 → 四条各一处且在缝内）。
