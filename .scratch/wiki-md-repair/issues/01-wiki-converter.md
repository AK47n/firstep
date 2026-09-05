# 01 — wiki 转换器域模块 + 爬虫接入（单页验证）

**要做什么：** 让 `fetch_wiki.py` 能产出可读的 wiki 手册页：新增带单元测试的转换器域模块
`src/contest_generator/wiki_md.py`（Shiki 代码逐行还原 + `<main>` 按原页顺序转正规 Markdown），
重构 `fetch_wiki.py` 接入；用 `--only` 重抓 sht30 / mpu6050 / 0-96-color-screen 三页，
产物经质量抽查看起来像真文档（正文/代码/表格式排布，无 token 逐行、无行号残留）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09 完成并提交。code-review 双轴：Standards 无硬性违反（采纳：元信息谓词提取 `_in_meta_ctx`、`code_block_count` 单源、`_ListCtx` 命名、`pans`→`pan_links` 统一、`<br/>` pre 路径修正）；Spec 刑抓到两个真 bug 已整改——①行号 wrapper 数字经 prose 路径泄漏（`_in_num_wrapper` 隔离 + 回归测试），②custom-block 落盘后 `_cur` 未清空致正文注入后续段（清空 + 回归测试）；另 `_` 移出转义集（词内下划线按字面）、img 相对 src 归一补 `/`、`\u200b` pre 路径剥离。三页产物与 live 页面经真实管线逐 fence 比对一致（316/34/21 行）。

- [x] `wiki_md.py` 实现 `shiki_lines()`：以 `<span class="line">` 为锚逐行还原代码，
      行号 wrapper（`line-numbers-wrapper`）不进代码；跨行 token、空行、多行注释正确。
- [x] `wiki_md.py` 实现 `parse_main(main_html, slug)`：h2-h6 标题（剥 header-anchor 锚点与 `\u200b`）、
      段落、粗体/斜体/删除线/行内代码/链接、`<ol start>` 编号列表（连续 li 合并为一块）、
      custom-block 转 `> **标题**：正文`、SSR 内嵌图片按出现顺序编号
      `![alt](images/<slug>/imgN.png)`、丢弃 `<!---->` 注释。
- [x] `wiki_md.build_markdown(slug, cat, url, title, md_body, img_urls, pan_links)` 组装单篇
      （`# slug` + 元数据 + 正文 + `## 百度网盘下载`），图片数/代码块数按实际计数。
- [x] `fetch_wiki.py` 删除 `clean_text`/`extract_codes`，接入 `wiki_md`；图片下载保留
      （相对路径转绝对；已存在跳过）；`--only`/`--limit`/`--force` 语义不变。
- [x] `tests/test_wiki_md.py` 覆盖：Shiki 行还原、行号隔离、标题锚点/`\u200b` 剥离、
      链接/粗体/行内代码、列表 start 编号与合并、custom-block、img 编号去重、注释丢弃、
      围栏语言、段落空行分隔、`<stdio.h>` 尖括号代码行。
- [x] `--only` 重抓 3 页成功；sht30 页代码围栏 [316, 34, 21] 行（与 live 页面经真实管线
      逐行比对一致）、无孤立 token 行、无 `\u200b`、标题层级正确（人工过目产物）。
