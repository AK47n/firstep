# 方案：给 DeepSeek 装眼睛（免费视觉通道）

> 日期：2026-08-18。性质：方案讨论（未立项）。实施时按 `docs/agents/workflow.md` 走 clarify → spec → 工单。

## 一、需求场景（哪里需要"眼睛"）

1. **赛题 PDF 里的图（最高价值）**：`extraction.py` 现在用 pypdf 只抽文本（`_extract_pdf`），PDF 里的电路图 / 场地布局图 / 结构示意图**全部丢失**；扫描版赛题 PDF（真题常见）直接报"未能抽取到任何文字"（`_require_text`）。"做新题目"时，图的尺寸 / 布局 / 电路细节往往是题面文字里简略甚至省略的关键信息——AI 看不到图 = 推荐与骨架可能漏需求。
2. **学生上传的照片**：作品照片、接线照片、示波器 / 屏幕截图——调试问答与报告素材（当前工具无此入口）。
3. **参考资料的原理图**：参考文件库文本为主，图进不了 LLM 上下文。

## 二、候选方案（免费优先）

| 方案 | 形态 | 免费性质 | 中文效果 | 隐私/断网 | 集成成本 | 备注 |
|---|---|---|---|---|---|---|
| **A. 智谱 GLM-4V-Flash**（[官方文档](https://docs.bigmodel.cn/cn/guide/models/free/glm-4v-flash)，[首个免费多模态 API 报道](https://hub.baai.ac.cn/view/41730)） | 云端 API，OpenAI 兼容（chat/completions + image_url base64） | 官方免费（有限速，日常够用） | 好（中文模型） | 云端（传图） | 低（与现有 DeepSeek 调用同构） | **首选云端**；注册智谱开放平台拿 key |
| B. 通义千问 Qwen-VL（阿里云百炼） | 云端 API | 新用户免费额度（用完收费） | 好 | 云端 | 低 | 免费是额度制，非长期免费 |
| C. Gemini API 免费层 | 云端 API | 免费层（RPM 限制） | 中（中文弱于国产） | 云端 | 低 | 需海外网络，备选 |
| **D. 本地 Ollama 视觉模型**（qwen2.5vl / [gemma3](https://www.douyin.com/video/7482414257288613139?source=Baiduspider-sdc) / llava，[Ollama Vision](https://mintlify.wiki/ollama/ollama/features/vision)） | 本地推理 | 完全免费无限制 | qwen2.5vl 中文好；gemma3 4B 可低配跑 | **本机，零泄露 + 断网可用**（契合现场模式） | 中（已有 local-llm-routing 底座，[qwen2.5vl 在 Ollama 库](https://ollama.com.tw/library/qwen2.5vl)） | 7B 级对复杂电路图 / 小字标注理解弱于云端大模型；需下载模型 |
| E. PaddleOCR / tesseract（纯 OCR） | 本地 | 免费 | 好（文字识别） | 本机 | 低 | **只解决"图里文字"，不解决"理解图"**——补充件，非替代 |

另有社区现成参照：给 DeepSeek 类文本模型加免费视觉的[自动降级路由项目](https://github.com/SolicitousMonkey/deepseek-free-eyes)、[dsh-img 插件](https://github.com/gmleong/dsh-img)、[GLM-4V 视觉 MCP](https://github.com/ethanweave/glm4v-vision-mcp)——说明需求普遍、形态可参考，但我们直接在应用层集成，不需要 MCP/插件层。

## 三、推荐组合（已定案：仅云端）

**主通道 = A（GLM-4V-Flash 免费 API），不做本地视觉**（用户决策：本地 7B 级模型识图效果不放心）。

- 默认云端 GLM-4V-Flash：中文好、质量高、零成本（有限速，一次赛题 2-10 张图够用）；
- 纯 OCR（E）不作为首期内容，遇到"图里文字识别"再补；
- 本地 Ollama 视觉（D）：**已否决**（识图效果顾虑），不实现。

### 扫描件 PDF 说明（用户问询记录）

PDF 分电子版（文本层，pypdf 可抽字）与扫描件（每页 = 一张图片，无文本层，pypdf 抽不出）。历年真题扫描版常见，现有 `_require_text` 对扫描件直接报"未能抽取到任何文字"。视觉通道的扫描件兜底 = 整页当图片丢给 GLM-4V-Flash 看图描述（比纯 OCR 强：能理解电路图/布局图，不只认字）。

## 四、架构集成设计（草案）

1. **新模块 `vision.py`**：`describe_image(image_bytes, prompt) -> str`——OpenAI 兼容接口（base64 image_url），云端 = GLM-4V-Flash、本地 = Ollama `/v1`（现有 local-llm-routing 同款端点）；描述提示词引导："这是电赛题面中的示意图，请提取尺寸 / 标注文字 / 电路连接 / 布局结构……"。
2. **extraction 扩展（核心增值）**：PDF 抽图（pypdf 页面图片提取，或换 pymupdf 一并拿图）→ 逐张 `describe_image` → 图注文本（`[图1：…]`）**追加进题面文本** → 下游（简介 / 推荐 / 骨架 / 交接）全部自动受益，**零改动**（题面文本是唯一入口，TopicContext 贯穿先例）。扫描件 PDF：OCR/视觉描述后不再报"未能抽取到任何文字"。
3. **上传图片入口**：步骤 1 支持贴图 / 上传图片（照片、截图），同样描述成文本挂进题面上下文（为将来的工程问答 C3 铺路）。
4. **设置页**：视觉通道配置（base_url / key / 模型 / 云端或本地开关），照 AI API 配置先例；LLM 观测（llm_observation）与费用估算可扩展覆盖视觉调用（同 collector）。
5. **缓存**：同图（内容哈希）描述结果缓存（照 recommend_cache 先例），重跑不重复花钱 / 耗时。
6. **测试**：假视觉先例（照 fakes.py 假 LLM）；PDF 抽图 + 描述注入的集成测试；旧路径（无图 PDF）逐字节不变。

## 五、风险与权衡

- **免费限速**：GLM-4V-Flash 免费层有 RPM 限制——一次赛题图 2-10 张、每张 1 次调用，日常足够；超限自动降级本地（路由层可做"云端失败 → 本地兜底"开关，与现有"本地失联不自动回退远程"策略相反，需决策）。
- **电路图理解深度**：7B 本地模型对复杂图弱——云端主通道缓解；描述质量用"提取要素"引导词 + 摘要注入（不是让模型看图解题）。
- **隐私**：云端传图（学生作品图一般无敏感）；本地模型零泄露。
- **体积**：Ollama 模型数 GB（qwen2.5vl:7b ≈ 5-6GB）——选装，不进软件包。

## 六、待决策点（进度）

1. ~~主通道确认用 GLM-4V-Flash？~~ **已定：仅云端 GLM-4V-Flash**（本地视觉否决）。
2. ~~本地备选模型选哪个？~~ **已否决（不做本地）**。
3. PDF 抽图库：pypdf 提取嵌入图（零新依赖，覆盖电子版示意图）vs pymupdf（渲染整页，扫描件兜底必需）——**取决于决策点 4**。
4. 扫描件 PDF 是否纳入首期？（推荐纳入：真题扫描版常见，视觉整页看图兜底"无文字"路径）——纳入则引入 pymupdf 依赖。
5. 视觉描述注入题面的时机：**上传/抽取时一次性做 + 图片哈希缓存**（推荐，下游零改动）——已建议，待确认。
6. API key：用户注册[智谱开放平台](https://open.bigmodel.cn)获取；设置页留空 = 视觉功能关闭（不阻塞开发与测试）。
