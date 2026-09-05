# spec：素材批次 Markdown 手册可读性修复（地猛星 70 篇）

前置：`.scratch/wiki-materials/spec.md`（素材批次浏览入口 + 4 模块提炼，已全部 resolve）。
本 spec 修复该批次**文件内容不可读**的缺陷——用户打开/预览手册时看到"一个词一行"的机器噪声。

## 问题陈述

「Markdown 资料」入口已能浏览/预览素材批次的 70 篇地猛星移植手册，但**内容本身是爬虫损坏产物**：

- 代码块里每个 token 独占一行（`#include` / `"bsp_sht30.h"` 分两行），间距错乱；
- 正文里残留行号 gutter（`304` `305`…每个数字一行）、零宽字符 `\u200b`；
- 正文中的代码被扁平化且与代码块章节两处重复；
- 用户无论「打开原文」还是「预览」，看到的都不像文档，起不到查资料的作用。

## 根因（已验证）

`fetch_wiki.py` 的 `extract_codes()` 有一行 `re.sub(r"</span>", "\n", block)`：wiki 页面（VitePress + Shiki）
把每个代码 token 包成 `<span>`，这行把**每个 token 的闭合标签都换成换行** → "一个词一行"。
`clean_text()` 则把 `<span class="line-number">N</span><br>` 行号列也排进了正文。
渲染管线（`fx/markdown.js`）本身无缺陷——它忠实渲染了损坏的内容。

wiki 页代码块真实结构（实测抓包确认）：

```html
<div class="language-c line-numbers-mode">
  <span class="lang">c</span>
  <pre class="shiki ..."><code>
    <span class="line"><span style="--shiki-light:...">/*</span></span>
    <span class="line"><span style="..."> * 立创开发板…</span></span>
    ...
  </code></pre>
  <div class="line-numbers-wrapper"><span class="line-number">1</span><br>…</div>
</div>
```

- 每行源码 = 一个 `<span class="line">`（内部若干 `<span style>` token）；
- 行号是 `<pre>` 的**兄弟节点** `line-numbers-wrapper`，只要锚定 `<span class="line">` 就天然隔离；
- 标题含 `<a class="header-anchor">` 锚点 + `\u200b` 需要剥掉；正文段落含 `<strong>`/`<a>`/`<code>`/`<span style>`；
- 有序列表渲染为 `<ol start="5"><li>…</li></ol>`（**真实序号在 start 属性**，且每个 li 独自一个 ol）；
- 提示块 = `<div class="warning custom-block">`（标题在 `p.custom-block-title` 内）；
- SSR 内嵌图片仅部分页面有（颜色屏 gif 等）；sht30 的「模块原理图」等是**客户端懒加载组件**，SSR HTML 里是 `<!---->`，抓不到 —— 已知局限。

## 方案

1. **重写转换器**：新域模块 `src/contest_generator/wiki_md.py`（HTML→Markdown 纯函数，无网络/无文件依赖），
   以 `html.parser` 一次性遍历 `<main>` 内容区，按原页顺序产出正规 Markdown：
   章节标题（h2-h6，剥锚点/`\u200b`）、段落（块间空行）、粗体/斜体/删除线/行内代码/链接、
   有序列表（读 `start` 属性编号、连续 li 合并为一块）、无序列表、提示块（转 `> **标题**：正文`）、
   代码围栏（`shiki_lines()` 以 `<span class="line">` 为锚逐行还原，语言取 `span.lang`）、
   内嵌图片（`![alt](images/<slug>/imgN.png)`，按出现顺序编号去重）。
   产出文本统一剥 `\u200b`、压缩 3+ 连续空行。
2. **重抓数据**：`fetch_wiki.py` 接新转换器，`--force` 全量重抓 70 篇（重建 `模块索引.md`/`网盘索引.md`；图片 + `images/<slug>/` 落地，已存在则跳过），
   人工抽查 + 全量质量扫描（无 token 逐行 / 无行号残留 / 无 `\u200b` / 代码围栏行数非零 / 文档结构计数）。
3. **预览图片**：新端点 `/api/materials-md-assets/{rel_path}`（路径安全 + 存在性 + 大小上限，按扩展名回 Content-Type）；
   前端预览 `markdownPreviewHTML` 传 `imageUrl` 回调（`fx/md.js mdImageUrl`：外链 http(s) 透传、相对路径按所在 .md 目录归一），
   图片在页内预览中显示（CSS 已有 `img{max-width:100%}`，无需改）。
4. 保留「打开原文」+「预览」两个按钮不动（内容修好后两边都干净）。

