# 视觉通道原生接入 DeepSeek（vision-deepseek-native）

## 问题陈述

DeepSeek 已于 2026-08 上线官方视觉模型（`deepseek-v4-flash-vision-exp`，OpenAI 兼容
`/chat/completions`，支持 JPEG/PNG/GIF/WebP，单图 token 计费封顶）。此前 firstep 的
「图 → 中文描述」视觉通道默认走智谱 GLM-4.6V-Flash 免费 API，用户需要**额外注册智谱
账号、单独配置第二套 key**（「给 DeepSeek 装眼睛」）。用户希望：已有 DeepSeek key 的
用户零额外配置即可获得视觉能力（PDF 嵌入示意图图注、图片文件直接识别）。

## 方案

- 视觉通道默认端点切到 DeepSeek 官方（base_url = `https://api.deepseek.com`，模型 =
  `deepseek-v4-flash-vision-exp`），请求协议（OpenAI 兼容 content 块数组 + base64
  image_url）两边完全一致，传输 / 重试 / 缓存 / 解析代码零改动。
- **key 复用**：视觉 key 留空时自动复用主 DeepSeek key（仅当视觉 base_url 为 DeepSeek
  官方端点时——用户改成自定义视觉服务（如智谱）仍须自备 key，防止把主 key 发去别的
  服务商）。
- 向后兼容：设置页视觉三字段（base_url / 模型 / key）保留；旧 config 若已填智谱
  base_url + key，行为与现状逐字节一致；不填 = 复用主 key。
- 边缘处理：DeepSeek 不支持 BMP。直接上传 .bmp 给友好中文报错（引导转存 PNG/JPEG）；
  PDF 内嵌 BMP 静默跳过（既有降级语义）。
- 观测 / 文案：视觉调用观测 provider 标签 zhipu → deepseek；未配置提示文案不再提
  智谱；429 不重试策略维持（DeepSeek 限流少见，改动留后续）。

## 用户故事

1. 作为已配置 DeepSeek key 的用户，我想要上传赛题 PDF / 图片后自动得到示意图视觉图注，
   以便 AI 简介 / 推荐 / 骨架「看到」图的内容——无需再注册智谱、无需在设置页填第二套 key。
2. 作为曾经配置过智谱视觉通道的用户，我想要旧配置继续原样工作，以便升级工具零迁移。
3. 作为使用其它 OpenAI 兼容视觉服务的用户，我想要设置页仍可覆盖 base_url / 模型 / key，
   以便不被锁定在 DeepSeek。
4. 作为上传 .bmp 图片的用户，我想要得到明确的中文提示，以便知道该转存为 PNG/JPEG。
5. 作为查看设置页 / 进度观测的用户，我想要文案与 telemetry 不再出现「智谱」字样，
   以便界面与实际后端一致。

## 实现决策

- 默认值单源：`vision.DEFAULT_VISION_BASE_URL` → `https://api.deepseek.com`，
  `vision.DEFAULT_VISION_MODEL` → `deepseek-v4-flash-vision-exp`；config 层沿用既有
  导入关系，不新增配置键。
- key 复用放在装配层（webapp 路由取配置处）而非 config 解析层：config 保持「原始值」
  语义（设置页回显不因复用而失真）；装配层以 helper 计算有效视觉 key，守卫 = 视觉
  base_url 属于 DeepSeek 官方端点（`https://api.deepseek.com` 与带 `/v1` 形态）。
- 视觉调用观测 `provider` 标签改为 `deepseek`。
- `VisionNotConfiguredError` 文案改为引导「填写视觉 key 或复用主 key」。
- .bmp 直接上传在 extract_image 入口拦截（友好中文）；PDF 内嵌图 mime 映射不变
  （bmp → image/bmp 仍发请求，失败静默跳过——现状降级语义）。
- 不改动：请求形状（与 DeepSeek 官方示例逐字兼容）、重试参数、429 不重试、进程内
  sha256 缓存、8 张 / 4MB 上限（单图独立请求，远低于官方 48MiB 请求体 / 32MiB 单图限）。

## 测试决策

- 只测外部行为，不测实现细节；沿用既有假传输注入（vision.Transport 接缝）与
  webapp 测试夹具（TestClient + config 替换）。
- 更新的既有测试：test_vision（docstring、默认值锁）、test_config（默认 base/model
  断言）、test_webapp 设置项（GET 默认值 / PUT 回写 / 掩码）。
- 新增断言：默认值 = DeepSeek 官方端点与模型名；有效视觉 key helper 的三种守卫分支
  （空 key + DeepSeek base → 主 key；空 key + 自定义 base → 空；显式 key 优先）；
  .bmp 直接上传 → 中文提示（400 中文，登记 errors.py 后仍走既有映射）。
- 结构测试（tests/test_repo_language.py 等）不新增断言；全量 pytest + 前端 node 测试
  收尾跑通。

## 范围外

- 429 重试策略调整（维持现状）。
- 视觉通道降级链（DeepSeek 失败自动回退智谱）——不做，保持「失败静默降级」既有语义。
- 图片 token 计费估算接入 llm_pricing（视觉调用观测已有 usage 空值通道，留后续工单）。
- PDF 扫描件整页 OCR（维持现状报错）。
- 移除视觉设置字段 / 简化 UI。

## 补充说明

- 官方依据：DeepSeek API 文档「图像理解」页（api-docs.deepseek.com/zh-cn/guides/vision/）：
  模型 `deepseek-v4-flash-vision-exp`，Chat Completions 端点，图片仅限 user 消息，
  格式 JPEG/PNG/GIF/WebP，单图 384 token 封顶，请求体 48 MiB / 单图 32 MiB。
- 用户已确认：设置页保留字段仅改文案；BMP 按友好报错处理（用户主路径是 PDF 上传）。
