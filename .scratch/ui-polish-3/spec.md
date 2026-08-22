# Spec：草稿记忆 + 顶部进度条 + Toast 轻通知（ui-polish-3）

> 状态：已完成（工单 01/02/03 全部 resolved，2026-08-22）。

> 延续 ui-polish / ui-polish-2 的迭代。用户确认「继续优化」；本轮自主选三个低风险高性价比方向（E/C/D），B（卡片折叠）留待单独一轮。

## 问题陈述

1. 生成页工作（题面 / 平台 / 模块 / main.c / Q&A）刷新即丢，误刷新损失大；
2. 12 步流程的整体进度（已完成几/12）没有一处总览，靠数左侧绿点；
3. 关键成功事件（生成完成 / 编译通过 / 复制成功 / 修订完成）只有行内小字，不够显眼。

## 方案

### E. 草稿自动记忆（localStorage）

- 自动记忆：赛题原文（problem）、历史题号（currentTopicId / topic-id 输入框）、目标平台（chosenPlatform）、已选模块（selectedSlugs）、main.c 内容、修订 Q&A（qa-text）；
- 写入时机：相关输入 input 事件（防抖 ~400ms）与选择变更处（平台选定 / 模块增删 / 引脚绑定）；
- 恢复：页面 init 完成后读取并回填，随后按内容标记对应步骤已完成（1 / 3 / 6 / 8 视内容而定），导航与卡片状态一致；
- 提供「清除草稿」入口（设置页新增一行说明 + 按钮；生成页提示条在恢复时短暂显示「已恢复上次草稿（清除）」链接）；
- 存储 key：`firstep.draft.v1`；读取必须 try/catch（JSON 损坏 / 被禁用时静默降级为新会话）；
- 不自动恢复会触发后端请求的内容（不重发推荐/生成），只恢复表单态。

### C. 顶部进度条 + 完成计数

- header 下方一条 3px 青色渐变细进度条，右端小字「已完成 n/12」；
- 数据源：markStepDone / markStepUndone 维护 done 集合，变更时同步进度条（进度 0 时隐藏整条，>0 淡入）；
- 切到非生成 tab 时隐藏（进度属生成流程）；回到生成 tab 恢复显示；
- 纯函数 `stepProgress(doneCount, total)` → `{ pct, text }`（pct 0~100，text "已完成 n/12"）供单测抽取。

### D. Toast 轻通知

- 右上角固定容器 `#toast-root`，`toast(kind, text)`：ok（青色）/ error（红色）/ info（灰色），2.5s 自动淡出，最多同屏 3 条，手动可点关闭；
- 接入点（只加不减，行内提示保留）：
  - 上传抽取成功、历史题面取题成功 → ok；
  - 生成完成 → ok「工程生成完成」；
  - 编译通过（compileBanner success）→ ok「编译通过」；
  - 交接提示词复制成功 → ok「已复制到剪贴板」；
  - 修订 / 深化完成 → ok；
  - 生成 / 上传失败 → error（简短，详情仍在行内）。

## 实现决策

- 只改 `src/contest_generator/static/index.html` + 新增 `tests/js/*.test.mjs`；后端零改动、API 契约零改动。
- localStorage 读写抽纯函数（可注入 storage，Node 单测用假 storage）：`draftSave(storage, state)` / `draftLoad(storage)` / `draftState(problem, topicId, platform, slugs, mainC, qa)` / `draftRestoreMeta(json)`（校验+裁剪非法字段）。
- 进度条与 toast 为 DOM 组件，不抽纯函数；`stepProgress` 抽纯函数。
- 视觉回归：无头 Edge + CDP 截图（进度条显示态、toast 弹出态）+ 计算样式断言；本地服务器 8000 端口已在跑。

## 测试决策

- 新增 `tests/js/draft-memory.test.mjs`（draftSave/Load/State/RestoreMeta 假 storage 用例，含损坏 JSON 兜底）与 `tests/js/step-progress.test.mjs`（stepProgress 边界：0/12、12/12、中间值）；
- `node tests/js/*.test.mjs` + `pytest tests/test_generate_check_contract.py` 全绿；全量 pytest 后台跑一次保底。

## 范围外

- B 卡片折叠（单独一轮）；不改后端；不做多标签页同步（localStorage storage 事件不监听）。
