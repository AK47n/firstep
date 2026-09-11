# 05 — 推荐/澄清请求预算：文档口径与真机实测不符（余量比账本记的小一半）

**要做什么：** 把 `budget.py` / `llm.py` 注释里的「最坏形态 ≈119.5KB」账本与**真机实测**
对齐，并在请求体贴边时给出可判读的信号（而不是靠上游 4xx 才发现）。

**被谁阻塞：** 无。

**状态：** resolved（2026-09-17 落地：段级账本可执行 + 统一余量单源 + 段级重分配）

## 真机现场（2026-09-10 第十六轮 C1 探针实测）

探针 `.scratch/recommend-vision-qa/probe-16-clarify-vision.py` 在 Transport 层记账
（`verify-16-C1-clarify-vision.json` 的 `request_sizes`）：

| 请求 | 实测字节 | 与上限 `MAX_REQUEST_BYTES = 128*1024 = 131072` 的关系 |
|---|---|---|
| 2021F select（清单行 + 词表 + 题面 + 契约，**无**澄清历史/参考全文） | **122161** | 余量 **8911 字节（6.8%）** |
| 同上 + 一段澄清历史（视觉答案「30cm」并入后） | **124475 / 124525** | 余量 **6.5KB / 6.5KB** |
| 同题 + 参考全文段（模型点名回读后） | 曾实测 **149674 → 被预检拒发** | 超限 |

`budget.py:104-119` 的推导写着「最坏形态总量 ≈119.5KB，余量 ≈10.7KB ≥ 10KB」——
**真机基础形态就已经 122.1KB**（还没加全文段），说明账本漏算了某一段（最大嫌疑：
`MODULE_SUMMARY_BYTES` 段与契约/词表段的 `ensure_ascii` 膨胀，或 86 条瘦身行 +
多实例规则段 + 同组互斥段的条件段叠加）。

## 后果

1. 「预算文档说有余量、实测贴边」→ 后续任何**加一段提示词**的改动（新条件段 / 新字段）
   都会先撞 128KB，表现为用户看到「请求体过大」或「AI 服务拒绝了本次请求」（若上游 4xx）。
2. 本轮已实测到一次真实超限拒发（149674 字节），发生在模型点名读参考全文之后——
   该路径的段级预算（`REFERENCE_FULLTEXT_BYTES = 27000`）在**基础形态已经 122KB** 的前提下
   不可能再塞进 27KB，属**账本失效**而非偶发。

## 修复方向（实施会话定，红证先行）

1. **复算账本**：把 `budget.py` 的最坏形态推导改成**可执行**的形式（结构测试按段拼出
   最坏载荷并断言 ≤ 上限 − 目标余量），而不是注释里的手算；实测基线用本轮的真机数字。
2. **段级预算重分配**：基础段（清单行 + 词表 + 题面 + 契约 + 条件段）先扣，剩余才给
   参考全文 / 澄清历史；`REFERENCE_FULLTEXT_BYTES` 与 `CLARIFICATION_HISTORY_CAP`
   随实测重新取值（现 27000 字节在 2021F 这种 86 条全量清单下已无空间）。
3. **可判读信号**：接近上限（如 ≥90%）时在 telemetry 里留痕（`sanitize_llm_usage`
   同一观测面），并在被拒时把「哪一段占了多少」写进日志——现在只有一个总字节数。

## 验收标准

- [x] 红证：结构测试按真实库（86 条 stm32 摘要行）+ 2021F 题面拼最坏载荷 → 现状超/贴边；
      实施后 ≤ 上限 − 目标余量
      —— **红证实测**：HEAD 真实库最坏形态 mspm0 **128405B / 余量 619B**（带生产
      必带的预筛注记；不带注记 128296B）。"账本 ≈119.5KB" 与此差 6KB+，且那 119.5KB
      其实是**修复侧**的数被推荐侧引用了。实施后 **125476B / 余量 5596B**（mspm0）、
      **124856B / 余量 6216B**（stm32），均 ≥ 统一余量 2048B。
- [x] 真机：2021F 真机推荐（含澄清历史与参考全文注入）不再出现「请求体过大」
      —— `verify-05-recommend-2021F-stm32.txt`：**终态 done、4 轮收敛**
      （`[1, 2, 3, 4]`，走完澄清历史注入路径）、10 模块、多实例猜测正常、
      全程无「请求体过大」。另静态复算了第十六轮那条被拒发路径
      （模型点名回读全文 149674B → 125476B；手动选三篇大参考 → 102274B）。
