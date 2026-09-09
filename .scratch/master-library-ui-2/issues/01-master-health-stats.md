# 01 — 母版体检：健康复核 + 体积统计（列表带出，表格徽章 + 详情统计行）

**要做什么：** 母版库每条母版一次算出「健康 + 体积」实况并展示——表格行加
健康徽章（✓ 健康 / ⚠ 有缺失或残留，悬停看明细），详情弹窗元数据段加体积
统计行（总字节 / 文件数 / 大文件 Top 10）；后端在 /api/masters 列表每条带
`health` / `stats` 两字段（一次算好，前端不按条回查——对偶 topic 轮 health
先例），体检口径与既有入库结构分析一致（关键文件缺失 / 工程配置文件 /
构建产物残留 / 统一噪音跳过后的体积与文件数）。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

## 验收标准

- [x] master_store 域函数：`master_health(masters_dir, platform)` 返回
  MasterHealth（ok / missing_key_files / config_file_ok / artifact_dirs）；
  `master_stats(masters_dir, platform)` 返回 MasterStats
  （total_size_bytes / file_count / big_files Top 10 >256KB）；平台
  不存在 → 与既有 get_master 同文案 MasterError；体积/文件数统计走
  统一噪音跳过（构建产物目录不计入，与浏览口径一致）
- [x] GET /api/masters 每条响应带 `health` / `stats`（既有 platform_label /
  key_files 字段不动，既有断言不破）
- [x] fx 纯函数 `masterHealthBadgeHTML(h)`（✓/⚠ + title 明细文本）与
  `masterStatsHTML(s)`（总大小 / 文件数 / 大文件清单，字节 → 可读单位），
  表格行加健康徽章列、详情弹窗元数据段加统计行
- [x] pytest：test_master_store.py（health/stats 用例：正常 / 关键文件缺失
  / 构建产物残留 / 平台不存在；体积与 big_files 数值断言）+ test_webapp.py
  （列表 health/stats 字段形状，tmp 母版注入不碰真实库）
- [x] tests/js：master-ext-browser.test.mjs（健康徽章 / 统计行渲染、
  缺失与残留文案）
- [x] 既有全量回归：pytest 全量 + node --test 全量保持绿；真实库冒烟：
  stm32 / mspm0 两条母版 health 实况正确（mspm0 无 artifact_dirs、
  stm32 关键文件 4 条全存在）
- [x] 中文提交

## 实施记录

（2026-08-27 完成）

- 后端：master_store.py 新增 MasterHealth / MasterStats / BigFileInfo 三数据
  形状与 `master_health` / `master_stats` 域函数（阈值常量
  BIG_FILE_THRESHOLD_BYTES = 256KB、BIG_FILE_TOP_N = 10）；存在性判定收敛进
  `_disk_master_dir`（「母版 {platform!r} 不存在」文案自此单源）、白名单查询
  收敛进 `_master_key_catalog`、构建产物残留判定收敛进 `_top_level_artifact_dirs`
  （与 analyze_structure 同口径）；webapp GET /api/masters 每条带 `health` /
  `stats`（既有字段零改动）。
- 前端：fx/master.js 新增 masterHealthBadgeHTML（✓ 健康 / ⚠ 有缺失或残留 +
  title 明细）与 masterStatsHTML（总体积 / 文件数 / 大文件清单，formatSize
  单源）；masterTableRowHTML 带 health 时出徽章列、masterDetailHTML 带
  stats 时出统计行（均条件渲染，旧调用零变化）；index.html 表头补「健康」
  列 + 徽章样式（评审修复）；masterKeyFileRowHTML 内联大小格式化顺手收口
  formatSize（行为等价）。
- 测试：test_master_store.py 增 11 例（正常/缺失/配置缺失/残留/不存在/
  未知平台 + 计数/噪音跳过/阈值与 Top10）；test_webapp.py 增列表字段断言；
  test_autocommit.py 注册表补 master_health/master_stats（read）；
  tests/js/master-ext-browser.test.mjs 新增（徽章/统计行/条件渲染/转义）。
- 回归：pytest 全量绿（2476 passed）、node --test 454/454；真实库实扫
  stm32 / mspm0 两平台 health ok:true、文件数与体积正常。
- 评审：code-review 双轴——Standards 硬缺陷 1（表头缺健康列，已修）+ 去重
  3 项（已修）+ 观察 2 项（fx-guard 观察项经评估不修：新名从未进
  index.html，不触发双源回退）；Spec 无缺口（仅徽章文案「需关注」→
  「有缺失或残留」对齐 spec，已修）。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
