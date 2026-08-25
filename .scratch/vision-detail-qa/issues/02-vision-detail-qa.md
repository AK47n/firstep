# 02 前端：设置页「问答式精注记」开关（vision-detail-qa）

Status: resolved

## 目标

设置页「视觉通道」区加开关 checkbox（`#set-vision-detail-qa`，默认勾选），保存/加载接入既有 settings 流程。

## 验收标准

- [ ] index.html 视觉通道区新增 checkbox + 说明文字（样式同 set-recommend-cache）
- [ ] loadSettings：`$("set-vision-detail-qa").checked = s.vision_detail_qa !== false`（旧 state 缺字段默认开）
- [ ] btn-save-settings payload 加 `vision_detail_qa: $("set-vision-detail-qa").checked`
- [ ] 保存后立即生效（刷新页面开关状态保持）
- [ ] `node --test tests/js` 全绿（无新纯函数，回归即可）

## 提交

中文提交信息。
