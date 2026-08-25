# 视觉通道自检（设置页一键测通）

## 问题陈述

视觉通道（图片/示意图识别）配置项多：base_url / model / api_key / 复用主 key
规则。用户配完不知道通不通（上传题面 PDF 才发现静默降级成「无示意图描述」）。
需要一个「自检」入口：点一下即知当前配置能否正确调用视觉模型。

## 方案

- **后端**：新增 `POST /api/vision/selfcheck`——用当前生效的视觉参数
  （`_resolve_vision` 同源：视觉 key 留空 + DeepSeek 端点 = 复用主 key）
  对内置 1×1 PNG 做一次真实识别（`describe_image`，不走缓存 = 每次都真发）。
  成功返回 `{ok: true, elapsed_ms, model, message}`；未配置 / 调用失败走
  HTTPException 400 中文（含设置页引导）——两类分开：空 key 直报
  「未配置：请到设置页…」（不套「自检失败」前缀），VisionError 报
  「视觉自检失败：<原因>」。
- **前端**：设置页「视觉通道（可选）」卡内加「自检视觉通道」按钮 + 状态行；
  点击 → 灰字「正在调用视觉模型…」→ 成功显示
  「✓ 视觉通道正常（模型 …，耗时 …ms）：<描述>」绿字，
  失败显示红字错误消息。

## 用户故事

- 作为用户，配完视觉参数点一下「自检」，马上知道通不通、用哪个模型、
  耗时多少，不用上传题面去试探。
- 作为用户，失败时看到原因（未配置 key / 网络 / 模型拒绝），知道去哪改。

## 实现决策

1. 自检走 `describe_image`（无缓存）——每次点击 = 真实链路请求，
   保证「通过 = 现在可用」；1×1 PNG 字节常量内置（与既有测试同款常量）。
2. 失败不返回 200 假成功：HTTPException 400 中文 detail，
   复用 `handle()` 前端统一错误提取（`e.message` 直接可显示）。
3. 自检不做二轮精注记（detail_qa）：只验证可用性，省一次视觉调用。
4. 测试用 monkeypatch `contest_generator.vision.describe_image`（webapp 直接
    import 的挂载点），照 test_extract_uploaded_png 先例。

## 测试决策

- tests/test_webapp.py 新增：
  - 成功：monkeypatch describe_image 返回描述 → 200、ok=true、elapsed_ms>=0、
    model 回显、message 含描述。
  - 未配置：自定义端点 + 空视觉 key → 400 中文（含「设置」）。
  - 调用失败：monkeypatch describe_image 抛 VisionError → 400 中文含原因。
- headless 冒烟：设置页按钮存在、点击后状态行有反馈（探针里 monkeypatch
  不可用，检查按钮渲染 + 点击后至少出现「正在」/错误文案之一即可）。

## 范围外

- 视觉通道健康度持久化 / 定时自检。
- 主 LLM 通道自检（已有推荐/简介调用可验证）。
- 自检历史记录。
