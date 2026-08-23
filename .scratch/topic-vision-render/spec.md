# 视觉优先渲染图注（topic-vision-render）

## 背景

2021F 补图注实测（.scratch/fig1_render_vision.py / fig1_deepseek_vision.py）：

- **文字标注对 LLM 可读性差**：`[图1 标注]` 的散乱尺寸词（60cm…40cm 30cm 40cm…）丢
  失垂直间距量级、行序与图形元素信息，让 deepseek-v4-flash 还原图结构只抓出碎片
  词（错漏严重：60cm 实为走廊宽度但不知布局、1号/2号位置全丢、红实线走向缺失）。
- **渲染 + 视觉描述质量高**：PyMuPDF（fitz，环境 1.28.0）把矢量图 PDF 页渲染成位图
  （Matrix(2,2) → 1191×1684 PNG，187KB），喂 DeepSeek 官方视觉模型
  deepseek-v4-flash-vision-exp（vision.py 默认通道，复用主 key）输出完整结构化
  描述：每条尺寸标注的位置、红实线走向、药房/病房分布，并主动列出不确定处。

用户拍板：**enrich 补图注改为「渲染页 → 视觉描述」优先**，视觉失败自动退回现有
文字标注路径。智谱视觉（用户当前配置）实测持续 429 限流——交付时把视觉配置改回
DeepSeek 官方默认（复用主 key，零额外额度）。

## 现状（改前）

- `_figure_notes`（topic_library.py:294）两级生成：`pdf_figure_annotations`
  （文字标注优先，零额度）→ 空则 `pdf_image_notes`（内嵌栅格图视觉兜底）。
- `pdf_image_notes`（extraction.py:132）只识别 PDF 内嵌栅格图对象（page.images）——
  **矢量图（绘图命令绘制）提取不到**，2021F 图1 正属此类。
- vision.py 默认通道已是 DeepSeek 官方视觉（DEFAULT_VISION_BASE_URL=
  api.deepseek.com、DEFAULT_VISION_MODEL=deepseek-v4-flash-vision-exp、key 留空
  且 base_url 为 DeepSeek 端点时复用主 key）——用户设置里配的智谱（glm-4.6v）
  覆盖了默认，且免费层持续 429。

## 方案

### extraction.py 新增（工单 01）

1. 常量：
   - `PAGE_RENDER_SCALE = 2.0`（渲染倍率，实测 Matrix(2,2) 质量足够且 187KB < 4MB 上限）
   - `RENDER_DESCRIBE_PROMPT`：页面渲染场景专用提示词——「只描述页面中的示意图
     （结构图/流程图/电路图），忽略页面上的正文文字；页面没有示意图只回复
     『无实质内容』」。
   - `RENDER_NOTE_MIN_CHARS = 8`（无实质过滤下限，与 topic_library.MIN_FIGURE_NOTE_CHARS
     同值但独立定义——extraction 不 import topic_library，防环）。
   - `RENDER_NO_FIGURE_PATTERN`（否定词守卫正则）：描述含 `无(?:示意)?图|没有(?:示意)?图|
     仅(?:有)?文字|只有文字|无实质内容` → 视为无图页丢弃（正文页误描述不污染题面）。
2. `_render_page_png(path: Path, page_no: int) -> bytes | None`：防御 import fitz
   （ImportError → None）；`fitz.open(str(path))` → `page = doc[page_no - 1]` →
   `get_pixmap(matrix=fitz.Matrix(scale, scale))` → `tobytes("png")`；任何异常 → None
   （渲染是增强不是阻塞）。模块级函数 = 测试 monkeypatch 接缝。
3. `_page_figure_label(page) -> str | None`：页文本层行首「图N」标题的图号（复用
   `^\s*图\s*\d+` 行首正则，正文引用「如图1所示」不在行首天然排除）；无 → None
   （扫描件无文本层，走顺序编号兜底）。
4. `pdf_page_render_notes(path, *, vision_base_url, vision_api_key, vision_model,
   observation_collector=None, pages=None) -> str`：
   - 选定页（_selected_pages，1-based，None = 全部页）；
   - 逐页：_render_page_png → None 跳过；`describe_image_cached(png, "image/png",
     RENDER_DESCRIBE_PROMPT, base_url=…, api_key=…, model=…, observation_collector=…)`
     （失败跳过该页，其余照常）；
   - 过滤：描述 strip 后 < RENDER_NOTE_MIN_CHARS 或命中 RENDER_NO_FIGURE_PATTERN →
     跳过（无图页 / 正文页）；
   - 图号：`_page_figure_label(page)` 非 None 用真实图号；否则顺序编号（第 k 个产出 → k）；
   - 产出 `[图N 标注：<描述>]` 逐行 \n join；产出数达 MAX_IMAGE_NOTES（8）封顶；
     全部失败/无图 → 空串（调用方降级）。
   - 幂等兼容：段前缀 `[图N 标注` 命中 enrich 既有幂等正则 `\[图\s*\d+\s*标注` ✓。