## 用户故事

1. 作为参赛者，我打开任意一篇地猛星手册的预览，能看到按 wiki 原页顺序排布的正文与代码 —— 阅读像页面的真文档。
2. 作为参赛者，我复制预览/原文里的代码块，得到的是逐行完整、缩进正确的 C 源码 —— 可直接拿去对照移植，不用手工还原。
3. 作为参赛者，我在手册里看到章节标题树、加粗关键词、可点击的采购/网盘链接 —— 结构与 wiki 页面一致。
4. 作为参赛者，手册中带图的模块（如 0-96 彩屏 gif）在预览中能看到图片 —— 图随文走，位置正确。
5. 作为参赛者，一个章节如果 wiki 本身是空的（如 sht30 的「2、引脚选择」为客户端渲染），手册同样保持空 —— 不编造内容。
6. 作为仓库维护者，转换器是带单元测试的域模块，任何依赖的 HTML 形态回归都能被发现 —— 不用再靠肉眼扫 70 个文件。
7. 作为仓库维护者，`模块索引.md`/`网盘索引.md` 与 70 篇正文同步重建 —— 索引计数与页面一致。
8. 作为仓库维护者，之后要做素材批次内容更新/重抓时，重复运行脚本即可 —— 幂等（已存在的图片跳过，`--force` 重抓 md）。

## 实现决策

- 新域模块 `src/contest_generator/wiki_md.py`（对齐仓库"域名模块 + 单测"惯例，而非把逻辑留在 scratch 脚本里）：
  - `shiki_lines(raw)`：`<pre><code>` 内部原始 HTML → 逐行代码文本列表；
  - `parse_main(main_html, slug)`：`<main>` HTML → (markdown 文本, 图片 URL 有序列表)；
  - `build_markdown(slug, cat, url, title, md_body, img_urls, pan_links)`：组装单篇手册（元数据头 + 正文 + 「百度网盘下载」小节）。
- `fetch_wiki.py` 重构：`clean_text`/`extract_codes` 删除，接入 `wiki_md`；图片下载逻辑保留（相对路径转绝对；
  已存在的图片文件跳过）；`--only`/`--limit`/`--force` 语义不变；`模块索引.md`/`网盘索引.md` 全量模式重建不变。
- 新格式单篇轮廓：`# slug` + 元数据列表（分类/来源/标题/代码块数/图片数）+ 正文（按原页顺序）+ `## 百度网盘下载`。
- 列表编号：连续 `<ol>`（每 li 一个 ol）合并为一个 markdown 列表块，编号取自 `<ol start>` 属性（`5.` `6.` `7.`），
  非列表块中断后重开。
- 提示块：`> **<标题>**：<正文>`（标题用页面自带的 `p.custom-block-title` 文本，如 WARNING/TIP/INFO）。
- 图片引用：相对路径 `images/<slug>/imgN.png`（基于批次根目录），与旧抓取同构；外链图片（http(s)）直接保留原 URL。
- 新图片端点 `GET /api/materials-md-assets/{rel_path:path}`：`md_library.resolve_md_asset()`（复用 `is_unsafe_path` +
  存在性校验 + 仅放行图片扩展名 + 16MB 上限，返回 Path），webapp 按扩展名回 Content-Type
  （png/jpg/jpeg/webp/gif/svg），非法/缺失/超限/非图片 → 400 中文文案（同 md 端点通道）。
- 前端：`fx/md.js` 新增 `mdAssetImageUrl(mdRelPath, src)`（http(s) 原样返回；否则按标准
  Markdown 语义「相对 .md 所在目录」归一，`./` 前缀剥除；`../` 越界由
  `fx/markdown.js isSafeImageSrc` 先拒，回调不复判。命名以 mdAsset 前缀区别于
  ui/codeeditor.js 的本地 mdImageUrl（/api/code/raw 预览图，签名/端点均不同））；
  `ui/md.js openMdPreview` 传 `{ imageUrl: (src) => mdAssetImageUrl(m.rel_path, src) }`。
  归一基准说明：wiki 手册约定 md 在批次根、图片在批次根 `images/` 下，此时
  「按 md 目录归一」与「按批次根归一」等价；子目录 md 按所在目录归一（标准语义）。
- 章节空（SSR 无内容）不编造：转换器忠实输出所见。

## 测试决策

