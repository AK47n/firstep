# 04 — 预览图片显示（前端）

**要做什么：** 让 Markdown 预览弹窗里显示手册图片：`fx/md.js` 新增纯函数
`mdImageUrl(mdRelPath, src)`（http(s) 外链透传、相对路径按 .md 所在目录归一），
`ui/md.js` 预览渲染改传 `imageUrl` 回调；带 JS 测试；
彩屏篇（0-96-color-screen）预览中 gif 可见、位置在正文对应段落处。

**被谁阻塞：** 03（图片资源端点）。

**状态：** resolved

**结论：** 2026-09 完成。`fx/md.js` 新增 `mdAssetImageUrl`（评审整改：命名与 ui/codeeditor.js 本地 mdImageUrl 区分；`./` 前缀归一不产出 `/./` 段；批次根/子目录 md 两义说明入 spec）；`ui/md.js` 预览传 imageUrl 回调（markdownPreviewHTML 与 code-viewer 同管线，CSS 已有 img{max-width:100%}）。JS 测试 22 通过（含 ./ 归一、外链透传、空 src、批次根 md）。服务端数据链路已验（彩屏篇引用 img1.gif 在盘上、资产端点 200）；**浏览器端到端（彩屏篇预览显示 gif）待用户刷新后人工核验**。

- [x] `mdAssetImageUrl`：相对路径 → `md 所在目录 + "/" + src`；http(s) → 原样；
      空 src → 空串（fx 侧 `isSafeImageSrc` 已拒 `../` 越界与绝对路径，回调不复判）。
- [x] `ui/md.js`：`renderMdBlocks(content, m)` 传 `{ imageUrl: (src) => mdAssetImageUrl(m.rel_path, src) }`。
- [x] `tests/js/md-library.test.mjs` 覆盖：相对归一（批次根目录拼接）、外链透传、空 src、
      `./` 前缀、批次根 md。
- [ ] 浏览器验证：彩屏篇预览能显示 gif；无图手册（sht30）无异常。（待人工刷新核验）
