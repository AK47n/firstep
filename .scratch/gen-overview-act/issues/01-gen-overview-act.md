# 01 总览条一键补齐 + 就绪生成按钮（gen-overview-act）

Status: resolved

## 验收标准

- [x] 新增纯函数 `overviewFillPlan(doneSet, hasRecommend, outputDirMissing)`：返回按序 `[{n, action}]`（1 focus / 3 spotlight / 6 adopt|spotlight / 9 focus-dir·仅 outputDirMissing=true 时），全齐返回 []
- [x] 新增纯函数 `overviewReadyToGenerate(checks)`：全 ok → true
- [x] 总览条 `.ov-actions` 行动区：「一键补齐」仅在有关键路径缺失时显示；「生成」仅 generateReadinessChecks 全 ok 时显示且与 btn-generate.disabled 同步
- [x] 一键补齐行为：顺序滚动 + 卡片临时高亮 .ov-fill-target（1.6s 自清）；步骤 1 聚焦 #problem、步骤 9 聚焦 #output-dir；步骤 6 有推荐（lastRecommend.modules 非空）且清单空 → 自动采用（renderRecommendResult(lastRecommend, true)），无推荐 → 仅高亮
- [x] 平台不自动选（仅滚动+高亮）
- [x] tests/js/gen-overview-act.test.mjs 覆盖两纯函数全分支
- [x] node --test tests/js/*.test.mjs 全绿
- [x] 中文提交信息

## 备注（实现期契约漂移记录）

开工验收原文为 `overviewFillPlan(doneSet, hasRecommend)`（行动限 1/3/6）；实现中发现「手动输出目录为空」时总览条会出现两个按钮都隐藏的卡死（9 不在 doneSet 内），故签名追加 `outputDirMissing`、计划新增 9/focus-dir——**已与用户确认扩规**（半自动：只聚焦不代填），spec.md 已同步；canAdopt 显式判「有推荐且清单空」防状态漂移误重复采用。
