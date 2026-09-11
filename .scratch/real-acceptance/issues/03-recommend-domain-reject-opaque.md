# 03 — 推荐域拒绝（SelectionError）被吞成通用话术且免重试：一次模型手滑 = 整次推荐终态失败

**要做什么：** 让「域拒绝」的**真实理由**到得了用户眼前，并给一次可恢复的机会——
现状是 `kind=client` 直接 break 掉重试循环 + `errors.llm_error_message` 的 client
分支统一换成一句通用话术，于是「模型给不支持多实例的模块带了 instances」这种
**一轮就能自愈**的手滑，变成了用户看到的「AI 服务拒绝了本次请求（可能是 API key
无效、账户余额不足或请求内容不被接受）」。

**被谁阻塞：** 无。

**状态：** resolved（2026-09-17 第十七轮落地，文案 + 带理由重试；修复方向 ③ 仅完成评估、留决策点，见文末「实施记录」）

## 真机现场（2026-09-10 第十六轮 A8/C5 实测；同一形态反复出现）

探针 `.scratch/recommend-domain-reject/probe-16-recommend-live.py`（内存注入诊断行，
磁盘 `src/` 零改动）跑真实推荐，捕获到的被吞掉的真实理由：

| 题 | 真实理由（`SelectionError`） | 表面所见（用户） | 次数 |
|---|---|---|---|
| 2026H / mspm0 | `模块 huidu 不支持多实例，不能带 instances` | 「AI 服务拒绝了本次请求（可能是 API key 无效、账户余额不足或请求内容不被接受）」 | 1 |
| 2026H / mspm0 | `模块 oled 不支持多实例，不能带 instances` | 同上 | 1 |
| 2026C / stm32 | `模块 k230 不支持多实例，不能带 instances` | 同上 | 1 |
| 2022C / stm32 | `库外建议的硬件名不在硬件词表中：红外对管循迹数组` / `红外测距传感器` / `TI MSPM0 主控板` | 同上 | **3 次连续** |
| 2026F / stm32 | `模块 adc 不支持多实例，不能带 instances` | 同上 | 1 |
| 2021F / stm32 | `库外建议的硬件名不在硬件词表中：称重传感器` | 同上 | 2 |
| 2024H / stm32 | `库外建议的硬件名不在硬件词表中：直流减速电机 + TB6612 双路驱动板` | 同上 | 1 |

现场证据：`.scratch/recommend-domain-reject/verify-16-*.txt`（每条的 `[PROBE16][域拒绝]` 行）、
`.scratch/real-run/verify-16-A8-stm32-2026C.txt`（首次真机现场）、
`.scratch/real-run/verify-16-recent-workflows.json`（遥测：`http_status=200` /
`parse_status=parse_error` / `error_kind=client` / `attempts=1`）。

## 为什么这是缺陷（而不是「模型的问题」）

1. **理由被丢掉**：`llm.py:1953` 把 `SelectionError` 译成 `LLMError(kind="client")`，
   `errors.py:192-198` 的 client 分支**不看 message**，一律换成 `LLM_CLIENT_MESSAGE`。
   用户拿到的建议（查 key / 查余额）与真实原因（模型给 oled 写了 instances）**毫无关系**
   ——这是误导性文案，不是「技术串被去技术化」。
2. **可自愈的失败没有自愈机会**：这类拒绝是模型输出的**概率性手滑**
   （同一题反复跑：2022C 第 3 次才成功、2026H 第 2 次才成功、2022C 三轮全挂在同一个
   词表名上），而同参数重试**经常就过了**（本轮实测 6 次尝试里 2 次 done）。
   但 `_retry_parse` 对 `client` 直接 `break`（`llm.py:2219-2222`），一次手滑 = 整次
   推荐终态失败，用户只能自己再点一次。
3. **工单 selects-domain-reject/01 的原判据值得复核**：当时理由是「同参数重试模型稳定
   输出同样的幻觉（2021F 实测 digit_uart 连续 5 轮同样带 instances）」——本轮 2022C
   的现场是**同一题三次三个不同的词表名**（`红外对管循迹数组` → 同上 → `TI MSPM0 主控板`），
   即「稳定复现同一幻觉」的前提并不总成立。

## 修复方向（三选一或组合，实施会话定）

