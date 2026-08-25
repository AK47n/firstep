# 工单 01：视觉通道自检接口与设置页按钮

Status: resolved
Slug: vision-selfcheck
依赖：无（webapp.py 新路由 + index.html 设置页按钮 + 测试）

## 背景

视觉通道配置项在设置页「视觉通道（可选）」卡（`#set-vision-base-url` /
`#set-vision-model` / `#set-vision-api-key` / `#set-vision-detail-qa`）。
有效参数装配 = `webapp.py:_resolve_vision`（视觉 key 留空 + DeepSeek 端点
复用主 key）。本工单新增「自检」：真实调用一次视觉模型验证链路。

## 验收标准

- [x] `webapp.py` 新增 `POST /api/vision/selfcheck`（`@_map_errors` 包裹）。
- [x] 配置未保存（config None）→ 400「请先保存主 API key 配置」。
- [x] 视觉 key 经 `_resolve_vision` 解析为空 → 400「视觉通道未配置：请到
      设置页…」（含「设置」引导，不套「自检失败」前缀；场景 = 自定义端点
      未配 key；DeepSeek 默认端点会复用主 key 不触发）。
- [x] 成功：对内置 1×1 PNG 调 `describe_image`（无缓存）→
      `{ok: true, elapsed_ms: int, model: str, message: str}`。
- [x] `VisionError` → 400「视觉自检失败：…」（含原错误）。
- [x] `index.html` 设置页视觉卡内加按钮 `#btn-vision-selfcheck` +
      状态行 `#vision-selfcheck-status`（muted，初始空）。
- [x] 点击：状态行「正在调用视觉模型…」→ 成功
      「✓ 视觉通道正常（模型 …，耗时 …ms）」绿字（.ok 类）；
      失败红字（.error 类）显示 `e.message`。
- [x] tests/test_webapp.py 新增 3 用例（成功 / 未配置 / VisionError 失败），
      既有测试不回归。

## 实现说明

- webapp.py 从 `.vision` 增补 import：`VisionError, describe_image`。
- 1×1 PNG base64 常量 = 既有测试同款
  `iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==`。
- 自检 prompt 独立常量（如「这是一张 1×1 测试图，请用一句话描述你看到的。
  若看不清内容，直接回复『测试图』。」）——与业务描述 prompt 区分。
- 前端 `apiPost("/api/vision/selfcheck")`（空 body）挂在设置脚本区
  （btn-save-settings 附近）；status 文案用 esc() 转义 message/model。
