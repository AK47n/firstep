# 05 — 标题与分类中文化（转换器 + 重抓 70 篇）

**要做什么：** 让每篇手册的顶部标题是中文名（wiki 页面 h1，如「SHT30温湿度传感器」）、
分类词是中文（传感器类/显示类/无线通信类/控制类）：`wiki_md.parse_main` 捕获页面 h1
随返回值带出，`build_markdown` 顶部 `# 中文名`（无 h1 回退 slug）+ `cat_label(cat)` 映射
分类；`fetch_wiki.py` 接入后 `--force` 全量重抓 70 篇；`模块索引.md` 分类标题用中文映射；
扫描器加 H1 含中文断言。

**被谁阻塞：** 无——可立即开始（追加：标题与分类中文化 spec 节）。

**状态：** resolved

**结论：** 2026-09 完成并提交。parse_main 捕获页面 h1（剥锚点/\u200b）返回 (md, img_urls, page_title)；build_markdown 顶部 `# 中文名`（空回退 slug）+ `- 分类：{cat_label}`（sensor→传感器类/screen→显示类/rf→无线通信类/control→控制类）+ `- 标题：` 同中文名；fetch_wiki 无 h1 时取 `<title>` 去「 | 立创…」后缀；模块索引 `## ` 分类中文化。全量重抓 70 篇 0 失败；扫描 70/70（新增"首页标题非中文"断言）；抽查 70 篇 H1 全为正常中文名（16路舵机驱动模块/WS2812彩灯/…），零异常。

- [x] `parse_main` 返回 (md, img_urls, page_title)：捕获 `<h1>` 文本（剥锚点/`\u200b`；h1 仍在正文外）。
- [x] `build_markdown`：顶部 `# 中文标题`（无 h1 回退 slug）；`- 标题：` 保留完整 `<title>`；
      `- 分类：{cat_label(cat)}`；`cat_label` 映射 sensor/screen/rf/control → 传感器类/显示类/无线通信类/控制类（未知回退原码）。
- [x] `fetch_wiki.py`：parse_page 用 h1 或 `<title>` 去后缀作标题；模块索引 `## ` 用 cat_label。
- [x] `tests/test_wiki_md.py` 覆盖：h1 捕获（含锚点/`\u200b`）、build_markdown 中文标题 + 分类映射、无 h1 回退 slug。
- [x] 全量重抓 70 篇（0 失败）；质量扫描 70/70（新增：每篇 H1 含中文）；人工抽查 3 篇。