1. **文案（最小改动，必做）**：client 分支改为「带原始理由」——`LLM_CLIENT_MESSAGE`
   只在「上游 4xx」时使用；**域拒绝类**（产品自己判的）保留 `LLMError.message`
   （即 `SelectionError` 原文，如「模块 oled 不支持多实例，不能带 instances」），
   并按需加一句人话引导（例如「这是模型输出与库内事实冲突，可直接重试」）。
   判据：`errors.py` 能区分「上游 HTTP 4xx」与「本地域判决」，不靠字符串猜。
2. **可恢复性**：给域拒绝一次（或两次）重试机会——重试请求里**带上被拒理由**作为
   追加指令（「上一轮你的输出被拒：<理由>；请修正后重出 JSON」），比空转重试有效；
   上限 1 次，避免烧钱循环。
3. **降级而非拒绝（词表闸专属）**：`selection._parse_suggestions` 遇到词表外硬件名时，
   现行文案已提示「词表外型号请降级为词表内的类别名」，但**判定是拒收**——
   可考虑确定性降级（能反查到类别行就落到类别名并标注「AI 给的型号不在词表，已降级」），
   把「拒收」留给真正无法归类者。注意：这会改动 `SelectionError` 的既有语义边界，
   需先确认与 `wordlist.py` / 买件指引链路的口径一致。

## 实施记录（第十七轮）

### ① 文案：kind 分流（改前红证 → 改后诚实）

- `llm.py` 新增类别常量 `ERROR_KIND_DOMAIN = "domain"`（与 `client` 并列，
  词表单源），域拒绝翻译点 `llm.py` 里 `raise LLMError(str(exc),
  kind=ERROR_KIND_DOMAIN)`——**不再借道 client**。
- `errors.llm_error_message` 新增 domain 分支：保留 `LLMError.message` 原文
  （`AI 生成的推荐内容与库内事实冲突：模块 oled 不支持多实例，不能带
  instances（这是 AI 输出与库内容对不上，不是登录凭据或账户问题——系统已
  自动重试 2 次仍不通过。请再点一次推荐…）`）；client 分支一字未动（上游
  4xx 仍是「核对 API key / 余额」——那条建议本身没错，错的只是拿它描述域拒绝）。
- 红证（`tests/test_errors.py`，表驱动两分支）：域拒绝分支断言含真实理由 +
  不含通用建议；上游 4xx 分支断言仍是 `LLM_CLIENT_MESSAGE` 语义。
- 判据达成：`errors.py` 区分「上游 HTTP 4xx」与「本地域判决」靠 **kind**，
  不靠字符串猜。

### ② 可恢复性：带理由重试 1 次

- `_retry_parse` 新增 `domain_retry` 开关（**只有 select_modules 打开**，其余
  调用方对域拒绝照旧立即结束——零变化）+ 新常量 `DOMAIN_RETRY_LIMIT = 1`：
  首轮域拒绝 → 第二次请求的 user 消息追加 `DOMAIN_FEEDBACK_SEGMENT`
  （「上一轮输出被拒绝…拒绝理由：<SelectionError 原文>…不要重复同样的输出」，
  拼在末尾离生成点最近）→ 通过即本轮自愈；仍失败照旧耗尽。
- 上限 1 次防烧钱循环；「同参重试稳定同错」的旧判据（select-domain-reject/01）
  已被现场推翻（2022C 同题三次三个不同错处），带理由重出而非空转重试。
- 红证（`tests/test_llm.py`）：`test_select_domain_rejection_retries_once_with_
  reason_then_succeeds`（首轮拒 → 次轮过，并钉住第二次请求真的带上了理由）、
  `test_select_domain_rejection_retry_is_capped_at_one`（上限）、
  `test_select_domain_retry_observation_records_domain_kind_and_attempt_pair`
  （遥测：两次调用各一条观测 `error_kind=domain`、`attempts=1/2`——不再像
  现场那样看起来是「一枪毙命」）。
- 既有两条用例随新契约更新：`test_select_modules_rejects_hallucinated_module_
  even_with_library`（断言 kind=domain）、`test_select_modules_rejects_
  instances_without_multi_instance_capability`（改为两次相同输出）。

### ③ 词表闸「降级而非拒收」——评估（**未改行为，留决策点**）