- [x] `budget.py` 注释里的推导被实测数字替换（口径可追溯：注明取值来源与本轮证据文件）
      —— `REFERENCE_FULLTEXT_BYTES` 与 `FIX_CONTEXT_TOTAL_BYTES` 两处注释改为
      实测值 + 证据文件路径（`.scratch/real-acceptance/verify-05-segment-budget.txt`）；
      并**删掉**了「最坏 ≈119.5KB / 余量 ≥10KB」这条被误引用的修复侧数。
- [x] 全量 pytest 绿（`tests/test_llm.py` 的 `test_fix_prompt_worst_case_fits_request_budget`
      同族预算测试同步）
      —— **3958 passed**；`node --test tests/js/*.test.mjs` **1430 pass / 0 fail**。

## 实施记录（2026-09-17）

### 一、根因：不是「漏算了哪一段」，是三种记账病

工单原假设「账本漏算了某一段（最大嫌疑 ensure_ascii 膨胀 / 条件段叠加）」。实施时的
段级实测证伪了这个假设——是**三种各不相同的病**：

**① 账本的数来自别的请求线。** 「最坏形态总量 ≈119.5KB，余量 ≈10.7KB ≥ 10KB」写在
`FIX_CONTEXT_TOTAL_BYTES`（**修复侧**）的推导注释里，被推荐侧当依据引用了很久。
推荐侧真实库最坏形态是 128405B——**差 6KB+**，而且推荐侧从来没有满足过那个 10KB。

**② 两个自设余量并存，且都没说清为什么。** select 两处写 2KB、fix / skeleton /
clarify 写 10KB。实际读法是「它们互不知情」：推荐侧被词表段十五次逐批增长一路啃到
2KB，另三条线没跟着动。本单把余量收敛成**单源** `budget.REQUEST_RESERVE_BYTES = 2048`
——取 2048 而不是 10KB 的理由写在该常量 docstring 里（取 10KB 等于把断言改到红，
不是把请求改小；10KB 是修复侧的历史遗留，推荐侧从没满足过）。

**③ 「最坏形态」一直比生产少算 109B，而且结构性漏算了一整个库形态。** 预筛注记
（webapp 预筛发生时告知模型清单不是全量）是**生产必带**的，而两条结构测试都不带。
更要紧的是：合成结构测试用固定 14 条假摘要 + 写死的短简介，实测 **94196B**，比真实库
形态（86 条摘要行吃满 `MODULE_SUMMARY_BYTES=40000`）**小 34KB**——它此前在文档里自称
「唯一硬保证」，实际上**不是上界**，真正绑定的那条是 `test_recommend_real_library_budget`。
（注：真实运行里注记**不一定出现**——2021F/stm32 真机是「86 条，截断=False，note=''」，
因为 stm32 全库摘要 28KB 装得进 40000 预算；mspm0 才会截断出注记。所以结构测试按
带注记 + 43 条截断形态构造，对两个平台都取到上界。）

### 二、顺带挖出的两个真缺陷

**②-a 段级预算不是实发上界（单篇形态）。** `_fit_segment_wire` 的 docstring 写着
「标注自身的 wire 字节计入预算」，实现却是**先 fit 到预算、再补标注** → 返回值超出
预算约 **281B**。后果不是「差几百字节无所谓」：段级预算因此**不是实发上界**，段级
账本永远对不上实发（实测候选清单段声明 4096、实发 4379），只能靠「约等于」打圆场
——正是本单要治的账实不同源。已改为与 `_wordlist_prompt_segment` 同款（**先预扣
标注再 fit**）；并补护栏：预算连标注都装不下时**原样返回**，绝不返回比预算更长的
内容（那是同一类病的另一面）。

**②-b 全文段预算是「逐篇」而不是「合计」——规格评审抓出的真缺口（最隐蔽的一处）。**
`_selection_user_prompt` 对**每一篇**全文各自 `_fit_segment_wire(fulltext)`
（预算 = 本常量），而篇数**不受任何段级约束**：模型可点名多篇，调用方也可给多篇
（`generator.build_reference_fulltexts` = 手动 ∪ 全部锚定 id，逐文件只受
`REFERENCE_FILE_CAP = 20000` 字符约束 ≈ 120KB wire）→ **N 篇 = N × 预算**。

