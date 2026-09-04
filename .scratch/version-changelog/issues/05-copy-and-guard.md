# 05 — 文案联动与中文守门收尾

**要做什么：** 全仓库口径与「版本更新记录」一致：
新手指引（fx/guide.js）导航介绍把「更新记录」从「资料管理」组移除、指南组介绍
补上它、一句话导语同步；CONTEXT.md 补一笔版本记录机制（CHANGELOG.md 草稿 →
VERSIONS.md 定稿）；tests/test_repo_language.py 扩展 VERSIONS.md 中文守门
（每条 `- ` 条目 ≥4 个中文字符，文件缺失即红）。

**被谁阻塞：** 04（文案描述最终形态的栏目）。

**状态：** ready-for-agent

- [ ] guide.js：资料管理组列表去掉「更新记录」，指南组介绍 + 一句话导语同步
- [ ] CONTEXT.md 补版本记录机制一行（或所在词条更新）
- [ ] test_repo_language.py 增 VERSIONS.md 中文守门并全绿
- [ ] 全量测试套件绿
