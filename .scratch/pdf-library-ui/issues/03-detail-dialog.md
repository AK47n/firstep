# 03 — 轻量详情弹窗

**要做什么：** 每行「详情」打开的轻量弹窗：完整路径 / 批次 chip / 目录 /
大小 / 修改时间 / **页数**（打开时按 `GET /api/pdfs/{rel_path}/pages` 懒取
一次并 memo，加载中 / 成功 / 「无法读取」三态）+ 「打开」「复制相对路径」
按钮（`navigator.clipboard.writeText`，失败降级「复制失败，请手动复制」）；
损坏 / 重复 ⚠ 标注位为 04 预留。

**被谁阻塞：** 01（页数端点）

**状态：** resolved

- [x] `pdfDetailHTML` 纯函数渲染弹窗内容（元数据段 + 操作段：路径/批次 chip/
      目录/大小/mtime/页数三态 + 打开 PDF/复制相对路径按钮 + 反馈槽），
      遮罩与关闭复用 `.ref-files-overlay` / `.ref-files-close` 先例
- [x] 页数懒取：`pdfPagesUrl` + `loadPdfPages`（单 Map promise memo：同一
      rel_path 零重复请求、并发去重、never-reject；400 确定性损坏落缓存，
      网络/500 不落缓存可重试）→ `showPdfDetail` 落盘三态
- [x] 「复制相对路径」：`copyPdfPath`（navigator.clipboard.writeText）→
      「已复制相对路径」/「复制失败，请手动复制」；复制原始 rel_path，
      打开用 pdfFileUrl（逐段编码）——两件事分开
- [x] 弹窗关闭：× / 遮罩点击 / Esc（对偶 showReferenceDetail）；行内
      `[data-pdf-detail]` 委托接线（数据透传，零重复请求）
- [x] tests/js：pdfEncodedPath / pdfPagesUrl（逐段编码）+ pdfPagesText 三态 +
      pdfDetailHTML 子串断言（路径/批次 chip/大小/mtime/页数占位/两按钮/转义）
- [x] 冒烟：TB6612FNG 手册详情页数成功；0 字节临时文件（素材库现无损坏文件，
      由脚本写入/清理，writeFileSync 在 try 内 + smokeBatch 空防御）→
      「无法读取」三态；×/Esc/**遮罩点击**关闭；复制反馈（28 项 PASS）
- [x] 全量 tests/js 355 绿（350 + 5）

**评审（双轴）：** Standards 无硬违反。按下述修复：
- ① 提取 `pdfEncodedPath(relPath)` 公共编码助手——pdfFileUrl / pdfPagesUrl
  字节级重复（逐段 encodeURIComponent 的微妙性易踩坑）；
- ② `pdfPagePending` 双 Map 冗余 → 单 Map「永不 reject 的 promise」同时达成
  memo + 并发去重；`handle()` 抛错附 `err.status`（400 确定性损坏落缓存 /
  网络·500 不落缓存可重试）；
- ③ `.pdf-detail-body`（无 CSS 规则）→ 复用 `.ref-detail-scroll`；
  `.pdf-detail-actions` 内联 style → CSS 类；
- ④ `smoke writeFileSync` 移入 try + smokeBatch 空防御 + 补遮罩点击冒烟；
- ⑤ 注释「remove 防悬挂引用」措辞更正为防御语义。
  保留判断句：number|"error" 哨兵（内联三态为工单要求，不引常量）；
  网络错误文案不归因（保持 spec「无法读取」字面）。
**Spec 忠实：** 无 creep（新元素全部 pdf- 前缀，零新增全局 id）。

**实现说明：**
- 素材库现状核查（spec 撰写时的数据已变）：大矩形(视觉识别训练样本).pdf
  （k230资料/材料/，1225B 真 PDF）、简单图形的识别.pdf（8638B）、
  DL-43P尺寸图.pdf（9618B）——三份原 0 字节损坏文件**均已修复为正常 PDF**，
  当前库无 0 字节文件（git status 干净 = 文件在 HEAD 即如此）；疑似重复组
  需 04 前重扫确认。corrup 态验证改走临时 0 字节文件链路。
