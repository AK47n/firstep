# 02 — 架构深化 v3：SSE 流化运行器（C2）

**What to build:** 第三轮架构深化（2026-08-08 报告，候选 C2，Strong）。SSE 运行机制（队列 + emit 旁路闭包 + 线程 + stream 生成器 + 终端事件收尾）在 `/api/recommend`（webapp.py:515-572）与 `/api/masters/distill`（webapp.py:783-816）两处字节级重复 ~50 行；终端事件词汇（EVENT_DONE/ERROR/QUESTION）与事件 schema 分居 webapp.py:316-347 与 events.py 两 file。收进一个深模块，两个端点变薄调用；接缝已有两个真 adapter，第三个 SSE 端点（生成进度）零成本接入。

1. **新模块 `src/contest_generator/sse.py`**（深模块）：吸收共享 SSE 块（webapp.py:301-347）——线格式契约注释、`_sse_frame`、`_QueueItem`、`_put_terminal`、`_SSE_QUEUE_MAXSIZE`、`_SSE_TERMINAL_TIMEOUT`，以及运行器组合：队列创建 + `emit` 闭包（put_nowait + Full 旁路）+ daemon 线程（参数 = 核心调用 run() → 终端数据）+ `stream()` 生成器（消费队列 → `_sse_frame` 帧，done/error/question 后停）。接口窄：一次调用 = 一个 run 回调（内部决定发哪些进度事件与终端数据）。
2. **终端事件词汇归位 events.py**：`EVENT_DONE` / `EVENT_ERROR` / `EVENT_QUESTION` 常量从 webapp.py 移入 events.py（事件契约唯一出处，events.py:1-7 docstring 同步更新：终态事件亦归契约），sse.py / webapp.py 从 events 导入。
3. **两个端点瘦身**：/api/recommend 与 /api/masters/distill 保留各自的入参校验与核心调用（select_modules_convergent / distill_master 流水线），SSE 机制一律经 sse.py 运行器；emit 闭包不再出现两次。
4. **测试**：现有端点契约测试全绿不动（线格式"精确一致不得单方面改动"——帧格式逐字节不变，前端 index.html 零改动）；新增 sse.py 运行器单测：队列满丢进度（断线旁路）、终端事件超时丢（断线不卡线程）、done/error/question 收尾停流。

**明确不动的（边界，勿越）**：llm.py（`_emit` 旁路 seam 照旧）、events.py 现有进度常量与 ProgressEvent 字段一字不动（只增三个终态常量）、index.html、错误映射（error 事件内容语义不变）、队列容量与超时数值。

**Status:** resolved

## 验收

- [x] 全量 pytest 绿 + mypy 干净（733 passed；mypy src 24 文件无问题）
- [x] `grep -n "def emit" src/contest_generator/webapp.py` 零命中（emit 闭包只剩 sse.py 一份）
- [x] EVENT_DONE/ERROR/QUESTION 定义只在 events.py；帧格式逐字节不变（现有 SSE 端点测试原样过）
- [x] 新增运行器单测覆盖断线旁路（队列满 / 终端超时）两条路径
- [x] 前端零改动，/api/recommend 与 /api/masters/distill 的流式行为与事件序列不变

## Comments

（2026-08-08 立项，架构评审 C2。与 C1 在 webapp.py 有极小重叠——C1 只改 webapp 的导入行，C2 只改 SSE 区；若并行合入冲突按仓库惯例解决。）

（2026-08-08 实施完成，无行为变化：帧格式逐字节不变、事件序列不变、前端零改动。细节：test_webapp.py 从 webapp 导入 EVENT_DONE/ERROR/QUESTION 的既有契约保持——webapp 保留 re-export 导入行（词表唯一出处 = events.py）；webapp.scan_project 的 monkeypatch 契约保持——端点内 scan_project 调用留在 webapp。工单行号按内容锚点重定位（webapp.py 因 C4 位移，SSE 共享块现位于错误映射区之后）；与并行分支无撞车。）
