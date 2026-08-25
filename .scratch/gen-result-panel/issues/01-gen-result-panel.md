# 01 结果面板两列网格（gen-result-panel）

Status: resolved

## 验收标准

- [ ] #generate-result 重构为 .res-grid（宽屏两列：.res-main 左 / .res-side 右），窄屏单列
- [ ] 既有 id 全部保留（res-dir / btn-copy-dir / res-artifacts / res-includes / res-modules / res-score-points / res-build-hint / res-structure / compile-banner），JS 填充/显隐零改动
- [ ] 每块有 .res-label 小标题；结构树在右列保持 pre.result 样式
- [ ] CSS 用页面令牌（panel/border/阴影），与生成页卡片同风格
- [ ] node --test tests/js/*.test.mjs 全绿；headless 截图目检（宽/窄屏）
- [ ] 中文提交信息
