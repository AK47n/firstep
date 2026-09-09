# 02 前端：设置页「问答式精注记」开关（vision-detail-qa）

Status: resolved

## 目标

设置页「视觉通道」区加开关 checkbox（`#set-vision-detail-qa`，默认勾选），保存/加载接入既有 settings 流程。

## 验收标准

- [x] index.html 视觉通道区新增 checkbox + 说明文字（样式同 set-recommend-cache）
- [x] loadSettings：`$("set-vision-detail-qa").checked = s.vision_detail_qa !== false`（旧 state 缺字段默认开）
- [x] btn-save-settings payload 加 `vision_detail_qa: $("set-vision-detail-qa").checked`
- [x] 保存后立即生效（刷新页面开关状态保持）
- [x] `node --test tests/js` 全绿（无新纯函数，回归即可）

## 提交

中文提交信息。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