- 组件/单元（新增 `tests/test_wiki_md.py`）：合成 HTML 夹具覆盖 —— Shiki 行还原（含行内多 token、
  空行、多行注释）、行号 wrapper 隔离（fixture 里塞 line-number 也不进代码）、标题锚点与 `\u200b` 剥离、
  链接/粗体/行内代码/删除线、`<ol start>` 编号与合并、custom-block 转引用、img 编号与去重、`<!---->` 丢弃、
  段落空行分隔、代码围栏语言。
- 组件/单元（`tests/test_md_library.py` + [md_library 资产]）：`resolve_md_asset` 路径安全（`../`/盘符/绝对路径拒绝）、
  缺失 400、超限 400、正常返回。
- 集成（`tests/test_webapp.py`）：`/api/materials-md-assets` 200 + Content-Type、非法路径 400、缺失 400。
- JS（`tests/js/md-library.test.mjs`）：`mdImageUrl` 相对路径归一、外链透传、空 src。
- 内容质量扫描（`.scratch/wiki-materials/scan_quality.py`，脚本非测试）：对 70 篇跑断言 —
  无 `\u200b`、无 `^<token>$` 孤立行（抽样正则）、`## ` 章节标题存在、代码围栏数 = 元数据计数、无行号纯数字行。
- 真实数据抽查：sht30 / mpu6050 / 0-96-color-screen 三篇重抓产物人工过目（转换正确性最终裁判）。

## 范围外

- 客户端懒加载图片（如 sht30「模块原理图」在 SSR HTML 里是 `<!---->`）：抓不到，不做 headless 渲染补图。
- 重抓后 `.scratch/wiki-materials/extract_inline.py` / `extract_code.py`（旧格式反解脚本）失效：已一次性消费完毕，
  后续模块提炼改为直接解析新格式的围栏（内容更干净），另开工单。
- 彩屏模块提炼、stm32 平台条目、其余 66 篇的模块化（上一 spec 范围外不变）。
- 预览样式美化（字体/间距微调）：CSS 已够用，不在本 spec。

## 追加：标题与分类中文化（2026-09，用户反馈「很多 markdown 的标题都是英文」）

扫描事实：正文 2~6 级标题全中文（607 个，零英文）；英文标题只三处——每篇顶部 `# slug`
（70/70）、`- 分类：sensor` 等分类码、模块索引的 `## sensor/screen/rf/control`。
中文名来源 = wiki 页面 h1（如「SHT30温湿度传感器」，转换器此前跳过），无需编造。

- **顶部标题**：`parse_main` 捕获页面 h1（剥锚点/`\u200b`）随返回值带出；`build_markdown` 顶部
  `# 中文名`（无 h1 回退 slug）；`- 标题：` 保留完整 `<title>` 记录源。
- **分类中文化**：`cat_label(cat)` 映射 sensor→传感器类 / screen→显示类 / rf→无线通信类 /
  control→控制类（wiki 自身四分类中文名）；`- 分类：` 与模块索引 `## ` 标题用映射（slug 仍在
  文件名与来源链接里，不丢英文码）。
- **列表中文标题**：`list_markdowns` 每条新增 `title`（首 8KB 内首个 `^# ` 标题；非本批产物
  回退文件名）；前端行渲染 = 中文标题（点击主行）+ 文件名小字第二行（muted），既有
  打开/预览/复制路径按钮不变。
- 重抓 70 篇；扫描器加断言：每篇 `^# `（H1）含中文。

## 补充说明

- 测试不受影响：现有测试用临时夹具建镜像，不读真实批次内容；重抓后文件数不变（70 页 + 2 索引）。
- wiki 当前可访问（HTTP 200，实测）；若重抓中途失败，脚本会重试 3 次并汇报失败清单（现状行为保留）。
- 70 篇重抓需 ~10 分钟，作为后台任务跑；`--force` 只重写 .md，图片已存在则跳过。
- **评审整改（code-review 双轴，2026-09）**：①「行号在 pre 兄弟节点天然隔离」只在 shiki_lines
  代码路径成立——`line-numbers-wrapper` 仍在 `<main>` 内，prose 路径必须显式隔离
  （`_in_num_wrapper` 跳过其数字/`<br>`），否则数字以空格连接序列泄漏进正文；
  ② custom-block 落盘引用块后必须清空 `_cur`（否则正文注入后续段落/列表项）；
  ③ 正文转义集不含 `_`（标识符词内下划线按 CommonMark 字面处理，转义污染原文）；
  ④ 图像相对 src 归一补 `/`；`\u200b` 在 pre 原始路径同样剥离。
  对应回归测试：行号 wrapper prose 隔离、custom-block 后接列表、del/em、块间空行。
