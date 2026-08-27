# 库外建议方案商量（buy-discuss）

> spec 状态：draft（用户已拍板：提交人 = 用户与 AI 沟通的情报源，评估人 = AI 可行性校核）
> 关联：.scratch/buy-guide/spec.md（推荐阶段选型参考面板，工单 01-02 已 resolved）
> 决策记录：用户原话——「这一步要增加跟 AI 的沟通 他要能够沟通之后能改变方案 不然这个就已经锁死了必须要买当中的一个了 万一用户有其他想法呢」「用户的方法只是他的猜想，AI 校核一下这个是不是真的可行并且跟用户进一步沟通」；持久化 = 记住 + 进生成上下文（用户选中推荐项）。

---

## 一、问题陈述

选型参考面板（buy-guide/02）已经给出词表方案 + 推荐/AI 建议双徽标，但：
1. **用户不能与 AI 沟通**：学生的情况（手头已有模块、学校仓库现货、场地限制）无处表达；AI 给的建议可能不贴合实际。
2. **AI 建议变相锁死**：`selected` 只有一个，学生若另有想法（词表外/二手模块/特殊接口）只能吞掉，或买了之后在任务卡补充框里补（延迟到写码阶段才沟通，太晚——买之前该决策）。
3. **买件决策不沉淀**：学生和 AI 商量好的结论（词表内某款 / 自定想法）没有载体，重新推荐/刷新即丢；生成后任务推进/深化写码时 AI 不知道用户已定什么。

目标：在**买之前**完成「商量 → 校核 → 确定」，结论**记住**并**流进生成后写码上下文**。

## 二、方案

### 2.1 讨论入口与形态

- 选型参考面板（`.sugg-panel`）底部加「**和 AI 商量**」按钮 → 面板内展开对话区（附着在该库外建议上——与任务卡补充框同哲学：对话挂在对象上，不是无根聊天）。
- 多轮：每轮用户发消息 → 一次 LLM 调用回复（含审核意见）→ 历史数组前端积累，下一轮全量带上（题面/需求句/平台/词表方案/历史）——与推荐收敛循环同哲学（上下文对齐、不猜）。
- 对话上限 **8 轮**（预算/费用防线）：第 8 轮后按钮变「总结并确定」——AI 输出终局建议，未确定也能关（结论可选）。

### 2.2 AI 校核（用户想法的可行性审核）

- LLM 协议新方法 `discuss_buy_options(problem_text, requirement, platform, solutions, history) -> {reply, review?}`：
  - `reply`：本轮回复文本（多轮对话的解答/追问）。
  - `review`：**仅当用户最新一轮提出新的自定方案**（词表外想法）时给出 `{verdict: feasible|risky|infeasible, reason, suggestion}`——AI 校核该想法对本赛题是否可行（接口/电压/资源/题面对症），`suggestion` 可指向词表更优方案（比对）。
- 立场：**AI 是顾问不是裁判**——`verdict` 是风险意见，最终仍用户拍板（用户原话「万一用户有其他想法呢」不能被锁死）；面板明确展示「AI 审核：可行/有风险/不可行 + 理由 + 建议」。

### 2.3 结论确定与持久化（记住 + 进生成上下文）

- 讨论中/后，用户点「**就用这个**」（词表方案行）或「**就用我提的**」（自定文本行，带 AI 审核意见）→ 结论 = `SuggestionDecision{source: wordlist|custom, name, note, verdict?}`。
- 结论三处生效：
  1. **前端 state**：`suggestion.decision` → chip 徽标「✓ 已定」。
  2. **localStorage 记住**（draft-memory 先例）：键 `buy-decisions`，按建议 `name`（类别降级名）匹配恢复——重推/刷新/换题面不丢。
  3. **进生成上下文**：结论随推荐载荷 `requirements[].suggestions[].decision` 上行（生成请求已带 requirements）→ 落 `.contest_context.json` → 任务推进/深化提示词的 requirements 段自动带「（已定：…）」。

