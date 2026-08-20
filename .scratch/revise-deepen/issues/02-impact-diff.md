# 02 — 影响分析与 diff

**要做什么：** 用户在「修订与深化」阶段粘贴新 Q&A 并点分析后，AI 逐条给出影响结论（每条 Q&A → 影响哪些功能需求 → 建议模块增/删/不变 + 理由），工具算出新旧模块集的确定性 diff（集合差，纯函数），并重算平台警告（missing / unverified / hardware_bound）。分析 API 返回待确认结果（影响结论 + 模块增删清单 + 理由 + 警告变化），前端可展示、可放弃。Q&A 以独立段注入（收敛循环先例：不并入题面、不动题面编号），Q&A 指纹变化缓存失效机制直接复用；结构化输出解析走重试兜底先例，非法输出自动重问。

**被谁阻塞：** 01（需要加载后的上下文：题面 / 现有 slugs / 功能需求）

**状态：** resolved（2026-08-21 实施完成 + code-review 双轴评审整改闭环）

## Comments

**实施记录（2026-08-21）：**
- 新模块 `impact.py`：compute_module_diff（新旧 slugs 集合差纯函数，增/删/
  不变保持输入顺序）；build_impact_analysis（域判决：逐条影响结论 + 建议
  模块集，库外 slug / 重复 / 自相矛盾 / 漏判大声失败）；run_impact_analysis
  （编排：LLM → diff → 平台警告重算 resolve_selection → done 载荷）。
- llm.py 加 analyze_impact（IMPACT_SYSTEM_PROMPT + Q&A 独立段注入，
  _retry_parse 重试兜底，RoutingLLM 走 remote——质量优先不进本地方法集）。
- webapp POST /api/revise/analyze（SSE：impact_analyzing → diff_ready →
  done 载荷 {impacts, suggested_slugs, diff, warnings, platform}）；服务端
  重新加载上下文（_load_revision_context 与 /api/revise/context 共用单址）+
  可选 slugs/platform 覆盖 + 可选 qa_count 逐条覆盖校验；缺题面同步 400。
- events.py 加 impact_analyzing / diff_ready 词表；ImpactError 登记 errors.py。
- 测试 21 项（tests/test_impact.py）+ 全量 2093 绿 + mypy 55 文件干净。

**评审整改（code-review 双轴）：**
- Standards：进度事件改引 events.py 常量（词表单源）；webapp 装载序列抽
  _load_revision_context（Duplicated Code）；suggested_slugs 重复拒绝。
- Spec：qa_count 逐条覆盖校验（工单「逐条 Q&A 的影响结论」落严）；add/remove
  与建议集一致性校验；analyze_impact 畸形输出重试兜底测试补齐。
- 决策留痕：工单正文「Q&A 指纹缓存失效机制直接复用」指设计模式（独立段注入
  + 指纹语义），分析端点未建缓存（验收清单未列；同 Q&A 重复分析成本低，前端
  可提示重跑）；slugs/platform 覆盖入参为前端手动调整入口（05 工单 UI 消费）。

- [ ] 分析 API：输入（上下文 + 新 Q&A）→ 输出（逐条影响结论 + 建议模块集 + 理由），SSE 进度事件（影响分析中 / diff 就绪）
- [ ] 确定性 diff：新旧 slugs 集合差 → 增/删/不变清单（纯函数，可内存直构测试）
- [ ] 平台警告按新模块集重算（复用既有警告逻辑）
- [ ] 假 LLM 测试：结构化输出解析、非法输出重试兜底
- [ ] 影响分析产物与 diff 可回传前端渲染（JSON 形状稳定）
