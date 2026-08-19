# spec：vision-eyes —— 给 DeepSeek 装眼睛（免费云端视觉通道）

## 问题陈述

工具所有 AI 能力走 DeepSeek（纯文本），**看不见图片**：赛题 PDF 里的电路图 / 场地布局图 / 结构示意图全部丢失（extraction.py 用 pypdf 只抽文本）；学生拍的照片 / 截图没有任何入口。电赛"做新题"时，图的尺寸 / 布局 / 电路细节往往是题面文字简略甚至省略的关键信息——AI 看不到图 = 推荐与骨架可能漏需求。

用户已定案：**仅用免费云端 GLM-4V-Flash**（智谱官方免费多模态 API，OpenAI 兼容）；本地视觉否决（识图效果顾虑）；扫描件 PDF 首期不做（整页渲染需 pymupdf 依赖，后续再补）。

## 方案

### 视觉通道（新模块 vision.py）

- `describe_image(image_bytes, mime, prompt) -> str`：OpenAI 兼容 `chat/completions`，content = text + image_url（`data:<mime>;base64,...`），模型默认 `glm-4v-flash`。
- 网络层照 llm.py 先例：标准库 urllib（零第三方依赖）+ 可注入传输接缝（测试假件）；网络错误重试（照 DeepSeek 网络退避先例，简化版）。
- 描述提示词引导提取要素："这是电赛题面中的示意图，请提取尺寸 / 标注文字 / 电路连接 / 布局结构等对解题有用的信息，用中文简洁描述。"
- 观测：复用 llm_observation 记录（operation="vision_describe"，provider=智谱）。

### 抽取注入（extraction.py 扩展）

- 电子版 PDF 抽取文本后：`page.images` 提取嵌入图（pypdf 6 自带，零新依赖）→ 逐张 `describe_image` → 图注段 `[示意图N：<描述>]` **追加进题面文本尾部**（下游简介 / 推荐 / 骨架 / 交接零改动全受益）。
- 上限守卫：单文件图片 ≤ 8 张、单张 ≤ 4MB（超限跳过并标注"（已跳过超大图）"），防请求体爆炸与限速。
- 图片内容哈希缓存（进程内 dict：sha256 → 描述），同图重跑不重复调用。
- **静默降级**：未配视觉 key / 网络失败 / 解析失败 → 只用文本（现行为逐字节不变），绝不阻断抽取。

### 图片文件上传（步骤 1 入口扩展）

- 文件上传 / 粘贴支持图片类型（.png / .jpg / .jpeg / .bmp / .webp）→ 直接走视觉描述 → 描述文本作为题面上下文（与 PDF 图注同格式）。

### 配置与设置页

- AppConfig 新增：`vision_base_url`（默认 `https://open.bigmodel.cn/api/paas/v4`）/ `vision_api_key`（默认空）/ `vision_model`（默认 `glm-4v-flash`）。
- 无 key = 视觉功能关闭（抽取行为与现在逐字节一致）。
- 设置页「视觉通道」卡片：base_url / key / 模型，照 AI API 配置先例。

## 用户故事

1. 作为参赛学生，上传含电路图 / 布局图的电子版赛题 PDF——抽取后题面文本带 `[示意图1：…]` 图注，AI 简介 / 推荐 / 骨架都能看到图的内容。
2. 作为参赛学生，上传作品照片 / 屏幕截图（jpg/png）——同样描述进上下文（为将来工程问答铺路）。
3. 作为未配 key 的用户——一切照旧（视觉静默关闭，逐字节兼容）。
4. 作为维护者——视觉调用有观测记录（operation=vision_describe），图片重复上传走缓存不重复花钱。

## 实现决策

- vision.py 纯函数 + 可注入传输（照 llm.py `post` 接缝先例）：不 import 生成流程；错误类型 VisionError 登记 errors.py（→ 400/降级文案）。
- 提取注入归 extraction 层（`_extract_pdf` 后处理），路由只透传（照现路由薄壳先例）。
- 描述失败逐张降级：某张失败只丢该张图注（其余照常），整文件视觉失败 = 无图注（文本照常）。
- 缓存放 vision.py（`describe_image_cached`，进程内 dict，键 = 图片 sha256；不落盘，重启即清——v1 够用，落盘留后续）。
- 图片类型分发：extraction.extract_file 加图片分支（mime 判定 + 读字节走视觉）；现有 `_require_text` 对图片不适用（图片无需"文字"判定）。
- 注入位置：PDF 文本尾部追加图注段（页序关联后续再细化）。

## 测试决策

- vision.py 单测：假传输注入（照 fakes 假 LLM 先例）——请求体形状（base64 data URL / 模型名 / 提示词）、错误重试、解析。
- extraction 集成：构造含嵌入图 PDF（pypdf PdfWriter + 仓库内小图片）→ 假视觉 → 文本 + 图注；无图 PDF → 逐字节不变；视觉失败 → 降级文本照常。
- 配置测试：无 key 关闭 / 有 key 启用（照 test_config 先例）。
- webapp 测试：图片上传端点 / 设置读写（照 test_webapp 先例）。
- 全量回归：不配视觉 key 时全量测试零变化（默认关闭）。

## 范围外

- 扫描件 PDF 整页兜底（需 pymupdf 渲染，用户已定首期不做）。
- 本地视觉（Ollama）/ OCR / 视频。
- 视觉描述缓存落盘（v1 进程内）。
- 图注与页面位置关联（v1 尾部追加）。
- 工程问答 C3 的图片问答入口（本 spec 只做"图 → 文本注入"，问答留后续）。

## 补充说明

- API key 由用户注册[智谱开放平台](https://open.bigmodel.cn)自行获取，工具设置页填写；开发与测试用假传输，不依赖真实 key。
- GLM-4V-Flash 免费层有限速——图片上限 + 哈希缓存 + 失败降级共同缓解。
- 语言规范：spec / 工单 / 提交信息中文。
