# 03 — 图片文件上传走视觉描述

**要做什么：** 步骤 1 文件上传支持图片（.png / .jpg / .jpeg / .bmp / .webp）：extraction.extract_file 加图片分支（读字节 + mime 判定 → describe_image_cached → 描述文本作为题面上下文，与 PDF 图注同格式）；webapp /api/extract 照常透传；前端 accept 加图片类型；无 key 时图片上传报可操作中文提示（配置入口）。

**被谁阻塞：** vision-eyes/01（视觉通道）。

**状态：** resolved

- [ ] extract_file 图片分支：mime 判定、读字节、描述、输出图注文本（格式与 PDF 图注一致）
- [ ] 未配 key：图片上传返回可操作中文提示（引导设置页），不崩
- [ ] webapp /api/extract 透传（路由薄壳，形状不变）；前端 accept 加图片类型
- [ ] 测试：假视觉图片上传 / 无 key 提示 / 非法类型照旧报错
- [ ] 全量测试通过
