# 22 — 结构钉表修正：spec.md step-done-refs 指向 generate-recommend.js

**要做什么：** 纯文档修正——`.scratch/frontend-es-modules-stage2/spec.md:92` 结构钉重指向表把 `step-done-refs.test.mjs` 列为 → ui/generate-steps.js，与实际实现不符：`tests/js/step-done-refs.test.mjs:13` 重指向 `ui/generate-recommend.js`，且实现更正确（文件头注释「cut 方案复核后非 generate-steps」；markStepDone(2) / syncStep4( 调用点均在 A 簇 generate-recommend）。

**被谁阻塞：** 无

**状态：** resolved（代码/文档已于 f26e1fa 提交，2026-08-27 收尾时补翻状态）

## 验收标准

- [ ] spec.md:92 表项改为 `ui/generate-recommend.js`（可加一句「工单 12 重指向：cut 方案复核后非 generate-steps」注记）
- [ ] 复核该表其余表项（90-95 行）与实现一致：group-cards / recommend-telemetry → generate-recommend ✓；score-points-format / btn-icons / price-reference-clear / generate-overwrite 等核对后不动的项无需改动
- [ ] 纯文档零代码改动；git diff 仅 spec.md 一行

## 实施记录

- spec.md:92 表项已改「ui/generate-recommend.js（工单 12 重指向：cut 方案复核后非 generate-steps）」；其余表项（group-cards / score-points-format / recommend-telemetry / btn-icons / price-reference-clear / test_generate_check_contract）核对与实现一致，未动。
- git diff 仅 spec.md 一行（连同 21-25 工单文件一并提交）。
