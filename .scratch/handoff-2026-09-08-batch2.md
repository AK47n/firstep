# 会话交接（2026-09-08，第 2 批开工前）

本文件给**新会话**当入口：读完即可接着干，不必回翻旧会话。

## 新会话推荐档位

**high**（够用且省）。理由：第 2 批是「改既有代码 + 真实库回归验证」，不是超大重构；决策点已在本文件里钉好，新会话主要是执行与验证。若你打算同时动「参考库内容补录」那条工作线，再上 **max**。

## 已完成（3 笔提交，全绿）

| 提交 | 内容 |
|---|---|
| `8065fbfd` | preselect-recall-visibility/01-02：判据取源归位（`TopicContext.library_summaries` / `PreselectResult.library_summaries` / `known_summaries` 可选入参）+ 覆盖率守卫（`tests/test_preselect_coverage.py`，6 组 xfail strict） |
| `96e739d9` | beep-pin-declaration/01：beep 补 pins 声明 + 全库引脚宏不变量（`tests/test_library_invariants.py`） |
| `6ca1139d` | library-hookup-and-invariants/01-02：8 个器件词表挂接 + 7 条库不变量进 pytest |
| `ad8a4983` / `ae5b5519` | backlog 状态更新 |

**当前测试状态**：`python -m pytest -q` → **3860 passed, 6 xfailed**（6 个 xfail = 第 2 批的验收缺口，见下）。mypy 改动源文件零告警。

## 第 2 批要解决的问题（唯一剩下的 P0 可见性）

2024H/stm32 预筛仍只见 **34/86**，`motor` 排名 71、`pid` 76、`servo` 78、`led` 67、`key` 65 全在截断线外。推荐流程已不中断（第 1 批修好了），但模型看不见这些模块的简介。

**量化事实**（探针见 `.scratch/library-audit/`）：

- 摘要行均值 1006B，其中 **description 占 72.6%（62802B）、套件段占 23.5%（20325B）**——真正在吃预算的是这两段。
- 瘦身到「首句 + 依赖 + 多实例标记」后：stm32 全库 **13313B** / mspm0 13282B，**预算 40000B 装得下全库 → 截断可以彻底消失**（`probe_sim_lean.py`）。
- 得分分布 `{1: 46, 0: 40}`：46 条并列 1 分全靠 slug 字典序，sensor 组因 `_term_matches_topic` 的中文 2 字滑窗（题面「传感器」→「传感」/「感器」命中 33 条方案名）白得 1 分（`probe_why_hits.py`）。
- 常备名额保底方案**无效**：传感器洪水占满名额，插不进关键模块（`probe_sim_quota.py`）。

## 两个已定结论（不要重新论证）

1. **骨架映射（5.4③）不能单独做**：`MODULE_PERIPHERAL_TERMS` 的值必须都在 `PERIPHERAL_TERMS` 里，而 75 个未映射模块需要的词项大多不在词表；且参考库 148 条标题里 **29/57 个词项 0 命中**（oled/lcd/key/led/beep/servo 全 0）。要动就得同时扩词表 + 保证词项能命中参考条目（`probe_term_effect.py`）。
2. **词表预算余量已吃紧**：`WORDLIST_PROMPT_BYTES` 8500 → 9200（词表完整 wire 8849）。最坏形态 mspm0 余量 **378B**（旧 727B）、stm32 998B——**后续往词表加内容先瘦身，不要再抬预算**（`probe_budget_headroom.py`）。

## 待用户拍板的两点（旧会话问了、用户改开新会话，未答）

1. **第 2 批路线**：(a) 摘要行瘦身——全库可装、截断消失（**推荐**，一步到位）；(b) 原计划——中文反向滑窗收紧 + 运动控制词族 + 分桶名额（不碰提示词格式，但天花板仍在）；(c) 先写方案对比再定。
2. **骨架映射**：并进第 2 批并加「每个新词项必须至少命中一条参考条目标题」的验收（**推荐**）／先冻结只做预筛／先补参考库内容。

## 开工步骤

1. 读 `CLAUDE.md`、`CONTEXT.md`、`docs/agents/workflow.md`。
2. 读 `.scratch/preselect-recall-visibility/spec.md` 与两张工单（第 1 批的完整决策与红证留痕）。
3. 读 `.scratch/library-hookup-and-invariants/spec.md`（第 3 批；含骨架映射为何转批的理由）。
4. 用 `probe_guard_cases.py` 复测当前缺口（应仍 6 组 xfail），再按用户拍板的路线立项：`.scratch/preselect-visibility/<spec.md + issues/NN-*.md>`。
5. 走 workflow：spec → 工单 → TDD 逐张 → `code-review` 双轴 → resolved + **中文提交**。
6. **第 2 批的验收就是那 6 条 xfail**：修好后它们自动 XPASS，`strict=True` 会报错提醒摘掉标记——摘掉即转常规守卫。

## 一个操作提醒

正在跑的应用（端口 4003）是 `PYTHONPATH=src` 直跑源码、`uvicorn.run(app)` **不带 reload**——改动要 `stop-firstep` + `start-app` 重启才生效。第 1 批的修复至今未在运行中的应用里生效过。