改前实测：4 篇满额 = **125634B**，再加篇数即越界；而单篇夹具下账本看起来完全正常
——段级账本在**单篇形态**下是上界，在**多篇形态**下不是。这正是本单要治的病的最隐蔽
形态（账本与实测不同源，且只在特定形态下暴露）。

已改为按篇数均分合计预算（`_reference_fulltext_total_budget`，与骨架侧
`SKELETON_REFERENCE_TOTAL_BYTES` 同款做法），两个注入路径（`reference_fulltexts` /
`manual_fulltexts`）都过；单篇形态逐字节等价（既有用例零变化）。改后：4 篇满额
125476B → **37535B**，10 篇亦 37535B 量级（篇数涨而总量不涨，那才是「合计预算」）。
回归测试：`test_fulltext_segment_budget_is_aggregate_not_per_reference`。

### 三、重分配（基础段先扣，余量才给可裁段）

按工单「修复方向 2」的顺序做，但**用实测值而不是估算**（清单行字节是库驱动的，
这正是旧账本手算「14 条 ≈7.6KB」与真实 40KB 差 32KB 的病根）：

```
上限 131072 − 统一余量 2048                          = 129024
− 基础段 63341（题面 4000 中文 + 已预筛清单行 + 预筛注记 + 输出契约）  ← 不可裁
− 条件规则段 3725（多实例 1222 + 同组互斥 618 + 题面核查 1885）      ← 不可裁
− system 提示词 5705 − JSON 壳 86                     = 56167
− 词表段预算 12150 − 候选清单段预算 4096               = 39921
− 澄清历史段实测形态 15438                            = 24483
→ 参考全文段（含段壳 ≈158）取内容 23400 → 账本用满 128099 ≤ 129024（余 925B）
```

（全文取 24400 时段级账本用满 129099 **超上限 75B** —— 23400 即当前基础段下的可行上界。）

**「先扣」是怎么落地的（如实说明）**：生产代码里**没有**运行期「剩余量再分配」的
逻辑——落地形态是**常量按实测重取 + 一条可执行的账本断言**：账本等式
（Σ段 + JSON 壳 = 实发）与用满口径不等式（基础段 + 各段级预算 ≤ 上限 − 余量）都在
测试里，任一常量长大即红。这满足「基础段先扣、余量才给可裁段」的**意图**（可裁段
分到的是扣完不可裁段之后的余量），但**不是**运行期自适应分配——那是另一档工程
（需要把段级预算改成运行期按剩余量计算），本单不做，明确记在这里免得下次误读。

| 常量 | 改前 | 改后 | 理由 |
|---|---|---|---|
| `REFERENCE_FULLTEXT_BYTES` | 25600 | **23400** | 腾出段级空间；24400 时账本用满即红。**语义同时从「逐篇」改为「合计」**（见二·②-b） |
| `WORDLIST_PROMPT_BYTES` | 12150 | 12150（**不动**） | 实发 9623，未用满的 2527B 是工单 08 明确留的「不瘦身反而涨预算」位（闸的合法 name 数据） |
| `MODULE_SUMMARY_BYTES` | 40000 | 不动 | 仍是段级上界，库长大时截断照旧兜底 |
| `CLARIFICATION_HISTORY_CAP` | 2500 | 2500（**不动，但已复算**） | 修复方向 2 点名「随实测重新取值」：实测历史段 15438B，**已按其满额进账本**（这正是旧账本缺的一项），再降只会缩短历史而换不到余量——账本余 925B 已够。留 2500 |
| `REQUEST_RESERVE_BYTES` | （两套魔数） | **2048（新增，单源）** | 四条线结构测试共用一个下界；**生产侧也消费它**（`payload_budget_state` → 贴边留痕 / 超限判定），不是测试专用常量 |

**夹具联动（如实记账）**：手动全文用例的夹具从写死 700 份（25225B wire）改为
**按常量联动推导**，并**删掉**「必须超 4000 **字符**」那条旧断言——4000 是**字符**
口径的旧截断上限，在 23400B 级 wire 预算下，「超 4000 字符」需要 ≈24000B 内容、
加上标注预扣必然触发截断，两条要求不可兼得。核心行为（不被旧上限截断、file_label
原样）改由 `TRUNCATION_NOTICE not in user_message` 直接守，与文字长度无关。
同款联动改了另两条全文用例（`embeds_requested_fulltexts` / `every_file_head`）。

### 四、测试与口径

新增 **9 条**测试（`tests/test_llm.py`）：

