# 04 — 页脚识别兼容 pypdf 逐字符打散（2026D/H 只显示前 2 页修复）

**要做什么：** 用户报「2026H 题在生成题面 pdf 的时候只生成了前 2 页，之前
其他题目曾经出现过这个问题解决了现在又来了」。2026H（与 2026D，同为
微信 rar 来源的官方赛区赛 PDF，4 页）页图预览只出前 2 页：`_page_footer`
用 pypdf 逐行匹配页脚正则，而这两个 PDF 的文本层被 pypdf **逐字符打散成行**
（'D' / ' ' / '-' 各占一行）→ 整行正则永不命中 → 无页脚 → `locate_topic_pages_full`
回退「命中页起 2 页」span。2026C 同款 PDF 却正常（pypdf 对它的页脚给出
规整独立行「C - 1 / 4」）。

**被谁阻塞：** 无——topic-pdf-viewer/02（页脚总页数扩展）的后续修复。

**状态：** resolved

- [x] `_page_footer` 提取改 **PyMuPDF（fitz）优先**：fitz 对同页给出规整的
      「D - 1 / 4」独立行（诊断实测），整行正则直接命中；PyMuPDF 缺失 /
      打开失败回退 pypdf（既有行为与测试替身模型不变——extraction.py 的
      _render_page_png 已是 fitz，同款局部 import 风格）
- [x] 测试（RED→GREEN）：fitz 窗口打散页脚场景（pypdf 假件打散行 + fitz
      假件规整行 → (1,4)）、fitz 缺失回退 pypdf（规整行命中 / 打散行 None 与
      修复前一致）；既有 4 个定位/full 测试不变
- [x] 真机验证：全库 15 题 _page_footer 全部识别（2026D/H (1,4)、2026A/B/G
      (1,3)，后三者此前也只显示 2 页）；curl /pages 2026H/D/C [1,2,3,4]、
      2021F [123..126]、2024H [232..234] 全部完整；页面 CDP 探针
      probe-pdf-pages.mjs SMOKE ALL PASS（2026H imgs=4）
- [x] 全量 pytest 绿（2413）

**评审与收尾（code-review 双轴）：** 直接按 bug 修复流程实施（诊断 → 根因
pypdf 提取打散 vs fitz 规整 → fitz 优先 + 回退 → TDD → 真机验证）。旧题
（2019A/2021F/2024H 汇总 PDF）页脚识别值与此前逐项一致，无回归。留痕：
pypdf 对部分官方 PDF 的文本层提取存在逐字符拆行缺陷，凡「整行正则匹配
文本层」的既有逻辑（页脚 / 图注 / 行聚类）都可能在遇到此类 PDF 时静默
失效——诊断时先评估提取源（pypdf vs fitz）再怀疑正则。
