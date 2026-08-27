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

## 4. 阶段 2 收尾评审（code-review b46f786^..HEAD，双轴 Standards + Spec）发现 —— ✅ 已落地（工单 frontend-es-modules-stage2/21-25，2026-08-27，提交 f26e1fa）

评审发现五项（2026-08-27 以 stage2 工单 21-25 全部落地：node 447/447 + pytest 2465 + diag 零 EXC + smoke 11/11；工单 22-25 状态于 245740d 补翻 resolved）：

- **发现 1（🔴 硬，Spec/CONTEXT 违背）：ui 模块环 generate-core ↔ generate-readiness** —— ✅ 落地（工单 21）：`desktopTopicOutputEnabled` 从 core 归位 readiness 簇（判据输入语义归位），core / steps → readiness 恢复单向；新增 `tests/js/ui-cycle.test.mjs` 静态环检测守卫。原成因：工单 20 补迁 btn-generate 监听器（core:35 import readinessState）+ 工单 19 readiness 簇反向 import core 的 desktopTopicOutputEnabled（readiness.js:21）——互为双向，违反「ui 模块间允许单向静态 import」。
- **发现 2（文档漂移）：spec.md:92 结构钉表陈旧** —— ✅ 落地（工单 22）：stage2 spec.md 钉表改 `ui/generate-recommend.js`（附注「工单 12 重指向：cut 方案复核后非 generate-steps」——step-done-refs.test.mjs:13 实际重指向 A 簇，markStepDone(2) / syncStep4( 调用点均在 generate-recommend）。
- **发现 3（判断项，近硬）：host 残留跨 tab DOM 渲染** —— ✅ 落地（工单 23）：`renderNewPlatformOptions` 导出归 ui/master.js（L676），index.html 启动 IIFE 只留调用（L2635）；IIFE 内其余渲染均已委托簇函数。
- **发现 4（Duplicated Code，判断项）** —— ✅ 落地（工单 24/25）：generate-steps.js 两按钮重复监听器提 `bindClearDraftButton(btnId)` 共享；generate-mainc.js 滚动三同步提 `syncPanels(ta)`（syncMainCHighlight 与 scroll 监听器共用）。
- **发现 5（Mysterious Name，弱，判断项）** —— ✅ 落地（工单 24）：`genOverviewWarn(n)` → `genOverviewWarn(stepNo)`；`overviewPlanNow(doneArr)` 经核语义尚可未改。
