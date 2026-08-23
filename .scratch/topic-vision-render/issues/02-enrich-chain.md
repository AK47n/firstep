# 工单 02：enrich 三级降级链（渲染视觉优先）+ 真实环境验证

- Status: claimed
- 依赖: 01（已完成）
- 阻塞: 无

## 目标

topic_library._figure_notes 改为三级降级链（渲染视觉优先 → 文字标注 → 内嵌图视觉），
并完成真实环境验证（2021F 换新图注 + 视觉配置切回 DeepSeek）。

## 改动

1. import 区加 pdf_page_render_notes；_figure_notes 三级链（各级异常空串降级）。
2. enrich_topic_image_notes / _figure_notes docstring 更新（视觉优先语义）。
3. 现有 enrich 测试（约 10 个）补 `monkeypatch.setattr(topic_library,
   "pdf_page_render_notes", lambda *a, **k: "")`（渲染空 → 走既有断言路径）。
4. 新测试：渲染优先写回（不调文字标注/内嵌图）；渲染失败降级文字标注；三级全空原样。
5. 真实环境验证：
   - PUT /api/settings 清空 vision_base_url / vision_api_key（回 DeepSeek 默认 + 复用主 key）；
   - 手动移除 2021F topic.md 旧 `[图1 标注]` 段 → GET /api/topics/2021F 触发 enrich →
     视觉优先写回 `[图1 标注：<DeepSeek 描述>]` → 质量核验 + 自动提交入库。

## 验收

- [ ] 三级降级链测试通过（顺序 + 各级降级）
- [ ] 现有 enrich 测试语义不变全绿
- [ ] 2021F 真实换新图注（DeepSeek 视觉描述写回，含红实线走向/尺寸位置），自动提交
- [ ] 全量回归 + mypy 干净

## 评审记录

（code-review 后填写）
