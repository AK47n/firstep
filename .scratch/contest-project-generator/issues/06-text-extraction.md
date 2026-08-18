# 06 — 赛题文本抽取（PDF/Word）

**What to build:** 用户上传 PDF 或 Word 赛题文件，工具在本地抽取文字（不联网）；纯文本输入直接可用，无需抽取。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] PDF 与 .docx 本地解析为纯文本
- [x] 纯文本输入直通，不重复抽取
- [x] 抽取失败（损坏 / 加密文件）给出明确错误信息而非崩溃
- [x] 样例文件测试覆盖三种输入（PDF / docx / 纯文本）

## Comments

- 2026-08-05: 工单 06 完成。`extraction.py`：`extract_text` 纯文本直通（不做任何文件操作）；`extract_file` 按后缀分发——.pdf 用 pypdf（加密 / 损坏 / 扫描件都抛明确错误，绝不静默给空文）、.docx 用标准库 zip + XML（段落保留换行，TOC/PAGE 域指令不混入正文）、.txt/.md 直读；不支持的类型（如旧版二进制 .doc）明确报错。依赖新增 `pypdf>=6`（pyproject.toml）。样例 PDF/docx 由 `tests/fakes.py` 构造器在测试现场生成，不提交二进制 fixture；14 个测试覆盖三种输入 + 全部失败路径。注意：提交时工作区另有工单 04 的进行中未提交工作（llm.py / config.py / test_llm.py / test_config.py / test_selection.py 及 fakes.py 中的 FakeTransport），本次提交已隔离，只含本工单文件。
