# 03 — 后端：检查更新端点 /api/update/check

**要做什么：** 用户在设置页点「检查更新」→ 得到「当前版本 / 最新版本 / 是否有新版 / 更新包下载地址 / 大小 / 更新说明」，无网或 GitHub 不可达时得到中文提示而不是报错。

**被谁阻塞：** 02（版本比对依赖 `__version__` 语义对齐）

**状态：** resolved

- [x] `GET /api/update/check`：请求 GitHub Releases API（repo AK47n/firstep，latest release + assets），从资产中识别 `firstep-update-*.zip` 与配套 `.sha256.txt`（tag 精确匹配，避免同 release 多包选错）
- [x] 返回契约：`{current_version, latest_version, update_available, zip_url, size_bytes, sha256, release_notes, published_at, error, message}`；无更新包资产 / 无新版 = `update_available: false` 并附中文文案；`sha256` 由服务端读 `.sha256.txt` 资产内容返回（apply 只下 zip）
- [x] 网络不可达 / 非 2xx / 资产缺失 → 中文 200 级错误提示（error 登记 network / no-asset，不 500、不裸异常）
- [x] 复用既有测试先例：mock GitHub API → 断言有新版 / 无新版 / 不可达 / 无资产 / sha 缺失 / 非法版本降级与返回形状（tests/test_update_check.py，15 项全绿）
- [x] 版本比对逻辑纯函数化（`compare_versions(current, latest)`，容忍 v 前缀、非法返回 None 由调用方降级），可单测

## Answer

新增 `src/contest_generator/update.py`（纯函数 + 可注入 HTTP），webapp.py 注册 `GET /api/update/check`（放 /api/health 之后）。关键实现点：`resolve_assets` 按 `firstep-update-<tag>.zip` 精确匹配 tag；sha256 从配套 `firstep-update-<tag>.sha256.txt` 资产拉取（内容解析首个 64 位 hex）；fetch 参数用 None 哨兵而非默认绑定函数对象（否则 monkeypatch 失效）。测试 15 项全绿。
