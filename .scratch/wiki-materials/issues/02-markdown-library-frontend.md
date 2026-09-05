# 02 — Markdown 资料前端 tab（导航 + 列表 + 页内渲染预览）

**要做什么：** 「PDF 资料库」旁边新增「Markdown 资料」tab：素材根全部 .md 的浏览入口——过滤/排序/统计/批次 chips 与 PDF tab 同款交互；点「预览」在弹窗内渲染 Markdown（代码块高亮，复用 code-viewer 的 markdown 渲染管线）——用户不离开工具就能读 70 篇地猛星移植手册。

**被谁阻塞：** 01 — Markdown 资料库后端（需要 /api/materials-md 两端点）。

**状态：** resolved

**结论：** 2026-09-05 完成并提交（acecec55 前置提交）。fx/md.js + ui/md.js + nav 11 tab（nav-tabs-guard/shared 同步）；JS 全量 1351 + Python 全量 3315 通过。浏览器端到端待服务重启后人工核验（运行中的 8000 端口服务是旧代码，重启即生效）。

- [ ] `fx/md.js` 纯函数组（对偶 fx/pdf.js）：`mdFilterEntries`（文件名/批次/目录/路径四合一子串过滤）/ `mdSortEntries`（文件名/批次/目录/大小/修改时间 ± 方向）/ `mdStats` + `mdStatsText` / `mdChipRowHTML`（批次 chips）/ `mdRowHTML`（文件名 + 批次 chip + 目录 + 大小 + 修改时间 + 预览/复制路径钮）/ `mdEncodedPath`（逐段编码）/ 预览 URL 构造
- [ ] `ui/md.js` DOM 胶水（对偶 ui/pdf.js）：加载/过滤/排序/统计渲染、批次 chips 事件、预览弹窗（ref-files-overlay 遮罩 + Esc/遮罩点击关闭）、全文懒取 memo（按 rel_path，400 落缓存可重试、网络/500 不缓存）、复制相对路径
- [ ] 预览渲染：`parseMarkdownBlocks` + `markdownPreviewHTML`（fx/markdown.js 单源，与 code-viewer md 预览同管线；代码块语言分发/高亮沿用既有；opts.imageUrl 置空——wiki 正文无图）
- [ ] index.html：nav 按钮「Markdown 资料」（data-tab，紧挨 pdf）+ `#tab-md` section（lib-toolbar：搜索框/排序下拉/方向钮/刷新/清空 + 批次 chips 行 + 统计条 + 表格 + 错误槽），CSS 对齐 tab-pdf 既有表格样式
- [ ] 人工验收：`lckfb-地猛星移植手册/` 批次可见、70 篇 + 2 篇索引全在；过滤「mpu6050」命中 1 篇；预览弹窗渲染正文 + 代码块高亮；刷新/清空正常
