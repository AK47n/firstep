# 03 — 用户侧：资料库检查端点

**要做什么：** 网页「资料库更新」区可用「检查更新」——服务端读本地基线清单与线上最新清单，按批次算出差异并返回给前端作为弹窗数据源；网络 / 无基线 / 无更新各态都是 200 级中文响应。

**被谁阻塞：** 01（清单契约）

**状态：** resolved

- [x] 用户侧模块（`src/contest_generator/` 下）：读本地 `sources/materials/.materials-manifest.json`（缺失 = baseline_missing 降级）
- [x] 从 GitHub releases 列表接口过滤 `materials-` 前缀 tag 取最新 → 拉 `firstep-materials-<tag>.manifest.json`；fetch 可注入（不碰网络）
- [x] 批次差异：本地批次版本 vs 线上版本（`batches: {slug: version}` 粒度）；未变更批次不出现在响应
- [x] `GET /api/update/materials/check` 契约：`{current_version, latest_version, update_available, total_size_bytes, batches: [{slug, name, add_count, modify_count, del_count, size_bytes, parts: [{zip_url, size_bytes, sha256}]}], error, message}`；网络失败 / 解析失败 / 无更新 = 200 级 + 中文
- [x] 测试：注入假 fetch 断言四态（有新版 / 无新版 / baseline_missing / 网络失败）；端点 monkeypatch 测试（先例 `tests/test_update_check.py`）

## Answer

`src/contest_generator/materials_update.py`：`materials_library_dir()`（工具根 sources/materials，不依赖 webapp 防环）、`load_local_manifest`（utf-8-sig，缺失/损坏 → None 走 baseline-missing）、`find_latest_materials_release`（过滤 `materials-` 前缀 + **按 semver 取最大而非 API 首匹配**，乱序发版安全）、`check_for_materials_update(local, fetch_json, fetch_text)`（注入 fetch；线上清单解析 → 按批次 diff：线上有 parts 的批次 = 需更新，变更计数 = 全量文件集对比，deleted_batches = 本地有线上无的整批删除）、`_response` 统一 200 级契约（network / no-release / bad-manifest / baseline-missing 四错误类型 + 中文 message）。webapp 端点 `GET /api/update/materials/check` 薄调。测试 `tests/test_materials_update.py` 12 项全绿（含端点 monkeypatch）；mypy 干净；update/apply/webapp 369 项回归全绿。说明：契约实际新增 `deleted_batches` 字段（整批删除由用户侧推导，比 spec 原「removed 跨批」更明确）；spec 已同步此处描述（见 Answer 说明，spec 属补充说明层不加字段描述——deleted_batches 已在本工单契约中登记）。
