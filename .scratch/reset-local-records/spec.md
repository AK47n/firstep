# spec — 一键重置本地记录（开新题前恢复干净状态）

## 背景与动机

用户反馈：「我觉得这个功能很不错啊，可以放进 firstep，就是一键清理之前的所有缓存记录什么的，能够让 firstep 恢复成第一次打开 firstep 时候的样子，适合每道题做完后开新题之前按一下」。

现状：换题前的清理靠手工（删工程目录 + 删 `~/.contest_generator/recent.json` + 删推荐缓存）+ 一个临时运维页 `/clear-cache.html`。数据散落两处（浏览器 localStorage 与服务端 `~/.contest_generator/`），无统一入口、无确认、易漏。

目标：设置页提供「重置本地记录」按钮 —— 一键清空「上一道题」残留的所有本地记录与缓存，让 firstep 回到开新题的干净状态；API key 与 UI 偏好保留。

## 用户故事

1. 作为用户，我想要在**设置页**看到一个「重置本地记录」入口（危险操作区），以便换题前一键清空。
   - 验收：设置页出现「重置本地记录」卡片（「最近 LLM 工作流」卡与「保存设置」卡之间）；含按钮 + 说明文字（列出将清除的内容与保留的内容）。
2. 作为用户，我想要点按钮后**先弹确认框**（列出将清除的清单，明确提示不可逆），确认后才执行，以便防手滑。
   - 验收：点击按钮 → `confirmModal` 弹窗（danger 样式，确认文案「清空本地记录」）；取消 = 什么都不发生；确认 = 执行清理。
3. 作为用户，我想要清理覆盖**全部题相关本地记录**：
   - 浏览器 localStorage：任务按步自检勾选（`firstep.checklist.v1.*`）、生成页题面草稿（`firstep.draft.v1`）、评分核对勾选（`score-checklist:*`）、购买决策记忆（`firstep.buy-decisions.v1`）。
   - 服务端：最近工程列表（`~/.contest_generator/recent.json`）、AI 推荐缓存（`~/.contest_generator/cache/recommend_*.json`）。
   - 验收：执行后上述数据全部消失；后续流程按「新题」状态工作（草稿不再回填、推荐重新走 LLM、最近工程列表为空、勾选清零）。
4. 作为用户，我想要清理**不动**这些内容：API 配置（config.json，含 key）、UI 偏好（主题 `firstep.theme` / 代码缩放 `firstep.mainc.zoom` / 设置折叠 `firstep.settingsCollapse.v1` / 用量统计 `firstep.usage.v1`）、磁盘上的工程目录与其中的代码与 `.contest_*` 记录（用户成果，属用户文件）、任务修复备份（fix-backups）、日志、sessionStorage 会话 id。
   - 验收：上述内容在清理后原样保持。
5. 作为用户，我想要清理完成后**看到结果汇总**（各类清了多少），以便确认生效。
   - 验收：按钮旁显示结果行，如「已清除：本地记录 12 项；最近工程 3 条；推荐缓存 2 个」；全 0 时显示「没有可清除的记录」。

## 实现决策

- **API 契约**：新增 `POST /api/reset-records`（无 body）→ 200 `{"recent_entries": int, "cache_files": int}`。清理尽力而为：文件/目录不存在 → 对应计数 0；单个文件删除失败不中断（计数只算成功的）。损坏的 recent.json / 残缺缓存同样被清（计数按「读到的正常记录」计，残缺文件算 0 但文件本身归零）。永不触碰 config.json / fix-backups / 工程目录 / 日志。
- **服务端模块**（小函数回所属模块，不塞 webapp.py）：
  - `recent_jobs.py` 新增 `clear_recent(fp: Path) -> int`（记录数 n → 写回 `[]`；文件不存在/损坏 → 0；返回清除条数；损坏文件顺带覆盖为空列表）。
  - `recommend_cache.py` 新增 `clear_recommend_cache(cache_dir: Path | None = None) -> int`（`cache_dir` 缺省 `DEFAULT_CACHE_DIR`；枚举 `recommend_*.json` 删除；目录不存在 → 0；只删该前缀，不动同目录其它文件；返回删除文件数）。
  - `webapp.py` 路由用 `context.config_path` 定位服务端记录（`recent_file(config_path)` 与 `config_path.parent / "cache"`——与 `recommend_cache_path` 缺省目录同源；清理无需读配置，不触发 `_current_config` 加载）。
