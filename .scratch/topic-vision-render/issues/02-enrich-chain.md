# 工单 02：enrich 三级降级链（渲染视觉优先）+ 真实环境验证

- Status: resolved
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

- [x] 三级降级链测试通过（渲染优先写回不调下级 / 渲染空降级文字标注 / 三级全空原样）
- [x] 现有 enrich 测试语义不变全绿（autouse fixture 关闭渲染路径 + test_webapp 补 mock）
- [x] 2021F 真实换新图注（DeepSeek 渲染视觉描述写回，146 行完整结构化：十字走廊布局/
      药房位置/中部病房/1号2号/门口区域 5cm/上臂与左右臂尺寸链/红实线走向；对比旧
      文字标注碎片词），自动提交 191db70「lib: 赛题条目补图注」+ 6198307 CHANGELOG
- [x] 全量回归（2202）+ mypy 59 文件干净

## 评审记录

与工单 01 同一轮 code-review 双轴（subagent 9670e5a6 / b4e050c8）：
- 渲染段幂等守卫缺口（`"[示意图" in notes` 拦不住 `[图1 标注：…]`）→ 守卫条件与
  _substantive_text 正则已覆盖冒号形态（见工单 01 评审记录）。
- 真实环境验证要点：PUT /api/settings 清空 vision_base_url/vision_api_key/vision_model
  （回 DeepSeek 官方默认 deepseek-v4-flash-vision-exp + 复用主 key，绕开智谱 429）；
  旧 `[图1 标注]` 段手动移除（备份 .scratch/backups/topic_2021F_pre_render_vision.md）
  后 GET /api/topics/2021F 触发视觉优先补图注；二次 GET 幂等（len=7382 不变，无新提交）。

## 评审后状态

- Status: resolved（真实环境验证完成，已推送）
