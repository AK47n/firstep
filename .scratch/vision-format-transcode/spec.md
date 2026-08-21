# PDF 内嵌图自动转码（BMP / JPEG2000 → PNG）

## 问题陈述

DeepSeek 视觉仅支持 JPEG/PNG/GIF/WebP。firstep 赛题库实测（vision-deepseek-native/01 的 pdf_image_scan.py）：261 页长 PDF 的 472 张嵌入图中，JPEG2000（.jp2）12 张、BMP 0 张——但用户可能上传含 BMP 的任意 PDF。现状（vision-deepseek-native/01 决策）：PDF 内嵌 BMP 发送前静默跳过；JPEG2000 走 `_image_mime` 未知后缀兜底 `image/png` 直发 → DeepSeek 按 PNG 解码 JPEG2000 **必然失败** → 单张静默跳过。结果：这些图的图注缺失，且用户无感知、无提示。切智谱 GLM 救不了 JPEG2000（智谱同样不收 JPEG2000；且兜底声明 PNG 与内容不符，任何服务商都解码失败）。用户确认方案：**根治——提取时自动转格式**（Pillow 转 PNG），DeepSeek 全部能识别，无需切换服务商。

## 方案

1. `pyproject.toml` dependencies 加 `pillow>=11`（运行时依赖；Pillow wheel 自带 OpenJPEG，支持 JPEG2000 解码）。
2. `extraction.py`：
   - 新增 `_transcode_to_png(data: bytes) -> bytes | None`：PIL 打开 → `convert("RGB")` → PNG 字节；**lazy import PIL**（函数内 import + 全异常兜底 None）——老环境未装 pillow 时行为退化为「跳过」，与现状一致，绝不崩启动。
   - `pdf_image_notes`：替换「.bmp 发送前跳过」（工单 vision-deepseek-native/01 的行为，本工单升级为转码）——后缀 ∉ DeepSeek 支持集（.jpg/.jpeg/.png/.gif/.webp）→ 转码；成功 → 以转换后字节 + `image/png` 发送；失败 → `skipped += 1` 降级（既有尾部标注「另有 N 张图跳过」已会提示）。
   - 直传图片（`extract_image`）的 .bmp 400 拦截**不变**（已有可操作中文提示，用户主路径是 PDF；避免范围膨胀）。
3. 测试（tests/test_extraction.py，假件体系 `_FakeImage/_FakePage/_FakeReader` + monkeypatch）：
   - **改** `testpdf_image_notes_skips_bmp_embedded_images` → `..._transcodes_bmp...`：真 BMP 字节（PIL 生成）→ 断言转换后以 image/png 发送、PIL 还原为 PNG；红证：现实现 BMP 跳过 → calls 少一条 → 红。
   - **新增** JPEG2000 转码测试（PIL 生成 .jp2；Pillow 无 OpenJPEG 时 pytest.skip 防脆）：断言转换后发送、还原 PNG；红证：现实现兜底直发原 JP2 字节 → 还原 format=JPEG2000 → 红。
   - **新增** 转码失败降级测试：垃圾字节 + .bmp 后缀 → 跳过计尾部标注（现实现也过，保护新路径不崩）。

## 用户故事

1. 作为用户，上传含 BMP / JPEG2000 嵌入图的 PDF，图注不再缺失（自动转 PNG 后 DeepSeek 可识别）。
2. 作为用户，图注尾部仍能看到「另有 N 张图跳过」提示（转换失败才出现，属异常路径）。
3. 作为用户，未安装 pillow 的环境（老部署）不崩——视觉行为退化为跳过，安装后自动升级。
4. 作为用户，直传 .bmp 图片仍得到原有中文报错（转存 PNG/JPEG），语义不变。

## 实现决策

- **lazy import PIL**（不是顶部 import）：顶部 import 会让未装 pillow 的旧环境启动即崩（模块加载失败），lazy + 异常兜底让降级路径与现状逐字节一致。Pillow 已入 dependencies，正常安装后即生效。
- **后缀判定转码**：`.jpg/.jpeg/.png/.gif/.webp` 直发（pypdf 的 ImageFile.name 反映真实格式，扫描实测可靠）；其余（.bmp/.jp2/未知）转码。转换失败 → skip，兜底一切异常字节。
- **`convert("RGB")`**：PNG 编码不支持 P/CMYK 等模式；RGBA 转 RGB 丢 alpha 对电路图影响可忽略。
- **不引入新错误文案**：复用 `_join_notes` 既有「另有 N 张图跳过：超大或描述失败」。
- **直传 BMP 400 拦截保留**（范围外：直传自动转码不在本工单）。
- 依赖仅新增 pillow；requires-python >=3.13 与 Pillow 11+ 兼容。

## 测试决策

红证先行（BMP 行为变更 + JPEG2000 新路径），假件体系无需真实 PDF；JPEG2000 生成用 PIL（环境无 OpenJPEG 时 pytest.skip，防脆）；全量 pytest + `mypy src` 收尾。

## 范围外

- 直传图片（.bmp 上传）自动转码——维持 400 提示转存。
- 图注跳过文案的细分（「超大或描述失败」不拆「格式不支持」）。
- 服务端 / 其它格式（TIFF/HEIC 等）——PDF 提取链实测仅 JPEG/PNG/JPEG2000。
