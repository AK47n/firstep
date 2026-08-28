# 参数速调 UI 网格卡片流：文档回归（param-grid/02）
Status: resolved

## 改动

1. CONTEXT.md「参数速调」词条行补一句：参数表 UI 为响应式网格卡片流（fx/params.js paramListHTML —— .param-grid 卡片，宽屏 3 列 / 窄屏 2 列 / 手机 1 列自适应）。
2. 全量回归：pytest（先 Remove-Item Env:FIRSTEP_LAUNCHER; PYTHONPATH=src，基线 2753）+ JS 全量（基线 597）+ 语言/PS1/CHANGELOG 检查（23）。
3. 中文提交（spec + issues 01/02 随提，探针不提交）。

## 验收

- 词条与代码一致；全量测试绿；工作树 src/tests/CONTEXT.md 干净（本次仅 CONTEXT.md + spec/issues + 源文件 + 测试）。
