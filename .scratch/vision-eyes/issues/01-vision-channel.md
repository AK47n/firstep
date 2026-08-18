# 01 — 视觉通道 vision.py（GLM-4V-Flash）

**要做什么：** 新增 vision.py：`describe_image(image_bytes, mime, prompt)` 调智谱 GLM-4V-Flash（OpenAI 兼容 chat/completions + base64 image_url），标准库 urllib + 可注入传输接缝（照 llm.py 先例）、网络重试、`describe_image_cached`（进程内 sha256 缓存）、VisionError 登记 errors.py；AppConfig 加 vision_base_url / vision_api_key / vision_model（无 key = 关闭）；单元测试用假传输。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [ ] vision.py：describe_image 请求体形状正确（model / content = text + image_url data URL），返回描述文本
- [ ] 传输接缝可注入（假件测试：请求形状 / 网络错误重试 / 非 200 / 解析失败）
- [ ] describe_image_cached：同图（sha256）重复调用不重发请求
- [ ] VisionError 登记 errors.py（error_to_http 表内，文案中文）
- [ ] AppConfig 三个新字段（缺省 = 关闭，旧 config.json 兼容）；无 key 时调用方走"未启用"分支
- [ ] 全量测试通过
