# 03 — 2021F 真机验收（主链路 + 降级路径）

**要做什么：** 用真实 DeepSeek 视觉服务跑通 2021F 的完整验收：走库内条目推荐，AI 提出「走廊宽度」类图内问题时被自动消化、用户不再被问；同时真机复验三条降级路径（无视觉配置 / 粘贴题面无图 / 视觉答不上），确认行为与改动前一致——主链路与降级都符合 spec 承诺。

**被谁阻塞：** 02 — 真视觉接线已就位

**状态：** ready-for-human

- [ ] 主链路：库内 2021F 条目 + ccs 平台走 `/api/recommend`，真实视觉调用；AI 提出图内尺寸类澄清问题时，观察 `question` 事件——该类问题不再出现（或已被自动消化后再无剩余），推荐正常收敛到 done；若首轮无澄清问题（题面已够），改用构造的图内问题场景（如临时删图注尾巴）复验
- [ ] 降级路径一（无视觉配置）：视觉 key 留空（或临时指向无效 key）走同一推荐——行为与改动前逐字节一致（该问用户的问题照问）
- [ ] 降级路径二（粘贴无图题面）：no-topic 形粘贴文本推荐——行为与改动前一致，无异常
- [ ] 降级路径三（视觉答不上）：构造视觉必然答不上的问题（或 mock 回调返回 None）——问题照旧问用户，流程不阻塞
- [ ] 视觉答案进 clarifications 后收敛正常（答案内容确实影响模块选择时行为合理、不产出幻觉模块）
- [ ] 验收记录（问题样例 / 视觉答案 / 剩余问题 / 结论）追加到本工单 Comments

## Comments

- 2026-09-09 代码事实盘点（**维持 ready-for-human，不翻牌**——本单验收必须真调视觉服务，
  消耗真实额度，非代码可证）：
  **已就位的代码事实（前序条件全部成立，只差真机跑一次）**——
  ① 2021F 库内条目存在：`library/topics/2021F/manifest.json`（year 2021 / number F /
  `original_pdf = 000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf`，文件 34996432 字节
  实况在盘）+ `topic.md`；
  ② 真视觉接线（工单 02 已 resolved）：`src/contest_generator/vision_qa.py
  answer_figure_question`（locate_topic_pages → 逐页渲染 → `describe_image_cached(prompt=问题)`
  → 否定词表判 None）；装配点 `src/contest_generator/webapp.py:1752-1769`
  （`topic.figure_pdf is not None` 且 `vision_configured(vision_api_key)` 才注入
  `vision_qa` 闭包，:1828 传 `run_recommendation`，:1833-1834 观测器结算）；
  ③ 单测覆盖：`tests/test_vision_qa.py` 9 用例（:42 答案返回 / :69 只渲染定位页 /
  :100 否定词参数化 / :117 定位失败 / :132 定位抛错 / :147 渲染失败跳过 /
  :171 视觉抛错 / :190 多页拼接 / :221 全否定）；
  ④ 本机配置实况：`~/.contest_generator/config.json` 的 **`vision_api_key` 为空**
  （长度 0），`vision_base_url=https://api.deepseek.com`、
  `vision_model=deepseek-v4-flash-vision-exp`——按仓库口径「视觉 key 留空 =
  复用主 key」，所以主链路可跑，但**必须真调一次 DeepSeek 视觉服务并消耗额度**。
  **为什么仍是 ready-for-human**：工单六条验收全部是「真机 + 真实额度 + 肉眼观察
  question 事件」的现场判定（主链路、三条降级路径、答案进 clarifications 后的收敛
  合理性、验收记录要写问题样例与视觉答案），agent 在沙箱内无法替代；且属于用户
  明确点名的「只有真机/额度才能验」类。
  **下个会话/人工开工指引**（直接照做即可）：
  1. `$env:PYTHONPATH='src'; python -m contest_generator.webapp`（或既有启动脚本）起服务；
  2. 走「选历史题 → 2021F + ccs 平台 → 推荐」，观察 SSE 是否出现 `question` 事件，
     以及图内尺寸类问题（走廊宽度等）是否被自动消化后收敛到 `done`；
  3. 三条降级路径按工单逐条复验（视觉 key 置空或指向无效 key / no-topic 粘贴文本 /
     mock 回调返回 None）；
  4. 把「问题样例 / 视觉答案 / 剩余问题 / 结论」写回本工单 Comments 后翻 resolved。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