评估探针：`.scratch/recommend-domain-reject/probe-17-wordlist-gate-verdicts.py`
（只读，把第十六轮现场五个被拒名逐条过现行判据 `selection._solution_group`，
再对词表的「类别名 / 型号名 / 选购方案名」三类取值域做归属判定）。实测输出：

| 被拒名（现场） | 是类别名 | 是型号名 | 是选购方案名 | 是某方案名的去括号裸名 |
|---|---|---|---|---|
| 红外对管循迹数组 | 否 | 否 | 否 | **是**（感知传感器：红外对管循迹数组（低价替代）） |
| 红外测距传感器 | 否 | 否 | 否 | **是**（感知传感器：红外测距传感器（GP2Y0A02YK0F）） |
| 直流减速电机 + TB6612 双路驱动板 | 否 | 否 | **是**（执行机构，逐字） | 是 |
| 串口摄像头（JPEG 输出 UART 转接） | 否 | 否 | **是**（视觉模块，逐字；第十七轮 2026H 现场新增） | 否 |
| 称重传感器 | 否 | 否 | 否 | 否（词表只有方案「HX711 称重传感器（压阻半桥）」） |
| TI MSPM0 主控板 | 否 | 否 | 否 | 否（词表无「主控板」类别，无任何方案） |

证据：`.scratch/recommend-domain-reject/verify-17-wordlist-gate-verdicts.txt`
（探针只读复跑输出）。

**结论（推翻了工单里「词表闸在做分类判断」的隐含假设）**：六个被拒名里
**四个**不是模型幻觉，而是**词表内部口径不对齐**——合法 name 取值域 =
类别名 ∪ 型号名（`_solution_group` 单源），而**选购方案名不在其中**；模型
恰好见了 `format_wordlist_prompt` 送出的「选购方案：…」段（段里只列方案名），
就照着说了（第十七轮 2026H 现场抓到的「串口摄像头（JPEG 输出 UART 转接）」
就是**逐字照抄提示词里的方案名**，这条把因果关系钉死了）。换言之：**提示词
把方案名摆在模型眼前，闸却只认类别 / 型号名**——这是三处口径（提示词科普段 /
合法 name 取值域 / 买件指引的选购方案）不一致的产物，不是「模型不懂硬件」。

**因此「降级而非拒收」不建议做成模糊降级**（把不认识的名字硬塞进某个类别）：
硬件建议直接落进买件链路（`_solutions_for` → 选型参考面板 → 用户照单采购），
类别错配是实质风险（买错件），而模糊降级恰恰在最需要准确的场合猜。三条更省的
路子（都需要先定语义，故本轮**只留决策点、不动 `SelectionError` 语义**）：

- **B1 数据口径对齐（首选，零语义改动）**：既然方案名就是「这一类里推荐买什么」，
  就把高频方案名的**裸名**登记进对应词表行的 `models`（如「红外对管循迹数组」
  → 感知传感器 models，「直流减速电机 + TB6612 双路驱动板」已在 `执行机构`
  → 它其实已是方案名，登记为型号即可），并补「主控板」「称重传感器」这类
  真实存在但词表缺失的类别。判据：**被拒名是否真的是电赛会买的硬件**——
  是 → 补词表（词表本来就是可手补的领域知识，`wordlist-lib-modules/01` 已开过
  这类先例：红外对管那条方案就是那时补的）；不是（如「TI MSPM0 主控板」是
  平台本身、库内已有）→ 拒收正确。
- **B2 把「方案名」纳入合法 name（小语义扩展，需确认）**：命中某行任一
  `solutions[].name` 或它的去括号裸名 → 视同该行类别名，`degraded=True`
  展示「AI 给的名称不是类别 / 型号，已归到该类别」。风险：方案名是**导览文本**
  （「LED + 蜂鸣器 声光组合套件」「车模自带驱动板（整车/轮组+驱动成品）」），
  当 name 展示会出现「chip 名 = 一整句话」的形态；且判据会变成两套（name 域
  与 solutions 域），买件指引面板会同时把同一句话显示两遍。
- **B3 保持拒收**（现状）：代价是这类失败继续消耗一次推荐（现已自愈 1 次，
  且失败文案诚实），且会**反复**发生在同一个题（2022C 三次同一类名字）。

