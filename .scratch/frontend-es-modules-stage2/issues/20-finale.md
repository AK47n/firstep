# 20 — 收尾：host 瘦身 + 结构钉盘点 + 全量双绿 + 词表

**要做什么：** 阶段 2 收尾：index.html 主体收敛为「fx imports + app.js import + ui 各模块 imports + 页签分发器 + 启动 IIFE + init\* 调用」；审计全部结构钉（JS 与 pytest）重指向完备；`node --test` + pytest 双绿；真浏览器冒烟；CONTEXT.md 词表补充；中文提交 + CHANGELOG。

**被谁阻塞：** 01-19 全部

**状态：** 待实施

## 检查表

- [ ] index.html 主体瘦身：核对 import 段（18 fx + app.js + 17 ui 模块）+ 页签分发器 + 启动 IIFE（init）+ init\* 调用段；目标主体 ~150 行；**运行 git diff --stat 前后行数对比**（应在预期内）
- [ ] 结构钉全盘点（grep tests/js + tests/ 中引用 index.html 的断言）：确认重指向新模块文件、无哑断言（断言目标文件存在）
- [ ] fx-guard DOMAINS 表核对：本阶段新增 fx 名（truncate / fmtSeconds / fmtClock / fmtDuration / decisionItem / archiveItem 等——按实际迁移）全部登记；ui 模块名不进 DOMAINS（DOMAINS 只管 fx 纯函数单源）
- [ ] 全量回归：`node --test "tests/js/*.test.mjs"`（基线 434 → 按新增单测计数）+ `pytest` 全绿
- [ ] diag.mjs 零 EXC；smoke.mjs 11/11 全绿
- [ ] 每 tab 实况探针（或按可用探针脚本汇总）：8 tab 渲染一把过
- [ ] CONTEXT.md「前端纯函数单源」bullet 更新：增补「DOM 胶水单源 = static/js/ui/*.js（阶段 2）」与 index.html 主体角色
- [ ] 中文提交 + CHANGELOG 记录（阶段 2 完成）

## 风险点

- 阶段 2 全程「纯搬家」；若收尾发现某票引入的行为漂移，回滚该票（git revert）而非带病收尾。
- index.html 行数验收：预期 9046 → ~600-800（含 markup + head + host）；host 脚本主体 ~150 行。
