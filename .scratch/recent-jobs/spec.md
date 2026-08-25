# 最近生成列表（B2 完整版）

## 问题陈述

用户场景 = 一题做几天、几天做一题：生成工程后常常关页面，第二天想继续
却发现「上次生成到哪 / 输出目录在哪 / 编译过没有」全忘了——草稿记忆
（localStorage）只存题面/平台/模块/骨架/Q&A，不存生成结果与编译状态。

## 方案

**后端落盘 `recent.json`**（与 config 同目录 `~/.contest_generator/`），最多
20 条，新→旧：

- /api/generate 成功时**自动记录**：`{id, ts, platform, slugs, output_dir,
  status: "generated"}`（同 output_dir 已存在 → 更新移到头部，防重复）。
- 前端每次编译完成（`runCompileOnce` 拿到 done 载荷后）上报状态接口：
  `generated / compiled_ok / compiled_warn / compile_failed`（超时归
  compile_failed；有错归 failed；0 错 N 警归 warn；0 错 0 警归 ok）。
- 前端生成页顶部（就绪总览条下方）新增「最近生成」条：每条 = 时间 +
  平台徽章 + 模块数 + 状态点（灰/绿/黄/红）+ 目录名（点击=复制完整路径
  + toast，安全面最小：不引后端打开/删除文件接口，与自动产物先例一致）；
  右侧「刷新」按钮 + 空态文案。
- 删除：每条 X 按钮 → `DELETE /api/recent/{entry_id}`（清错记 / 不想要的）。

## 用户故事

- 作为用户，第二天打开页面，顶部「最近生成」一眼看到上次工程的目录与
  编译状态，点一下复制路径就能继续。
- 作为用户，编译修复跑完后回来刷新页面，状态点自动变绿/黄/红，不用回忆。

## 实现决策

1. 新模块 `src/contest_generator/recent_jobs.py`：load/save（原子写
   tmp+replace）/record/update_status/delete 纯函数；损坏/缺失文件 → 空列表
   不炸；cap=20。
2. 路由只做薄壳装配（generate 成功处一行 record、三个新端点 GET/DELETE/
   status-POST），校验：status 白名单 {generated, compiled_ok,
   compiled_warn, compile_failed}；DELETE 不存在 → 404 中文。
3. 状态更新由前端驱动（runCompileOnce 拿到 done 后上报）——编译链路
   （SSE /api/compile）不改动，避免动 compile_runner 域模块。
4. 前端纯函数 `recentChipHTML(entry)` / `recentStatusMeta(status)` 自包含
   供 tests/js 抽取；渲染用 esc() 转义。
5. 列表加载：init 时 + 生成成功回调 + 编译上报后各 refresh 一次（列表小，
   全量重拉开销可忽略）。

## 测试决策

- tests/test_recent_jobs.py：record/同目录更新/update_status/delete/损坏
  容错/cap 截断。
- tests/test_webapp.py：生成成功 → GET /api/recent 含记录；POST status →
  状态变更；DELETE → 消失 + 404；未生成时 GET 空列表。
- tests/js/recent-jobs.test.mjs：recentChipHTML / recentStatusMeta 纯函数。

## 范围外

- 打开工程目录 / 删除工程文件（安全面最小：只复制路径）。
- 跨设备同步 / 云端。
- 列表分页 / 搜索（cap 20 够用）。
