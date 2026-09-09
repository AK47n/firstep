# 03 — 图片文件上传走视觉描述

**要做什么：** 步骤 1 文件上传支持图片（.png / .jpg / .jpeg / .bmp / .webp）：extraction.extract_file 加图片分支（读字节 + mime 判定 → describe_image_cached → 描述文本作为题面上下文，与 PDF 图注同格式）；webapp /api/extract 照常透传；前端 accept 加图片类型；无 key 时图片上传报可操作中文提示（配置入口）。

**被谁阻塞：** vision-eyes/01（视觉通道）。

**状态：** resolved

- [x] 图片上传链路：mime 判定、读字节、描述、返回文本——实现形态 = 独立 `extract_image` + `webapp` 按后缀分派，返回**裸描述**（原「extract_file 图片分支 + 图注包装」口径已修订；图注包装只走 `pdf_image_notes`）。
- [x] 未配 key：图片上传返回可操作中文提示（引导设置页），不崩
- [ ] webapp /api/extract 透传（路由薄壳，形状不变）；前端 accept 加图片类型
- [ ] 测试：假视觉图片上传 / 无 key 提示 / 非法类型照旧报错
- [ ] 全量测试通过

## 验收口径修订（2026-09-09 在途盘点）

- 图片链路实现为独立 `extract_image` + webapp 按后缀分派，返回裸描述；`[示意图N：…]` 图注包装只属于 PDF 路径（`pdf_image_notes`）。