**决策点（需人确认后再开单，本轮不动）**：`wordlist.json` 里 `solutions`
的语义边界——是「可购买的推荐选项（导览文本）」还是「库外建议 name 的合法取值
（领域名词）」？

- 若答案是前者 → 走 **B1**（补词表数据；必要时加一条结构测试：现场被拒名不得
  再出现），`SelectionError` 语义零改动。
- 若答案是后者（方案名也算「厂商 / 品类专名」）→ 走 **B2**，届时需要同步改
  `_solution_group` 判据单源 + `OutOfLibrarySuggestion.degraded` 的展示文案
  （`fx/recommend.js` 的「（型号不在词表，按类别展示）」）+ 工单口径。
- 两路都不包含模糊匹配 / 跨类别猜测——**降级只允许确定性反查，猜不出就拒收**
  （与现有「词表外型号 + 模型给出词表内 category 才降级」同一条保守线）。

回归锚（无论走哪条路都已被测试钉住）：`tests/test_selection.py::
test_build_selection_solution_name_is_not_a_legal_suggestion_name`——当前
行为（方案名不入合法 name → 拒收）是显式契约，改 B2 时这个用例应当红着被改。

### ④ 双轴评审整改（Standards + Spec，落地后跑）

- **文案不报重试次数**（Spec 轴「看似实现但实现有误」）：原实现用
  `DOMAIN_RETRY_LIMIT + 1` 格式化成「系统已自动重试 2 次」，而用户感知的重试
  只有 1 次（且将来 `domain_retry=False` 的调用方会被谎报）。改为
  「系统已自动重试仍不通过」——**文案不承载可变量**，测试加两条反向断言。
- **前端错误类别词表补 `domain`**（Standards 轴 Shotgun Surgery）：
  `fx/llm.js` 的 `errLabels` 缺项会让设置页遥测显示「错误 domain」；
  补「域拒绝」+ `tests/js/llm-telemetry-format.test.mjs` 一条断言。
- **单源口径统一**（Standards 轴）：`errors.llm_error_message` 的四条分支
  全部改用 `llm.ERROR_KIND_*` 常量（原来只有新加的 domain 用常量、兄弟分支还在
  比裸串）；文件头的 kind 词表注释同步补 domain。
- **CONTEXT.md 补词表**（Standards 轴「领域词表要更新」）：「错误映射」行补
  `LLMError.kind` 分派口径（client=上游 4xx / domain=本地域判决），「收敛循环」
  行补域拒绝带理由重试与**重试预算按调用算**的事实。
- **注释纠偏**：`DOMAIN_FEEDBACK_SEGMENT` 原注释说模型「看得见自己上一轮的
  输出」——实际 `_retry_parse` 只带 system + user（不重发被拒输出），注释改为
  实话（模型靠理由自己定位改哪里）。
- **探针产物不再污染历史证据**：`--out-prefix`（缺省 `done-16` 仍写老名字，
  复跑必须显式给 `done-17`）；本轮误覆写的 `done-16-2022C-stm32.json` 已
  `git checkout` 复原。
- **测试去重**：三条域拒绝用例共用的 payload 提成模块常量 `DOMAIN_REJECTED_JSON`
  （与 `SELECTION_JSON` / `REQUIREMENTS_INSTANCES_JSON` 同规）；去掉未用的
  `caplog` fixture。

**评审提出但本轮不改的（记在这里，不是漏项）**：`kind=client` 里仍混着两处
**本地**失败——输出超长守卫与 max_tokens 截断（前者文案已专门、后者被 413 兄弟
分支之外的通用话术换掉）。它们不是域判决，不该借 domain；要治得给「本地失败」
单开一类或让截断走专属分支，属另一张单的范围（本单口径 = domain / client 二分）。

## 验收标准

- [x] 红证：对上述任一条现场文本（探针已留档）跑现状路径 → 用户可见文案是通用话术；
      实施后同输入 → 文案含真实理由（如「oled 不支持多实例」）
      —— 改前形态由 `client` 分支的 `LLM_CLIENT_MESSAGE` 直接可得（`errors.py`
      该分支不看 message）；改后契约见 `tests/test_errors.py` 两条域拒绝用例
      （含真机原文端到端一条）。
