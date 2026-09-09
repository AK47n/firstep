# 03 — LLM 方案段 + webapp 生成接线

**要做什么：** llm.py 新操作 generate_report_draft（协议 + 提示词 + 结构化解析
{rationale, workflow}，走既有 _retry_parse / 预算底座）；webapp 生成路由在
generate_project 前调用（输入 = 题面 + 功能需求 + 模块摘要 + 引脚表摘要），把输出文本
传 generate 的 report_draft_text；LLM 失败降级 = 空文本（报告照写、LLM 节占位），
生成主链不阻断、不新增失败面；LLM telemetry 照常采集。

**被谁阻塞：** 02（往 generate 的 report_draft_text 参数接线）

**状态：** resolved（2026-08-23） 实施完成 + code-review 双轴评审整改闭环；

## Comments

**实施记录（2026-08-23）：**
- llm.py：REPORT_DRAFT_SYSTEM_PROMPT（方案论证 / 软件流程，workflow 单段约束——
  与 report_draft._split_llm_text 契约配套）+ LLM Protocol 声明 +
  DeepSeekLLM.generate_report_draft（照 reference_judge_archivable 先例：
  _retry_parse + json_mode + _parse_report_draft 严格解析——缺键 / 非字符串 /
  空串拒 LLMError，宁可大声失败也不带病进报告）+ _report_draft_user_prompt
  （题面 / 需求（含句子号）/ 模块摘要 / 引脚表摘要，含小写 json 提示）+
  RoutingLLM 显式方法（恒落 remote，LOCAL_LLM_METHODS 不含本方法）。
- webapp 生成路由（薄壳层）：题面非空时，LLM 调用在 generate_project 前——
  resolve_selection 先取选中模块（非法平台 / slug 在 LLM 调用前 400，不烧
  LLM）→ generate_report_draft → 拼接 report_draft_text（rationale + \n\n +
  workflow，渲染契约）传 generate_project。LLMError → 双 PLACEHOLDER 占位
  文本（报告仍写盘、两节中文占位，spec 失败策略），生成主链不阻断；
  telemetry = create_llm_observation_collector("generate-report-draft") +
  finally recent_llm_workflows.add_completed（照 recommend 路由先例）。
  题面空 = 不调 LLM（无题面无可论证，走缺省路径不写报告文件，旧请求行为
  逐字节不变）。_pin_summary_text：与 README 同源（_pin_rows + _pin_row_text
  行格式单一出处），声明默认值口径（绑定 / 多实例不进素材，docstring 声明）。
- 测试：test_llm.py 5 项（协议 / 缺键拒 / 空串拒 / 重试兜底 / 提示词携带全部
  输入）；test_webapp.py 5 项（LLM 文本落盘 + 输入装配 / 往返契约（论证多段
  原文 + 流程最后一段切回）/ LLM 失败降级占位 / 题面空跳过 / telemetry 记录
  （真 DeepSeekLLM + FakeTransport，workflow_name = generate-report-draft、
  call_count 1、status success））；FakeLLM / RaisingLLM / RecordingLLM 补
  协议方法。全量 2164+ 通过 + mypy 59 文件干净。

**评审整改（code-review 双轴）：**
- Spec：(a) telemetry 补测试钉住（recent_llm_workflows 记录名 / 次数 / 状态）；
  (b) 备注 spec 措辞漂移——「LLMError 降级（空文本 + 占位）」与「报告仍写盘」
  在 generate 的 `if report_draft_text:` 门（缺省空 = 不写）下不可两全，实现
  取「报告仍写盘」读法（webapp 传双 PLACEHOLDER，报告落盘含占位节）；渲染层
  `if rationale else PLACEHOLDER` 兜底保留，防御契约外输入；(c) workflow 单段
  契约 = 提示词软约束（_parse_report_draft 不校验空行），模型违规时
  _split_llm_text 多余段并入论证、最后一段仍为流程——已知软点，留痕。
- Standards（判断项）：(a) 引脚行格式第三处复制 → readme._pin_row_text 单一
  出处（README 表 / 报告表 / LLM 摘要共用）；(b) _pin_summary_text 口径偏差
  （声明默认值 vs 报告侧绑定 / 实例行）——docstring 声明口径，评审认可低风险
  （LLM 素材够用，绑定多为微调）；(c) test_llm json 断言改大小写敏感；(d)
  _report_draft_user_prompt docstring 内 # 残留注释移入函数体；(e) RecordingLLM
  补协议方法；(f) 局部 import（build_manifest_summaries）照 _module_library_
  summaries 既有先例，保持一致。

- [x] llm.py 新操作 generate_report_draft：协议 + 提示词 + 结构化解析 + 重试兜底
- [x] webapp 生成路由接线：调用 → 传 generate；失败捕获降级空文本，生成不阻断
- [x] LLM telemetry / 预算 / 观测照常（复用既有 collector）
- [x] tests/test_llm.py（协议 / 解析 / 重试）+ tests/test_webapp.py（接线 + 失败降级：生成仍成功、报告含占位）
- [x] 全量回归 + mypy 干净