| 测试 | 钉住什么 |
|---|---|
| `test_select_request_segment_ledger_closes_and_reserves` | **对账等式**：Σ段 + JSON 壳 = 实发 total（逐字节）；段名按稳定键名（`msg0:system` 等） |
| `test_select_segment_ledger_matches_measured_segments` | 段级分解逐条落预算内；用满口径账本 ≤ 上限 − 统一余量；账本 ≥ 实发（必须是上界） |
| `test_select_budget_reserve_is_single_source` | 统一余量单源；**现测四条线**（select 真实库 / 澄清 / 骨架 / 修复）都过同一下界，判据走生产同一函数 `payload_budget_state` |
| `test_fulltext_segment_budget_is_aggregate_not_per_reference` | 全文段是**合计**预算：篇数 1→10，总量不得跟着涨（两个注入路径） |
| `test_fit_segment_wire_never_exceeds_budget` | 段级预算就是实发上界（含极小预算的护栏形态） |
| `test_format_segment_breakdown_is_content_free_and_keyword_pinned` | 分解串只含元数据（脱敏契约），keywords 命中段无视 top 恒列出 |
| `test_rejected_oversized_payload_logs_segment_breakdown` | 拒发时 `llm_request_budget` 留痕含 request_bytes / limit / over_by / segments；**且渲染后的消息文本自带分解**（无 handler 时的唯一出口） |
| `test_near_limit_payload_logs_segment_breakdown` | ≥90% 留痕在**发出之前**；测两种贴边形态（仍在余量内 / 已跌破余量） |
| `test_normal_payload_logs_no_budget_warning` | 常规请求不留噪声 |

**尺寸断言口径（本单定的硬约定，已写进 `budget.py` 模块 docstring）**：尺寸类断言 /
记账一律走**发送前 wire 字节**（`wire_size` / `request_segments` / `payload_wire_size`），
与 `llm._chat_once` 预检同一行同一对象；**不得**用快照函数返回值或 JSON 增量估算代账
——工单 08 立单时按 `format_wordlist_prompt` 估 +1942B、实发只 +770B（低估），按 JSON
增量估则偏高，两个方向都错。段级预算的**四种段壳口径**（词表段段内自扣 ≤ 预算、
候选清单段段体 ≤ 预算 + 2B 拼接换行、全文段段壳 + 合计预算、条件规则段按实发计量）
在测试里逐条按实现断言，不统一猜测。

### 五、可判读信号

| 时机 | 通道 | 内容 |
|---|---|---|
| 贴边（≥90% 上限） | `logger.warning`，extra key `llm_request_budget` | operation / call_id / request_bytes / limit / headroom / within_reserve / segments |
| 被拒（超上限） | 同上（`logger.error`） | 追加 over_by；**恒含 `msgX:user`** |

**信号必须落得到 sink（评审整改）**：src 全仓**没有配置任何 logging handler**，
未配置时 Python 的 `lastResort` 只把 `record.getMessage()` 打到 stderr——只放
`extra` 的字段在真机上**根本落不到任何 sink**。故分解串**同时进消息文本**（
`logger.warning("LLM 请求体接近上限：%s（…）")`），`extra` 里保留一份给结构化
消费方；测试直接断言 `record.getMessage()` 带分解串（钉住这个出口不被改回去）。

**已知粒度限制（如实记账，未做）**：分段粒度到 **message 级**（`msg1:user`），
用户消息内部的二级段（题面 / 清单行 / 词表 / 全文 / 历史）没有再拆——要拆需要
拼装层回传段级结构，属另一档工程。**判读方式**：把 `msg1:user` 的字节数与账本
各段实测值（`.scratch/real-acceptance/verify-05-segment-budget.txt` 的 ② 节）
对照即可定位是哪一段涨的。

**为什么不进 observation / SSE（工单建议「在 telemetry 里留痕（`sanitize_llm_usage`
同一观测面）」——本单**有意不采纳**，理由记下来）**：观测 dict 的键集被
`llm_telemetry._OBSERVATION_KEYS` / `llm_recent_workflows._OBSERVATION_KEYS` 两个
allowlist 过滤，且 `tests/test_llm_recent_workflows.py` 对 sanitized call dict 做
**精确相等断言**——加键要同时改 allowlist + 契约测试，而那条契约的卖点是「内容安全、
键集稳定」。本单的改动不碰观测 / SSE 契约（工单文件边界也写了「不动 SSE / 前端」），
改用日志出口（上面已保证它真的落得到）。若日后要把段级信息上 GUI，那是一条独立的
契约变更，别顺手加。

