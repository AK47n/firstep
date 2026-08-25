# 工单 01：最近生成列表（后端落盘 + 前端条）

Status: resolved
Slug: recent-jobs
依赖：无（新模块 recent_jobs.py + webapp 三端点 + index.html 前端条 + 测试）

## 背景

「几天做一题」场景：生成后关页面，第二天不记得输出目录 / 编译状态。
本工单落地 B2 完整版：后端 recent.json（~/.contest_generator/，cap 20），
生成成功自动记录，编译完成上报状态，生成页顶部展示。

## 验收标准

- [x] `src/contest_generator/recent_jobs.py` 新增：
      `recent_file(config_path)` / `load_recent(fp)` / `record_recent(fp, *,
      output_dir, platform, slugs)` / `update_recent_status(fp, output_dir,
      status)` / `delete_recent(fp, entry_id)`；原子写（tmp+replace）；
      损坏文件 → 空列表；cap 20；同 output_dir 更新移到头部。
- [x] `webapp.py` /api/generate 成功路径自动 `record_recent`（status 初值
      generated；带 topic_id 时一并存）。
- [x] `GET /api/recent` → 最近列表（新→旧）。
- [x] `POST /api/recent/status`（{output_dir, status}）→ 更新状态；
      status 白名单 {generated, compiled_ok, compiled_warn,
      compile_failed}，非法 400 中文；output_dir 无记录 → 200 忽略（不建）。
- [x] `DELETE /api/recent/{entry_id}` → 删除；不存在 404 中文。
- [x] index.html 生成页 `#gen-overview` 后新增 `#gen-recent` 条：
      头部「最近生成」+ 刷新按钮；列表每条 = 时间 + 平台徽章 + 模块数 +
      状态点（灰 generated/绿 ok/黄 warn/红 failed）+ 目录名（点击复制
      完整路径 + toast）+ X 删除；空态「还没有生成记录」。
- [x] 纯函数 `recentStatusMeta(status)` / `recentChipHTML(entry)` 自包含
      （不引用模块级常量），tests/js/recent-jobs.test.mjs 覆盖。
- [x] `runCompileOnce` 拿到 done 后上报状态（ok/warn/failed，超时=failed）；
      生成成功回调 refreshRecent；init 时加载列表。
- [x] tests/test_recent_jobs.py + tests/test_webapp.py + tests/js 全部通过，
      既有测试不回归。

## 实现说明

- recent.json 路径 = `context.config_path.parent / "recent.json"`。
- 前端上报用 `apiPost("/api/recent/status", {output_dir, status})`；
  列表刷新 `refreshRecent()` 全量重拉（列表 ≤20，开销可忽略）。
- 点击复制走既有 `navigator.clipboard` 模式（btn-copy-dir 同款），
  不引后端打开接口（安全面最小先例 report-draft-demo/04）。

## code-review 落实（2026-08-25 双轴）

- Standards：状态白名单重复校验收敛——模块层抛注册异常
  `RecentStatusError`（errors.py 登记 400 中文），路由回归薄壳；
  前端平台标签改查表；`recentStatusNow` 防御分支加注释说明语义。
- Spec：①同目录重生成 = 整条替换（id/ts 更新、status 重置 generated，
  重新生成=新状态，语义有意为之）②failed 判定补 `summary.errors > 0` 兜底
  ③cap 20 双保险：写入端截断 + 读取端（load_recent）再截，手改超 20 不炸。
- 额外修复：`_read` 改 utf-8-sig 容忍 Windows 记事本/PowerShell 写出的 BOM
  （否则 json.loads ValueError → 静默丢条）；既有
  `test_generate_report_draft_telemetry_recorded` 补 tmp config_path，
  杜绝测试污染真实 `~/.contest_generator/recent.json`。
