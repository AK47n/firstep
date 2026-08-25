# 03 修复中心 / 修订深化卡内分组（ui-detail）

Status: resolved

## 验收标准

- [ ] 新增 .card-group / .card-group-title CSS（panel-2 底 + 边框 + 圆角 + 小标题）
- [ ] 卡 10：编译输出（自动采集）、手动模式（无工具链回退）两段包成 card-group；主操作区不动
- [ ] 卡 11：上下文入口（两入口行）合成 group；已加载上下文/影响分析/确认并执行 三个 box 加 .card-group
- [ ] 全部既有 id 保留，JS 选择器零改动（先 grep 确认无 JS 引用被改的 h3）
- [ ] node --test 全绿；headless 截图目检两卡
- [ ] 中文提交信息