- **前端**（localStorage 由浏览器同源页面直清，不走后端）：
  - 新纯件 `fx/reset.js`（遵循 fx 无副作用约定）：导出 `RESETTABLE_EXACT_KEYS` / `RESETTABLE_KEY_PREFIXES` / `isResettableKey(key) -> bool`（判定单源：`firstep.checklist.v1.` 前缀、`firstep.draft.v1` 全等、`score-checklist:` 前缀、`firstep.buy-decisions.v1` 全等）；导出 `collectResettableKeys(keys: string[]) -> string[]`（保序、去重）。
  - `ui/settings.js` 胶水：`btn-reset-records` 点击 → `confirmModal({title, message(清除清单), danger:true, confirmText:"清空", cancelText:"取消"})` → 确认后（a）枚举 `localStorage` 遍历收集可清键、逐个 `removeItem`、计数；（b）`apiPost("/api/reset-records")`；（c）结果汇总写入 `#reset-records-msg`（成功类）。失败场景：POST 失败 → 仍显示本地已清 + 服务端失败原因（部分成功语义）。
  - `index.html` 设置页新增卡片 `<div class="card" data-collapse-id="reset-records">`（标题「重置本地记录」+ 按钮 + 说明），不加入 `SETTINGS_DEFAULT_COLLAPSED`（默认展开）。启动挂载点：`initWiringToggle` 类似处（boot 区）——本次按钮监听放 `ui/settings.js` 模块顶层（与 `btn-env-check` 等先例一致），无需 boot 改动。
- **删除临时运维页**：`src/contest_generator/webapp.py:939-941` `/clear-cache.html` 路由 + `src/contest_generator/static/clear-cache.html` 删除（正式入口取代；双入口会漂移）。`webapp.py` 无该路由的相关测试。
- **数据纪律**：清理清单单源 —— 前端键判定唯一在 `fx/reset.js`；服务端清理范围唯一在 `clear_recent` / `clear_recommend_cache` 两函数；设置页说明文案引用同一清单（纯文案，可重复，但必须与单源一致——测试兜底键清单）。

## 测试决策

- 只测外部行为：计数正确、残留消失、不该动的保留。
- `tests/test_recent_jobs.py`：`test_clear_recent`（有记录 → 返回条数且文件变 `[]`；无文件 → 0；损坏 JSON → 0 且不抛）。
- `tests/test_recommend_cache.py`：`test_clear_recommend_cache`（3 个 recommend_*.json + 1 个其它文件 → 返回 3、recommend 全删、其它文件保留；目录不存在 → 0）。
- `tests/test_webapp.py`：`test_api_reset_records_clears_server_records`（预置 `recent.json` + `cache/recommend_*.json` → POST → `{recent_entries:2, cache_files:1}` 且文件消失）；`test_api_reset_records_empty_when_nothing`（无记录 → `{0,0}`；config.json 原样保留断言）。`context` 夹具的 `config_path` 指向 tmp_path。
- `tests/js/reset.test.mjs`（node:test + assert/strict，先例 resource-board.test.mjs）：`isResettableKey`（四类命中 + 保留键 `firstep.theme`/`firstep.mainc.zoom`/`firstep.settingsCollapse.v1`/`firstep.usage.v1` 不命中 + 其它键不命中）；`collectResettableKeys`（保序去重、空输入）。
- 全量回归：pytest + `node --test "tests/js/*.test.mjs"`（必用 glob）。

## 范围外

- 工程目录及其中的 `.contest_*` 记录 / 源码（用户文件，不碰——「做完题开新题」清理的是 firstep 自身记录，不是用户的工程代码）。
- 任务修复备份 fix-backups、webapp 日志。
- API key / 视觉 key（config.json 整体保留）。
- 自动清理 / 定时清理 / 「开新题」时机自动触发（只做手动按钮）。
- 清理结果的持久化历史。
- 服务端新增全局「用量清零」类操作（`firstep.usage.v1` 属 UI 偏好，保留）。
