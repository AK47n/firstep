# UI 打磨（ui-polish-8）：代码着色 / 庆祝动画 / toast 动效 / 阶段播报

## 背景

延续 ui-polish-1~7 的界面迭代（全前端，src/contest_generator/static/index.html 单文件，
后端零改动）。用户从 10 项候选中选出 4 项：

1. 代码块行号 + 语法着色
2. 步骤完成庆祝动画
3. toast 动效升级
4. 生成中阶段播报

## 范围

全部只改 `src/contest_generator/static/index.html` + `tests/js/*.test.mjs`。

### 01 代码块行号 + 语法着色（main.c 预览）

- main.c 是 `<textarea id="main-c">`（L825）。text-overlay 方案：
  外层 `.code-wrap`（relative）包住三个层：`.line-nums`（行号列）、`.hl-layer`（pre，
  着色 HTML）、`textarea#main-c`（透明文字 + 青色光标，滚动同步到前两层）。
- 纯函数 `cHighlight(code)`：先 HTML 转义，再正则分 token 着色：
  注释（`//` `/* */`）、字符串、预处理指令、关键字（C 常用词表）、数字；
  输出 `<span class="tok-com">…</span>` 等。自包含、无模块级依赖。
- 纯函数 `cLineCount(code)`：行号列表（`split("\n")`，空串至少 1 行）。
- 同步时机：`input` 事件、生成骨架成功（`$("main-c").value = data.main_c` 处）、
  草稿恢复（draftLoad mainC 处）。
- CSS：`.line-nums` 等宽、右对齐、muted 色、pre 层与 textarea 同字体同 padding，
  禁用用户选择；token 配色：注释绿、字符串琥珀、关键字青、数字紫、预处理灰。
- 亮色主题配色覆盖。

### 02 步骤完成庆祝动画

- `markStepDone(n)` 成功路径统一触发：目标卡 `.step-no` 徽章「弹跳」动画 +
  卡片顶部 2px 青色光带从左扫过（`.celebrate` 类，`animationend` 后移除）。
- `markStepUndone(n)` 移除 `.celebrate`。
- 逻辑放 markStepDone 内部（保持 tests/js 抽取自包含）；动画类名常量内联。
- prefers-reduced-motion 下禁用动画（仅保留勾号变色）。

### 03 toast 动效升级

- 现有 `toast(kind, text)`（TOAST_ICON、#toast-root、2.5s 自动移除、上限 3 条、
  点击关闭、`& < > " '` 转义）保持行为契约不变，仅加：
  - 入场动画：`@keyframes toast-in`（translateY(-6px) → 0 + opacity 0→1，.18s）；
  - 离场动画：移除前加 `.toast-out`（opacity→0 + translateX(6px)，.18s），
    `animationend`/`transitionend` 后再真正移除（上限 3 条逻辑不受影响）；
  - 类型左边框：ok 绿 / error 红 / info 青（现有 border 改 3px 实色左边框 + 背景微染）。
- prefers-reduced-motion 下无动画直接移除。

### 04 生成中阶段播报（前端轻量版）

决策记录：`/api/generate` 为同步 JSON，`generate_project` 无进度发射器；SSE 化核心
路径需动域层+路由+前端三层并适配大量生成测试，本轮不做。真实阶段信息仅有：
校验（同步）、生成（同步等待）、修复中心（SSE 流，真实阶段）。

- 生成按钮点击后 `#gen-status` 升级为阶段播报区：
  1. 「正在校验引脚绑定…」（真实，`/api/bindings/validate` 请求期间）；
  2. 「正在生成工程…」+ 子阶段文案轮播（「选模块→定位母版→生成骨架→写入文件→
     生成摘要」，每 1.8s 切一个）+ 等待计时「已等待 N 秒」（每秒更新）；
  3. 生成成功：「工程生成完成，渲染结果…」→ 清空；
  4. 失败：错误文案（现状）。
- 修复中心阶段播报：`startFixCenter` 已消费 SSE fix 流，事件类型
  （compile_start / fix_start / verify_result / done）→ 在修复中心横幅
  `#fix-status` 显示「编译中…→ 修复中…→ 验证中…」真实阶段（只读现有事件，
  不改 fix 流契约）。
- 纯函数：`genStageTexts(i)`（轮播文案数组循环）、`fmtWait(seconds)`（中文计时）。
- 计时器只在生成请求期间运行，完成/失败/校验失败均清理。

## 非目标

- 不改后端（含 /api/generate 的 SSE 化，见决策记录）。
- 不做其他代码块（引脚配置等）着色，仅 main.c。
- 不做 toast 堆叠布局重构（上限 3 条行为不变）。

## 验收标准

1. main.c 有行号与四类 token 着色，滚动三者同步，光标可见、文字不双影；
   生成成功 / 草稿恢复 / 手动输入均刷新。
2. 步骤完成时徽章弹跳 + 顶部光带，动画结束类自动清理；undo 移除。
3. toast 滑入滑出，类型左边框，2.5s/上限 3/点击关闭/转义行为不变。
4. 生成期间 gen-status 显示轮播阶段 + 计时；完成/失败清理；修复中心显示
   编译/修复/验证真实阶段。
5. `node --test tests/js/*.test.mjs` 全绿（新增 cHighlight / cLineCount /
   genStageTexts / fmtWait 用例）；`python -m pytest tests/test_generate_check_contract.py`
   50 全绿；CDP 无头 Edge 截图目检。

## 工单

- issues/01-code-highlight.md：行号 + 语法着色
- issues/02-celebrate.md：步骤完成庆祝动画
- issues/03-toast-anim.md：toast 动效升级
- issues/04-stage-report.md：生成中阶段播报
