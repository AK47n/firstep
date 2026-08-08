# 工单 02：5 个架构评审 DRAFT PR 评审合并（2026-08-07）

状态：resolved。5 个 PR 全部评审通过并合入 main，远端分支已删。

## 前置处理

- 开工时发现远端 main（32f45b5）落后本地 main（565e2da）30 个提交（工单 01-09
  等从未推送）——用户确认先 push 本地 main 后再合 PR。
- 网络故障：git/curl 的 libcurl 栈连不上 github.com，gh 的 go 栈正常；用户开启
  加速器后恢复，未用 SSH 方案。

## 各 PR 记录

| PR | 分支 | 评审结论 | 合并 commit | 测试结果 |
|----|------|----------|-------------|----------|
| #2 | worktree-candidate-03-error-mapping | 通过：error_to_http 表覆盖业务/工程文件/OSError/LLMError，未登记→500（旧兜底 400 已删），19 路由全挂 `@_map_errors`，HTTPException 穿透，per-route catch 无遗漏；SSE 化适配（distill 端点错误改走流内 error 事件，2 测试改写） | d3880d3 | 406 passed → 合并后 487/492 passed |
| #3 | worktree-candidate-04-rule-categories | 通过：RULE_CATEGORIES 描述表驱动六处流水线，`_validate_category_disposition` 替代四校验，行为等价逐点核对；与工单 09 结构性融合（config_files 进表尾 keep、startup_files 作表内钩子、恢复 `_validate_forced_exclusions`） | 1fc1ef8 | 404 passed → 488 passed |
| #4 | worktree-candidate-05-judgment-ownership | 通过：JudgmentFile/FileVersion 迁 report.py，master 不再从 llm 导入模型类型（仅 LLM/ProgressEmitter 协议），version_groups 单源 + 不变量校验（版本非空/各组非空/组间不重叠） | d505d9a | 407 passed → 492 passed |
| #1 | worktree-arch-llm-retry-primitive | 通过：`_batches`/`_retry_batch` 原语与旧孪生函数行为等价（判定阶段逐位一致，摘要阶段多跨轮去重——描述明示的修复）；合并时 `_retry_batch` 吸收 retry 事件发射参数（progress_emitter/batch_index/phase），`_judgment_batches`/`_chunked` 调用点迁移到 `_batches` | 2c1cb6d | 403 passed → 492 passed |
| #5 | worktree-distill-progress-spec | 通过：spec/ADR 0004/CONTEXT 词条与已合入 distill-progress 实现一致（ProgressEvent 发射 seam、SSE 端点、事件契约）；内容已随本地 main 进入远端，GitHub 自动标记 MERGED | —（head 85ab9ab 已是 main 祖先） | 纯文档，无测试 |

## 遗留项

- `tests/test_master.py::test_real_projects_2026c_21f_distill_and_import` 在任务
  开始前 main 上即红（1 failed/485）：真机素材 2021F/21F 工程含
  "最新ALX-AOA-FIT跟随套件开发资料" 目录 67 个 .c 未被 uvprojx 引用，工单 09
  入库结构校验拒绝。非本次 5 个 PR 引入；素材处理 / 校验逻辑调整另行处理。
- 最终 main 全量：492 passed + 上述 1 个既有失败。
