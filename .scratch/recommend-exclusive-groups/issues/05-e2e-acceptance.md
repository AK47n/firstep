# 05 — 端到端验收（2024H 真跑 + stm32 回归）

**要做什么：** 真跑 2024H 推荐（MSPM0）验证两个原始投诉都修好：①不再出现双
8 路灰度配置（pid/xunji 只一个进已选）；②航向保持卡出现（AI 命中或 hint 兜底），
用户可换选 imu_uart / ml_mpu6050。stm32 出题回归无组卡、行为不变。更新
CHANGELOG 并回归全套测试。

**被谁阻塞：** 01、02、03、04

**状态：** resolved

- [x] 真跑 2024H AI 推荐（MSPM0）：done 载荷带 gray-track + attitude-hold 组卡；推荐结果无重复灰度配置（同组只一个进 selectedSlugs）；姿态组卡出现（AI 命中或 hint）
- [x] 组卡交互实测：换选 xunji → 已选只剩 xunji；再点取消 → 整组移除；展开/引脚配置无重复 8 路灰度
- [x] stm32 赛题回归：无组卡、chips 行为与现状一致；旧推荐缓存渲染不变
- [x] 全量 pytest + mypy src 干净；CHANGELOG 中文条目

**Notes:**

## 运行环境关键发现（已处理）
- 127.0.0.1:8000 原服务进程（PID 41180，18:34 启动）加载的是工单 01-03 **之前**的 Python 代码——静态 index.html 从磁盘现读（页面已是新版），但 selection.py 的 exclusive_groups 派生逻辑是进程启动前代码，导致第一次真跑 done 载荷完全无组卡。
- 处理：停止旧进程，用本仓库代码重启 `python -m contest_generator.webapp`（新 PID 31492，日志 .scratch/webapp-stdout.log / webapp-stderr.log），并确认 /api/state 正常。
- 另将 18:37 旧代码时期的脏缓存 `recommend_2024H.json` 移为 `.stale-1837.bak`（旧载荷无 exclusive_groups，会让缓存命中路径看不到组卡；真跑新载荷已重新落缓存）。

## ① 真跑 2024H（MSPM0）——通过
- 临时 PUT /api/settings 关闭推荐缓存 → POST /api/recommend（{problem_text=topic 库 2024H 题面, topic_id:"2024H", platform:"mspm0", reference_ids:[], clarifications:[], qa_text:""}）→ SSE 事件 llm_telemetry×4 / round×2 / converged / done → 校验 PASS（脚本 .scratch/recommend-exclusive-groups/e2e-tmp/api-e2e-real.mjs）。
- 真跑载荷（本轮）：modules=["motor","pid","imu_uart","led_beep","ntb_time"]；gray-track（hint=false，members=[huidu,pid,xunji]，recommended=[pid]）；attitude-hold（hint=false，members=[imu_uart,ml_mpu6050]，recommended=[imu_uart]）；两组各自同组仅 1 个进 modules。
- 另一次浏览器内真跑（同请求、同载荷契约）：modules=["xunji","led_beep","motor","ml_mpu6050"]，gray-track recommended=[xunji]、attitude-hold recommended=[ml_mpu6050]——两组卡同现、每组仅 1 个入 selectedSlugs。
- 页面断言（playwright，缓存命中路径与真跑逐字同载荷）：组卡 2 张、标题含 label、AI 推荐徽标 2 个、同组去重、组员不再渲染独立 chip、需求清单出现「已在『功能组选择』中」灰注、单入选时无冲突黄字警告。

## ② 组卡交互实测——通过
- 换选：默认勾选 xunji → 点击 huidu → selectedSlugs 中灰度组成员仅剩 huidu（等价于 AC 的 pid→xunji 场景，语义一致）。
- 取消：再点已选成员 radio → 整组移除（selectedSlugs 无任何灰度组成员）。
- 展开：重选一名组员后点「展开依赖并检查平台」→ expanded 与 #selected-list 中灰度组成员各仅 1 个（无重复 8 路灰度配置），且无冲突警告；截图 .scratch/recommend-exclusive-groups/e2e-tmp/ui-2024H-groups.png、ui-group-cards-element.png。

## ③ stm32 赛题回归——前端点通过（详见说明）
- 2021F + stm32 真跑 3 次（各全新页面）均被**既有**后端校验拦截：`AI 服务调用失败：模块选择连续 1 次调用失败：模块 led 的实例清单在不同需求条目中不一致`——该校验来自 module-multi-instance/06（commit 5470d62，早于本系列 01-04），与功能组无关（2021F 送药小车题模型跨需求条目给出不一致的 led 实例清单）。
- 前端错误路径回归通过：3 次均无组卡、无 JS 异常、无崩溃，`#recommend-msg` 显示中文错误，其余区域照常。
- chips 行为与现状一致：注入 stm32 风格旧载荷（modules=[pid,led] + requirements 两行 + instances{led}）→ 无组卡、chips 正常渲染；点击 chip 移除 = 从 selectedSlugs 取消勾选、chip 作为推荐标记保留（与 04 前旧行为逐字一致，已对照 73be22f^ 源码）。
- 旧推荐缓存渲染不变：注入无 exclusive_groups 的旧载荷（section C）→ 无组卡、不报错、chips 原样（pid 可移除）。

## ④ 全量测试——通过
- pytest：2288 passed（53.99s，与基线持平，3 个既有 SyntaxWarning）。
- mypy src：Success: no issues found in 60 source files（0 错误）。
- JS 单测（04 已提交）：tests/js/ 全量 142/142 passed。
- CHANGELOG：本工单提交时由 .githooks 自动追加中文条目（见提交）。

## 复现脚本（未入库，仅本次验收用）
.scratch/recommend-exclusive-groups/e2e-tmp/{api-e2e-real.mjs, browser-e2e.mjs, debug-browser.mjs, stm32-retry.mjs, stm32-inject.mjs, shot-groups.mjs}`
