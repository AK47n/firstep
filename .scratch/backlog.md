# 待办计划（backlog）

后续可做的优化清单（2026-08-19 记录，按需立项走 workflow）。

## 1. 推荐缓存加模块库指纹校验 —— ✅ 已实现（工单 recommend-cache-fingerprint/01，2026-08-19）

**问题**：`validate_recommend` 只校验题面 / 平台 / 赛题键，**不查模块库内容**——库变了（模块增删 / description 变化）缓存照旧命中，直出旧推荐结果。实测：2026C 缓存是旧模块库时代生成的（OLED/LED 被归库外建议），库切换后缓存仍直出。

**已落地**：library_sha256 = ManifestSummary 摘要行（to_line）排序 hash；写缓存存指纹、校验比对；库变 → 缓存失效走真实推荐；旧缓存无字段保守失效（宁可重推）。

## 2. 多实例配置：AI 没猜实例时的自动兜底 —— ✅ 已实现（工单 instance-default-fallback/01，2026-08-19）

**问题**：AI 猜实例（module-multi-instance/06）依赖模型按题面数量输出 instances——题面没写数量（如 2026C"声光提示"）时模型不猜，推荐后实例卡为空，用户要手动添加。

**已落地**：命中多实例模块且 AI 没猜 → 按平台默认自动填（stm32 红黄绿 3 实例 / mspm0 单实例，与"不配置"生成等价零回归），实例卡直接可见可改。

## 3. 母版库浏览 UI 轮（master-library-ui）的剩余候选 —— ✅ 已落地（工单 master-library-ui-2/01-06，2026-08-27）

本轮范围外 / 评审发现的后续可做项（2026-08-27 以 master-library-ui-2 系列全部落地）：

- 母版库详情/浏览的其他候选（用户未选入本轮，多选枚举时排除）：**文件树浏览 / 结构健康复核 / 体积文件统计 / 母版替换入口**——全部落地：体检（health/stats 徽章 + 统计行）、文件树（/tree 端点 + 原生 details 树）、替换入口 = **免提炼快速导入**（import_master_direct + /api/masters/import，「直接导入替换」按钮）；并顺带落地预览增强（复制按钮 + C/XML 轻量高亮）与 confirm 仓库级统一（共享工厂 + 8 处迁移 + alert 归 toast）。
- 提炼确认流程「确认并入库」按钮（卡片1）原用原生 `confirm()`——已随 confirm 统一迁移共享弹窗。
- 关键文件预览的语法高亮 / 复制按钮——已落地（fx/highlight.js + masterContentHTML 复制钮）。
- **单文件写侧替换**（上传替换 pin_config.h / mspm0.syscfg 等关键文件）**评估后不做**：母版 = 生成根，关键文件在生成侧全部是模板/默认值或由渲染器现写（模板 main.c 被骨架覆盖、pin_config.h 被绑定覆写、.uvprojx 由确定性渲染器现写、mspm0.syscfg 是默认外设布局），写侧替换会破坏「母版 = 生成基线」不变量；整体替换已有路径（提炼确认可更换 + 免提炼导入）。详见 .scratch/master-library-ui-2/spec.md「范围外」。

## 4. 阶段 2 收尾评审（code-review b46f786^..HEAD，双轴 Standards + Spec）发现 —— 未立项（2026-08-27）

**发现 1（🔴 硬，Spec/CONTEXT 违背）：ui 模块环 generate-core ↔ generate-readiness**
- 成因：工单 20 补迁 btn-generate 监听器至 ui/generate-core.js（前置校验需 `readinessState`，core.js:35 import 自 generate-readiness）；工单 19 的 readiness 簇反向 import 了 core 的 `desktopTopicOutputEnabled`（readiness.js:21，readinessState() L36 使用）——互为双向。
- 违反 spec.md 桥接约定 3「ui 模块之间允许单向依赖」与 CONTEXT.md「ui 模块间允许单向静态 import」；与仓库既有消环先例不一致（A↔ST 循环 spec L59-63 拆 step-state 消环；15→16→18→19 均为「改接缝 / 静态 import」单向化）。
- 运行时安全（双方均为函数级 live binding、无顶层互调；回归 node --test 444/444、pytest 2465 passed、diag 零 EXC、smoke 11/11、probe-20 6/6），但对未来顶层引用是隐雷。
- 建议：`desktopTopicOutputEnabled`（core.js L125-128：`$("desktop-topic-output")?.checked ?? true` 式无状态 DOM 读）是 fx 纯函数候选——迁 fx/readiness.js 或 fx/generate.js 即断环（与 A↔ST cut 同构，符合「新纯函数一律 fx」）；或按 15→16 先例改回 deps 接缝。二选一，推荐前者。

**发现 2（文档漂移）：spec.md:92 结构钉表陈旧**
- 表项「step-done-refs.test.mjs → ui/generate-steps.js」与实现不符：step-done-refs.test.mjs:13 实际重指向 ui/generate-recommend.js，且指向更正确（文件头注释：cut 方案复核后非 generate-steps；markStepDone(2) / syncStep4( 调用点均在 A 簇）。
- 建议：改 spec.md L92 为 ui/generate-recommend.js（纯文档修正，无代码影响）。

**发现 3（判断项，近硬）：host 残留跨 tab DOM 渲染**
- index.html:2593-2594 启动 IIFE 内 `$("new-platform").innerHTML = state.platforms.map((p) => '<option value="..."'>...).join("")`——母版 tab「新增平台」下拉是 master 簇胶水（工单 04），inline 渲染逻辑与「主体仅剩 imports + 页签分发器 + 启动 IIFE + init* 调用」的目标形态有偏差（IIFE 内其余渲染均已委托簇函数）。
- 建议：迁 ui/master.js（导出 renderNewPlatformOptions 或并入 loadMasters）。

**发现 4（Duplicated Code，判断项）**
- generate-steps.js:68-79：「btn-clear-draft / btn-draft-clear」两个监听器 4 行逻辑逐字重复（clearDraft + 「已清除」→1.5s 还原「清除草稿」）——历史遗留重复，迁移时未合并。建议提共享 handler。
- generate-mainc.js:29-30 / 37-39：滚动三同步（hl.scrollTop/Left、nums.scrollTop）在 syncMainCHighlight 与 scroll 监听器内联重复——建议提 syncScrollFrom（历史遗留）。

**发现 5（Mysterious Name，弱，判断项）**
- generate-steps.js:104 `overviewPlanNow(doneArr)` / :116 `genOverviewWarn(n)`：`n` 为裸步骤号，名称不揭示「按步骤号索引的补齐/警告」语义。低优先。
