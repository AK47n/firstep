# 06 — 赛题文本抽取（PDF/Word）

**What to build:** 用户上传 PDF 或 Word 赛题文件，工具在本地抽取文字（不联网）；纯文本输入直接可用，无需抽取。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] PDF 与 .docx 本地解析为纯文本
- [ ] 纯文本输入直通，不重复抽取
- [ ] 抽取失败（损坏 / 加密文件）给出明确错误信息而非崩溃
- [ ] 样例文件测试覆盖三种输入（PDF / docx / 纯文本）
