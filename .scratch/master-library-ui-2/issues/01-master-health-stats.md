# 01 — 母版体检：健康复核 + 体积统计（列表带出，表格徽章 + 详情统计行）

**要做什么：** 母版库每条母版一次算出「健康 + 体积」实况并展示——表格行加
健康徽章（✓ 健康 / ⚠ 有缺失或残留，悬停看明细），详情弹窗元数据段加体积
统计行（总字节 / 文件数 / 大文件 Top 10）；后端在 /api/masters 列表每条带
`health` / `stats` 两字段（一次算好，前端不按条回查——对偶 topic 轮 health
先例），体检口径与既有入库结构分析一致（关键文件缺失 / 工程配置文件 /
构建产物残留 / 统一噪音跳过后的体积与文件数）。

**被谁阻塞：** 无——可立即开始

**状态：** ready-for-agent

## 验收标准

- [ ] master_store 域函数：`master_health(masters_dir, platform)` 返回
  MasterHealth（ok / missing_key_files / config_file_ok / artifact_dirs）；
  `master_stats(masters_dir, platform)` 返回 MasterStats
  （total_size_bytes / file_count / big_files Top 10 >256KB）；平台
  不存在 → 与既有 get_master 同文案 MasterError；体积/文件数统计走
  统一噪音跳过（构建产物目录不计入，与浏览口径一致）
- [ ] GET /api/masters 每条响应带 `health` / `stats`（既有 platform_label /
  key_files 字段不动，既有断言不破）
- [ ] fx 纯函数 `masterHealthBadgeHTML(h)`（✓/⚠ + title 明细文本）与
  `masterStatsHTML(s)`（总大小 / 文件数 / 大文件清单，字节 → 可读单位），
  表格行加健康徽章列、详情弹窗元数据段加统计行
- [ ] pytest：test_master_store.py（health/stats 用例：正常 / 关键文件缺失
  / 构建产物残留 / 平台不存在；体积与 big_files 数值断言）+ test_webapp.py
  （列表 health/stats 字段形状，tmp 母版注入不碰真实库）
- [ ] tests/js：master-ext-browser.test.mjs（健康徽章 / 统计行渲染、
  缺失与残留文案）
- [ ] 既有全量回归：pytest 全量 + node --test 全量保持绿；真实库冒烟：
  stm32 / mspm0 两条母版 health 实况正确（mspm0 无 artifact_dirs、
  stm32 关键文件 4 条全存在）
- [ ] 中文提交

## 实施记录

（待实施）
