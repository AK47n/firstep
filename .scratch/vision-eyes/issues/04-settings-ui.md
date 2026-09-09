# 04 — 设置页视觉通道配置

**要做什么：** /api/settings GET/PUT 支持 vision_base_url / vision_api_key / vision_model（缺省兼容旧 config）；设置页「视觉通道」卡片（base_url / key 掩码 / 模型 + 说明文案：免费 GLM-4V-Flash、无 key 关闭）；状态横幅提示视觉开/关。

**被谁阻塞：** vision-eyes/01（配置字段）；可与 02/03 并行。

**状态：** resolved

- [x] /api/settings 读写三个新字段（缺省 = 旧 config 逐字节兼容；key 掩码语义照现有 api_key）
- [x] 设置页视觉卡片 UI（base_url / key / 模型输入 + 说明）
- [x] 无 key 时横幅/提示（与现有"尚未配置 API key"同款）
- [x] 测试：settings 读写 / 缺省兼容（照 test_webapp 先例）
- [x] 全量测试通过


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
