# 01 — 后端一键清除服务端记录（recent 列表 + AI 推荐缓存 + 重置端点）

**要做什么：** 新增 `POST /api/reset-records`：一键清空 firstep 在服务端留下的全部题相关记录——最近工程列表（`~/.contest_generator/recent.json`）与 AI 推荐缓存（`~/.contest_generator/cache/recommend_*.json`）；返回各自清除的条数/文件数。API 配置（config.json）、任务修复备份（fix-backups）、工程目录与日志一律不动；文件不存在或损坏 = 对应计数 0，不报错。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `recent_jobs.py::clear_recent(fp)` 实现：有记录 → 返回条数且文件写回 `[]`；无文件/损坏 → 0 且不抛
- [x] `recommend_cache.py::clear_recommend_cache(cache_dir=None)` 实现：枚举删除 `recommend_*.json`，返回删除数；目录不存在 → 0；同目录其它文件保留
- [x] `webapp.py` 新增 `POST /api/reset-records`（无 body）→ `{"recent_entries": int, "cache_files": int}`；经 `context.config_path` 定位服务端路径；坏 JSON 不抛
- [x] tests/test_recent_jobs.py：clear_recent 三态（有记录/无文件/损坏）
- [x] tests/test_recommend_cache.py：clear_recommend_cache（多文件+异类文件保留/目录不存在）
- [x] tests/test_webapp.py：端点两态（预置文件清除计数正确 + 文件消失；无记录 → {0,0} 且 config.json 原样）
- [x] 全量 pytest 绿

**评审：** 标准轴（46240693）无硬违规，仅判断项（clear_recent 语义已显式化）；规格轴（78c9096d）功能级无错误，整改项（data-collapse-id / 确认文案 / spec 措辞）已落实。全量 pytest 2807+ / tests/js 667 绿。