- [x] 域拒绝有 ≥1 次带理由的重试；`tests/test_llm.py` 覆盖「首轮域拒绝 → 次轮修正通过」
- [x] 全量 pytest 绿；`errors.py` 的契约测试补「域拒绝 vs 上游 4xx」两分支
      （两分支为两条独立用例，非 parametrize——同一种 LLMError 只换 kind，判据在 kind）
- [x] 真机：2022C / 2026H 各跑 1 次不再出现「查 key / 查余额」误导文案
      —— **如实记录**（评审整改：原措辞"两项都出现域拒绝现场"不成立）：
      2022C / stm32 本轮两次实跑**一次域拒绝都没有**（一次 done、一次补问收尾），
      因此它证明的是「没有出现误导文案」，**不构成域拒绝路径的证据**；域拒绝路径
      的证据全部来自 2026H / mspm0（见下节）。两题的终态文案里通用话术出现 **0 次**。
- [x] 修复方向 ③（词表闸降级）完成**评估**并留决策点（本节）

## 真机验收（第十七轮）

命令：`python .scratch/recommend-domain-reject/probe-16-recommend-live.py
--topic <题> --platform <平台> --attempts <n> --out-prefix done-17`
（探针走产品自己的 `run_recommendation`；注入锚点已随 kind 改名同步更新；
`--out-prefix` 是评审整改补的——缺省 `done-16` 会覆写第十六轮现场件，
本轮已用 `git checkout` 复原被覆写的 `done-16-2022C-stm32.json`）。

| 题 / 平台 | 域拒绝现场 | 结局 |
|---|---|---|
| 2022C / stm32（第一次：`verify-17-recommend-2022C-stm32.txt` 首版，被第二次覆盖） | 0 条 | done，收敛轮次 [1, 2] |
| 2022C / stm32（第二次，现行日志） | 0 条 | 补问收尾（终态 question，轮次 [1]）——**未触达域拒绝路径** |
| 2026H / mspm0（`verify-17-recommend-2026H-mspm0.txt`） | **6 条**（k230 / xunji / ntb_time / 红外对管循迹数组 / 串口摄像头…，跨 3 次尝试、3 个收敛轮） | 4 条被带理由重试**接住**（未成终态）、2 条重试后仍拒 → 终态 exception，文案带真实理由 |

2026H 的关键行（逐字）：

```
[PROBE16][域拒绝] SelectionError → 模块 k230 不支持多实例，不能带 instances
[PROBE16][域拒绝] SelectionError → 模块 xunji 不支持多实例，不能带 instances
[PROBE16][重试耗尽] LLMError kind= domain | 模块 xunji 不支持多实例，不能带 instances
[PROBE16][编排抛错] LLMError: 模块选择连续 2 次调用失败：模块 xunji 不支持多实例，不能带 instances
```

**探针口径限制（评审整改显式记录）**：探针打印的是**异常本体**（`str(exc)`），
不是 `errors.llm_error_message` 渲染出的**用户可见文案**——「文案带真实理由」
这一步是**代码追踪 + 单元测试**证明的，不是这份日志证明的：

- 链路：`LLMError(kind=domain)` → `error_entry`（`errors.py` 表 502 行）→
  `llm_error_message` 的 domain 分支（保留 message 原文）→ webapp
  `_error_message`（`error_entry(exc)[1]`）→ `run_sse(run, error_message=…)`
  推给前端；
- 端到端用例：`tests/test_errors.py::
  test_llm_error_domain_exhausted_real_machine_reason_survives`——输入就是上面
  「重试耗尽」那行原文（`kind=domain`），断言用户可见文案含「xunji 不支持多实例」
  且不含「核对 API key」。

**域拒绝重试的实际效果（如实记录，非全胜）**：2026H 三次尝试里 4 条域拒绝被
重试接住（模型换了个说法/改对了），2 条重试后仍被拒——即「一次手滑 = 整次推荐
白跑」的比例下降但不是零，且**重试预算按调用算**（收敛循环每轮各一次），
一次推荐最坏可多花 ≈ 轮数 次调用（第十六轮那种"一次就跑完"的题不受影响）。



## 附：本轮的量化背景（供排期参考）

第十六轮 C5 + A8 一共跑了 **14 轮真实推荐**（含重试），其中 **9 轮**因域拒绝终态失败
（64%）——即「推荐点一次能成的概率」在本机当前模型下明显偏低，而失败文案还指错了方向。
