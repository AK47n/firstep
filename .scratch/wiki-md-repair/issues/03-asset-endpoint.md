# 03 — 图片资源端点（后端）

**要做什么：** 让 Markdown 手册里的图片能在浏览器中请求到：`md_library.py` 新增
`resolve_md_asset()`（路径安全 + 存在性 + 16MB 上限），webapp 新增
`GET /api/materials-md-assets/{rel_path:path}` 按扩展名回 Content-Type，
配 Python 测试（200 + 类型、非法路径 400、缺失 400、超限 400）。

**被谁阻塞：** 无——可立即开始（端点服务于素材库任意批次资产，不依赖重抓）。

**状态：** resolved

**结论：** 2026-09 完成并提交。`resolve_md_asset` 复用 is_unsafe_path + 存在性 + **仅放行图片扩展名**（评审整改：任意扩展名放行缩窄为 _ASSET_MEDIA_TYPES 六种，防 .html/.exe 经此分发）+ 16MB 上限；`asset_media_type` 按扩展名回 Content-Type（未知回退 octet-stream）；路由 `GET /api/materials-md-assets/{rel_path}`。服务端实测：彩屏 gif 端点 200 image/gif 1,621,056 字节。测试：md_library 5 条 + webapp 5 条（含非图片 400、超限引用常量）。

- [x] `resolve_md_asset` 复用 `is_unsafe_path`（绝对路径/盘符/反斜杠/`..`/空段拒绝），
      缺失/非文件 → ReferenceError（webapp 映射 400 中文）。
- [x] 上限 16MB（超限 → 400 中文，不静默截断）。
- [x] 路由按扩展名回 Content-Type：png/jpg/jpeg/webp/gif/svg。
- [x] `tests/test_md_library.py` + `tests/test_webapp.py` 覆盖上述断言。
