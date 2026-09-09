# 05 — 文案联动与中文守门收尾

**要做什么：** 全仓库口径与「版本更新记录」一致：
新手指引（fx/guide.js）导航介绍把「更新记录」从「资料管理」组移除、指南组介绍
补上它、一句话导语同步；CONTEXT.md 补一笔版本记录机制（CHANGELOG.md 草稿 →
VERSIONS.md 定稿）；tests/test_repo_language.py 扩展 VERSIONS.md 中文守门
（每条 `- ` 条目 ≥4 个中文字符，文件缺失即红）。

**被谁阻塞：** 04（文案描述最终形态的栏目）。

**状态：** resolved

**完成情况：**
- [x] guide.js：资料管理组列表去掉「更新记录」，指南组介绍 + 一句话导语同步
- [x] CONTEXT.md 补版本更新记录机制词条（草稿区 → 定稿区 + 前端 + 发布仪式）
- [x] test_repo_language.py 增 VERSIONS.md 中文守门并全绿（含 helper 纯函数单测）
- [x] 全量测试套件绿

**审查结论（code-review 双轴）与整改：**
- 标准轴：无硬违规。整改：nav 键三份拷贝 → 新建 nav-tabs-shared.mjs 单源
  （guide.test / guide-refs 改 import；nav-tabs-guard 增加深浅一致性深比较锁）；
  中文守门注释状态机从惰性 → 抽 _version_entry_lines 纯函数 + 单元测试
  （多行注释区间 + 行内注释剥离两态真触发）；标签集口径统一（四处均列
  新增/改进/修复/性能：guide.js / index.html title / h2 / VERSIONS.md / CONTEXT）。
- 规格轴：主体达标；域名术语统一为「版本更新记录」；守门行内注释洞已修。
- 此前被 04 评审指出的「无操作顺序重排」已随单源化消解（顺序含义只在
  nav-tabs-shared 一处表达）。

- [x] guide.js：资料管理组列表去掉「更新记录」，指南组介绍 + 一句话导语同步
- [x] CONTEXT.md 补版本记录机制一行（或所在词条更新）
- [x] test_repo_language.py 增 VERSIONS.md 中文守门并全绿
- [x] 全量测试套件绿


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