### 六、证据与文件

- 实测证据：`.scratch/real-acceptance/verify-05-segment-budget.txt`（四条线现状 +
  段级分解 + 与 08 校准值对照）；探针 `probe-05-verify-budget.py`（可复跑）
- 四条线余量现状：`probe-05-headroom-lines.py` / `.txt`
- 真机：`.scratch/real-acceptance/verify-05-recommend-2021F-stm32.txt`（+ 首跑
  `-run.txt`、答案文件 `clarify-answers-05-2021F.json`、done 载荷
  `.scratch/recommend-domain-reject/done-05-2021F-stm32.json`）
- 产品改动：`src/contest_generator/budget.py`（新常量 + 段级记账原语 + 口径更正）、
  `src/contest_generator/llm.py`（标注预扣 + 贴边/拒发留痕 + 注释口径同步）、
  `tests/test_llm.py`

### 八、双轴代码评审（`code-review` 技能，两轴并行子代理，定基点 `19f4590e`）

**规格轴**抓出一个**真缺口**（已修，见二·②-b：全文段逐篇 vs 合计预算）——这条只有
对抗性复算才抓得到，自测的夹具是单篇所以全绿。另有两条已处理：`_fit_segment_wire`
极小预算仍可超预算（已加护栏）、`CLARIFICATION_HISTORY_CAP` 未复算（已复算并写明
结论：保持 2500，其满额已进账本）。一条**有意不采纳**（进 telemetry 观测面）与一条
**如实记为未做**（message 级以下的分段粒度），理由都在上文节里。

**标准轴**抓出三处文档/口径不一致（已修）：测试 docstring 里的常量写成 24000
（实现是 23400）、同一单内两处「唯一硬保证」互斥、`budget.py` 新函数的 docstring
把叶子语义锚在 llm 的私有实现上（依赖方向反）。另有三处 smell（已处理）：
`MESSAGE_SEGMENT_KEY` 零消费方（删）、`format_segment_breakdown` 内联壳算式而不用
`payload_shell_wire_size`（改为复用 + 支持传入已算结果）、`REQUEST_RESERVE_BYTES`
零生产消费方（新增 `payload_budget_state` 让预检真的消费它）。

评审过程中工作树被实施方反复改动（评审方据此报「当前是红的」）——那是同一会话边改
边审造成的，不是遗留缺陷；**定稿后复跑全量 pytest 绿（3958 passed）**。

### 九、未了 / 交给下一个人

1. **`WORDLIST_PROMPT_BYTES` 的 2527B 未用满**是最容易误读的一处：它**不是**可以
   随手砍的闲钱，而是工单 08 留的合法 name 数据位。下一次要腾空间，先动全文段
   （与 08 同向），或按 08「未了 1」先瘦身既有 models。
2. **段级账本是「用满口径」的上界 + 「实发口径」的对账**两条腿。新增提示词段时，
   两处都要过：实发口径那条（`_measure_prompt_segments`）会告诉你段进了哪一档；
   用满口径那条会告诉你预算还够不够。别只改一处。
3. 真实运行里预筛注记**按需出现**（stm32 全库装得下就不出），所以「最坏形态」
   必须按**会出现注记的平台**构造（mspm0）——下一个人加平台时注意。

## 实施提示词（新会话粘贴）

> 工单：`.scratch/real-acceptance/issues/05-request-budget-reality-gap.md`（先读全文）。
> 背景：`.scratch/tracker-audit/2026-09-09-在途盘点.md`「第十六轮」④ O-3；
> 实测数字来源 `.scratch/recommend-vision-qa/verify-16-C1-clarify-vision.json`。
> 任务：复算推荐/澄清请求的最坏形态账本（改成可执行结构测试），重分配段级预算，并给贴边/超限留可判读信号。
> 文件边界：`src/contest_generator/budget.py` + `llm.py`（段预算与预检）+ `tests/test_llm.py` 等预算测试；不动 SSE/前端。
> 红证先行：按真实库 86 条摘要行 + 2021F 题面拼最坏载荷（本轮已有实测 122161 字节基线）。
> 真机验收：2021F 真机推荐（可复用 `.scratch/recommend-domain-reject/probe-16-recommend-live.py`）不带「请求体过大」跑完。
