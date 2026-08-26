# 05 — 视觉与环境收尾 + 全量回归

**要做什么：** tab-pdf 与全站观感对齐的收尾：空态（无数据 / 过滤无结果）/
加载态 / 错误态文案与视觉和生成页、模块库页、参考文件库页一致；按钮 /
徽章 / 行 hover 令牌核对；CONTEXT.md 补「PDF 资料库」词表行；冒烟清单全绿
（含 id 唯一检查）；全量回归（tests/js / pytest / 冒烟）。

**被谁阻塞：** 02、03、04

**状态：** resolved

- [x] 空态：库空（「素材库中暂无 PDF」+ 放入提示）/ 过滤无结果（「没有匹配
      的 PDF 文件」+ 换关键词提示，与库空空态区分——「清空过滤」语义而非
      「暂无 PDF」）已由 02 实现；本轮冒烟补「过滤无结果空态 + 清空恢复」
      断言（对偶参考库页空态文案）
- [x] 加载态 / 错误态：列表加载中「正在读取 PDF 资料库…」⏳ 占位 +
      /api/pdfs 失败中文提示（pdf-msg）已由 02 实现
- [x] 令牌核对：表格/徽章/按钮/chips/统计条全部复用 `.lib-table` /
      `.lib-toolbar` / `.lib-chip` / `.lib-stats` / `.badge` 系与既有 CSS 变量
      ——04 评审硬违反（.pdf-dup 硬编码色）已在 04 修完（→ var(--warn) 族）；
      行 hover、焦点态与参考库页一致（lib 令牌）
- [x] DOM id 唯一：新增 `pdf-*` id 在页面无重复（冒烟检查项）
- [x] CONTEXT.md 词表补「PDF 资料库」行：素材根 sources/materials 全量 PDF
      直通入口；批次 = 第一级目录、批次内子目录 = 二级目录；列表字段
      rel_path/name/batch/size_bytes/mtime；页数按需 PyMuPDF 单文件
      （/api/pdfs/{rel_path}/pages）；数据健康判据（0 字节 = 损坏、
      同名同大小 >0 = 疑似重复，提示语义只警示不删）
- [x] 冒烟清单全绿（38 项：28（02/03 存量）+ 8（04 数据健康）+ 1（05 空态）
      + id 唯一检查）+ 截屏存档（shot-04-full / dup-filtered / detail）
- [x] 全量回归：tests/js 362 绿、pytest 2402 绿（04 后无后端改动——04 提交
      全量已跑）、冒烟 38 项全绿

**提交**：04 提交 412455d + 自动 CHANGELOG cfedf04；本轮提交 CONTEXT.md 词表行
+ 05 冒烟空态 + 工单文件。
