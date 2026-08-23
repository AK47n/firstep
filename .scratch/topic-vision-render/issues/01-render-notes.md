# 工单 01：渲染视觉图注（extraction.py 渲染页 → DeepSeek 视觉描述）

- Status: resolved
- 依赖: 无
- 阻塞: 02

## 目标

extraction.py 新增渲染视觉路径：矢量图 PDF 页渲染成位图 → DeepSeek 视觉模型描述，
产出 `[图N 标注：<描述>]` 段；渲染/视觉任何失败静默降级（空串，绝不抛）。

## 改动

1. 常量：PAGE_RENDER_SCALE=2.0、RENDER_DESCRIBE_PROMPT（只描述示意图忽略正文、无图
   只回「无实质内容」）、RENDER_NOTE_MIN_CHARS=8、RENDER_NO_FIGURE_PATTERN
   （`无(?:示意)?图|没有(?:示意)?图|仅(?:有)?文字|只有文字|无实质内容`）。
2. `_render_page_png(path, page_no) -> bytes | None`：防御 import fitz（ImportError →
   None）；fitz.open → doc[page_no-1] → get_pixmap(Matrix(2,2)) → tobytes("png")；
   任何异常 → None。模块级 = 测试 monkeypatch 接缝。
3. `_page_figure_label(page) -> str | None`：页文本层行首「图N」标题图号（`^\s*图\s*\d+`），
   无 → None（顺序编号兜底）。
4. `pdf_page_render_notes(path, *, vision_base_url, vision_api_key, vision_model,
   observation_collector=None, pages=None) -> str`：逐页渲染 + describe_image_cached
   （RENDER_DESCRIBE_PROMPT，mime=image/png）；无实质/否定词描述过滤；真实图号优先 /
   顺序编号兜底；`[图N 标注：<描述>]` 逐行；MAX_IMAGE_NOTES=8 封顶；全失败空串。
5. pyproject.toml dependencies 加 "pymupdf>=1.24"。
6. 模块 docstring 与 pdf_image_notes docstring 更新（矢量图渲染路径说明）。

## 验收

- [x] 测试：_render_page_png（无 fitz → None / 假 fitz → PNG / 坏 PDF → None）、
      _page_figure_label（行首图号 / 正文引用 / 无文本层）、pdf_page_render_notes
      （格式 / 图号优先与兜底 / 过滤 / 失败跳过 / pages 限定 / 封顶 / 全败空串 /
      渲染抛异常跳过 / 图号防撞）
- [x] 全量回归（2202 通过）+ mypy 干净
- [x] 单测阶段不真实调用视觉（describe_image_cached 全 mock）

## 评审记录

code-review 双轴（subagent 9670e5a6 Standards / b4e050c8 Spec）：

**Standards 轴整改**：
- 硬违规：CONTEXT.md「赛题库」词表仍写两级生成 → 已更新为三级视觉优先。
- 气味整改：describe_kwargs 三处重复 → 提取 `_describe_kwargs` helper；
  `_render_page_png` 无句柄管理 → `with fitz.open(...)`；图号兜底与真实图号
  撞车重复（真实 bug）→ used_labels 集合 + 顺序兜底从 1 找第一个未占用号 +
  同图号页跳过；行首正则与 _figure_annotation_block 不同源 → 共享
  `_FIGURE_TITLE_RE` 常量。
- 微项：autouse fixture 位置移到 import 区后。

**Spec 轴整改**：
- (c)1 幂等守卫不覆盖渲染段：`"[示意图" in notes` 拦不住 `[图1 标注：…]`，
  `_substantive_text` 正则剥不掉冒号形态 → 守卫条件改 `[示意图` 或 `[图N 标注：`
  正则；`_substantive_text` 正则 `\[图\s*\d+\s*标注[：]?` 支持两种形态。
- (c)2 `description.strip()` 在 try 外（防御缺口）→ 渲染/描述/过滤整体移入 try，
  渲染函数调用也包 try（渲染器抛异常外泄防护）。
- (a) 测试未覆盖渲染抛异常分支 → 补 test_pdf_page_render_notes_rendering_exception_skips_page。
- 补测试：图号防撞（真实不连续 + 顺序兜底取 2）、同图号页跳过、渲染段无实质
  不写回（test_topic_library）。

## 评审后状态

- Status: resolved（整改完成，全量 2202 + mypy 59 文件干净）