5. 模块 docstring 与 `pdf_image_notes` docstring 更新（「矢量图视觉提取不到」修正为
   「矢量图无栅格图对象，走 pdf_page_render_notes 渲染路径」）。

### topic_library.py（工单 02）

1. `_figure_notes` 三级降级链（渲染视觉优先）：
   1. `pdf_page_render_notes`（渲染页 → DeepSeek 视觉描述）；
   2. `pdf_figure_annotations`（文字标注兜底，零额度）；
   3. `pdf_image_notes`（内嵌栅格图视觉兜底，现状保留）。
   各级异常 → 空串，逐级降级；全空 → 返回空（enrich 原样返回）。
2. import 区加入 `pdf_page_render_notes`。
3. `enrich_topic_image_notes` / `_figure_notes` docstring 更新（两级 → 三级、视觉优先、
   各级失败降级语义不变：图注是增强不是阻塞）。
4. 幂等检查与 MIN_FIGURE_NOTE_CHARS 守卫不变（`[图N 标注：` 段也过
   _substantive_text 守卫——实质 < 8 字符不写回）。

### pyproject.toml（工单 01）

- dependencies 加 `"pymupdf>=1.24"`（渲染能力正式依赖，Pillow 先例：声明依赖 +
  代码防御 import，缺失时降级不崩）。

### webapp.py

- **零代码改动**（GET /api/topics/{key} 已透传 vision 三参数 + _resolve_vision
  复用主 key）。
- **交付动作**：PUT /api/settings 清空 vision_base_url / vision_api_key（回 DeepSeek
  官方默认 + 复用主 key，绕开智谱 429）。

### 真实环境验证（工单 02）

- 2021F topic.md 已含旧 `[图1 标注]`（文字标注）——幂等会跳过重补。**手动移除旧段**
  → GET /api/topics/2021F 触发 enrich → 视觉优先写回 `[图1 标注：<DeepSeek 描述>]`
  → 验证写回质量 + 自动提交「lib: 赛题条目补图注」+ CHANGELOG。

## 测试计划（tdd）

- test_extraction.py：
  - `_render_page_png`：无 fitz（monkeypatch `sys.modules["fitz"] = None` → import 抛
    ImportError）→ None；假 fitz（monkeypatch sys.modules 注入 FakeFitz：open → doc →
    get_pixmap → tobytes("png")）→ 返回 PNG 字节；坏 PDF → None。
  - `_page_figure_label`：假页对象（extract_text 含行首「图1 院区结构示意图」→ "1"；
    正文「如图1所示」无行首 → None；无文本层 → None）。
  - `pdf_page_render_notes`：monkeypatch `_render_page_png`（假 PNG / None 混合）+
    `describe_image_cached`（记录调用返回假描述）→ 断言 `[图1 标注：…]` 格式、真实
    图号优先 / 顺序编号兜底、无实质与否定词页过滤、单页视觉失败跳过、pages 限定、
    MAX_IMAGE_NOTES 封顶、全失败空串。
- test_topic_library.py：
  - 现有 enrich 测试（test_enrich_topic_annotations_prefer_text_over_vision 等 10 个）
    全部补 `monkeypatch.setattr(topic_library, "pdf_page_render_notes", lambda *a, **k: "")`
    （渲染空 → 降级走既有断言路径，语义不变）。
  - 新增：渲染优先测试（pdf_page_render_notes 返回 `[图1 标注：…]` → 写回且不调
    文字标注/内嵌图视觉）；渲染失败降级文字标注；三级全空原样返回。
- 全量回归 + mypy src 干净。

## 范围外

- 不做拆条入口（extract_pdf_with_image_notes）的渲染改造——上传 PDF 是单题文件，
  文字标注+内嵌图视觉够用，渲染视觉留 enrich 一条路径。
- 不改 pdf_image_notes 语义（内嵌栅格图路径保留为第三级兜底）。
- 不做 Word/PDF 导出、不做缓存落盘（进程内缓存沿用）。
