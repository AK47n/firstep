# 02 — LLM 工作流观测收成一处（三件套 20 处 + 视觉半套 5 处）

**要做什么：** 把散在 25 个路由里的「预算 + 观测收集器 + 客户端派发 + 结算」收成一个缝：
`_llm_run(context, workflow)` 造出观测单元，`.llm()` 现派发客户端（语义逐字照旧），`with`
退出即结算进观察面板。新增路由时漏掉其中一件从此不可能——三件套只写一次。

**被谁阻塞：** 无——可立即开始（与 01 无重叠：本单只动 LLM 观测面，不动检测页装配）

**状态：** ready-for-agent

## 判据（单源不变量）

webapp.py 源码里这四件事**各恰好一处**，且都落在缝内：

| 事 | 位置 | 现状 |
|---|---|---|
| `RetryBudget(...)` 构造 | `LLMRun.__init__` | 20 处（14 处局部变量 + 6 处内联） |
| `create_llm_observation_collector(...)` | `LLMRun.__init__` | 25 处 |
| `_llm(context, ...)` 派发 | `LLMRun.llm()` | 22 处（20 处三件套 + 2 处裸调用以外的全部） |
| `recent_llm_workflows.add_completed(...)` | `LLMRun.settle()` | 26 处 |

判据写成**吃源码文本的纯函数**（返回违规清单），既作用在真源码上，也能在合成片段上复现红
（红证不靠手改仓库文件，避免与套件并行时的中间态）。

## 计划

1. `webapp.py` 新增缝（紧邻既有 `_llm`）：
   ```python
   def _llm_run(context: AppContext, workflow: str) -> LLMRun: ...
   ```
   `LLMRun`：`budget` / `collector`（构造即建）；`llm()` **每次现派发**（不缓存——既有契约
   要求同一趟的多次派发共享同一个预算与收集器对象，被两条既有用例钉着）；`settle()` 幂等；
   `__enter__` / `__exit__`（退出即 `settle()`）。
2. 20 处三件套改用缝。两种形态各一套写法，**全文件只此两种**：
   - 同步端点（`with` 退出结算）：
     ```python
     with _llm_run(context, "hwcheck-triage") as llm_run:
         ...  llm_run.llm() ...
     ```
   - SSE 路由（起流前创建、流内 `with` 结算，闭包晚于路由体执行）：
     ```python
     llm_run = _llm_run(context, "tasks-plan")
     def run(emit):
         with llm_run:
             with bind_llm_telemetry(llm_run.collector, emit.progress):
                 result = run_task_planning(llm=llm_run.llm(), ..., emit=emit)
             emit.done(result)
     ```
3. 5 处只做视觉观测的工作流（上传抽取 ×2 / 拆条 / 取题面补图注 / 推荐里的按需视觉问答）改用
   同一个缝的收集器，**不调 `.llm()`**（零多余派发）。
4. `recent_llm_workflows.add_completed` 与 `context.recent_llm_workflows` 的直接使用全部收进
   `settle()`；`RetryBudget` / `create_llm_observation_collector` 从 webapp 的 import 面退场
   （改为在缝内使用）。
5. 新测试文件：缝的行为直测 + 单源结构守卫 + 合成片段红证。
6. 不动：`_llm` 的工厂兼容面（1 / 2 / 3 参数派发）与 7 处裸 `_llm(context)` 调用；端点路径 /
   事件序列 / 载荷键 / 前端。

## 验收标准

- [ ] 25 处全部经 `_llm_run`；webapp 里四件事各恰好一处且都在缝内（结构守卫断言）
- [ ] 守卫带**合成片段红证**：往判据喂一段重新长出三件套的源码 → 违规清单非空（记录在
      `.scratch/webapp-consolidation/`）
- [ ] `.llm()` 每次现派发不缓存；`settle()` 幂等（重复调用只记一条观测）
- [ ] 视觉 5 处只用 `run.collector`，工厂零派发（用记录型工厂断言）
- [ ] 推荐路由：主流观测先结算、按需视觉问答后结算；**正文抛错时两者都结算**（与从前
      `finally` 语义逐字一致）
- [ ] 直测六条：3 参数工厂收到共享预算与收集器 / 1 参数工厂不炸 / 不调 `.llm()` 零派发 /
      `with` 退出结算 / 零调用不记（`add_completed` 既有语义）/ `settle()` 幂等
- [ ] `tests/test_webapp.py` 的工厂契约两条用例、观察面板用例、`tests/test_fix_errors.py` 与
      `tests/test_webapp.py` 的 AST 结构钉**判据零改动**全绿
- [ ] `python -m pytest -n auto` 全绿；`node --test "tests/js/*.test.mjs"` 全绿（前端零改动）
- [ ] 不新增任何真机 / 浏览器项（本单不碰前端与端口）

## Comments

（待实施）