### 2.4 上下文注入（提示词）

- `plan_tasks` / `execute_task` / 深化的需求段装配函数（`_requirement_lines` 系）：库外建议带 `decision` 时追加注记：
  - wordlist：「（已定：<方案名>，<价格/接口>）」——选型确定，写码照此；
  - custom：「（已定：<自定文本>，AI 审核：可行/有风险/不可行）」——自定接口信息由用户描述承载。

## 三、用户故事

1. 学生点开「遥控接收」选型参考 → 点「和 AI 商量」：「我们仓库只有红外和 NRF24L01，场地阳光强」→ AI：红外怕强光（建议遮光罩或不选），NRF24L01 更稳但需 SPI 自写驱动，价格差距小 → 学生点「就用这个」（NRF24L01 行）→ 徽标 ✓ 已定；任务推进时 AI 自动知悉已定 NRF24L01。
2. 学生有旧 HC-SR04：「我想用仓库里旧 HC-SR04」→ AI 校核：可行（GPIO trigger/echo，库内 filter 已有回响读法），注意 5V 回波分压 → 点「就用我提的」→ 自定结论进上下文。
3. 学生提 ESP8266 遥控 → AI 校核：可行但延迟 ~100ms 且需自建 AP，现场恐来不及，建议词表「NRF24L01 遥控（含手柄）」→ 学生改选词表款。
4. 学生不讨论直接跳过 → 全部旧行为不变（solutions 空/无 decision 的 chip 原样）。

## 四、实现决策

1. **一轮一请求（同步 JSON）**，非 SSE 流式——回复结构小、无进度语义；telemetry 照常采集（llm_telemetry 事件 + recordLLMUsage，与推荐/任务一致）。
2. **review 识别**：LLM 判「用户提出的某个方案名/文本不在词表 solutions.name 内」即出 review；词表内方案讨论不出 review（仅 reply）。
3. **持久化只在浏览器端**（localStorage，draft-memory 先例），服务端不存；不做已购清单页。
4. **结论不阻断**：verdict = infeasible 仍允许用户确定（顾问非裁判，UI 明确标注 AI 意见）。
5. **对话上下文**：题面（_truncate_content）+ 需求句 + 平台 + 当前建议整体（name/examples/方案清单）+ 历史逐条（_truncate_content + 条数上限 = 对话轮上限 8）。
6. **词表仍人工维护**：讨论不改词表、不生成方案文本（宁缺毋编不变）；自定文本只承载用户自己输入。
7. 复用预算原语：discuss 单轮请求体有 wire 预算兜底（取 SELECT 同款常量的段级截断，防超长历史/题面撑爆）。

## 五、测试决策

- `tests/test_llm.py`：discuss_buy_options 协议签名 / DeepSeek 解析（review 可选、verdict 词表外修正）/ RoutingLLM 转发 / prompt 含历史与方案清单 / 预算截断。
- `tests/test_selection.py`：SuggestionDecision to_dict 与缺省（无 decision = 旧载荷逐字节）；`_suggestion_line`（或 `_requirement_lines` 扩展）带 decision 注记两形态。
- `tests/test_webapp.py`：POST /api/buy/discuss 端点（payload 校验 / 历史 / 响应 / 错误）。
- `tests/js/discuss.test.mjs`（或并入 recommend.test.mjs）：对话区渲染纯函数 / 审核徽标三态 / 已定徽标 / localStorage 读写纯函数。
- 全量 pytest + JS 绿；浏览器 E2E（拦截式）：讨论一轮 + 确定 → 徽标 → localStorage 落键 → 生成上行载荷含 decision。
- 中文 commit。

## 六、范围外（明确不做）

1. 已购清单页/管理表/勾选持久化 UI（localStorage 记忆即止）。
2. 服务端多用户存储/同步。
3. AI 自动改词表、自动生成方案文本（方案知识仍只来自词表 + 用户自述）。
4. 购买链接/下单/比价。
5. 结论反向改推荐模块选择（买件决策不反向影响模块集）。
