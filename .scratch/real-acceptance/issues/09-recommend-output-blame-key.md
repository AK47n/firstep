# 09 — 推荐失败被报成「AI 服务拒绝了本次请求（可能是 API key 无效、账户余额不足）」（真因是本地输出失败）

**要做什么：** 把「本地拿到但用不了的模型输出」单独归类，让错误文案不再把用户指去查
API key / 余额——HTTP 200 的失败套那句通用话术，按定义就是错的。

**被谁阻塞：** 无。

**状态：** resolved（2026-09-17 落地：`ERROR_KIND_OUTPUT` 分流 + 文案 + 可重试形态重试）

## 真机现场（2026-09-17，用户报障）

用户原话（推荐模块界面）：

> ai推荐模块显示 AI 服务拒绝了本次请求（可能是 API key 无效、账户余额不足或请求内容不被接受）。
> 请在设置页核对 API key 与账户余额后重试。

**先排除凭据与余额（实测，不是猜）：**

| 检查 | 实测 |
|---|---|
| `GET /user/balance`（用户 config 里的 key） | `is_available=true`，余额 **21.57 CNY** |
| 同 key 最小 chat 调用（`deepseek-flash`） | HTTP 200，正常返回 |

**再看运行中的 app（`127.0.0.1:8000`，进程 `python -m contest_generator.webapp`）**：
`GET /api/llm-workflows/recent` 最近两条 recommend 工作流**都失败**，且形状一致：

| 项 | 值 |
|---|---|
| workflow | `recommend:d01f0f22…` / `recommend:71ea3513…`，`status=error` |
| 失败调用 | `operation=select_modules`（第 2 次调用） |
| `http_status` | **200** |
| `parse_status` | `parse_error` |
| `error_kind` | **`client`** |
| `attempts` | **1**（一次都没重试） |
| `request_bytes` | 56980 |
| `usage.completion_tokens` | 972 / 759 |

**判据**：`http_status=200` 说明 `_chat_once` 走的是「解析后失败」那一支（非 200 会先把
`http_status` 记成 `status` 再抛）——**上游没有拒绝**，是本地拿到的输出不能用。
而 `errors.llm_error_message` 的 `client` 分支把所有 `kind=client` 一律换成
「AI 服务拒绝了本次请求（可能是 API key 无效、账户余额不足…）」。于是：服务回 200、
key 与余额都正常，用户被指去设置页查凭据。

## 根因

**输出侧本地判决被塞进了 `client`（= 上游 HTTP 4xx）这一格。** 三个现场：

| 位置 | 形态 | 为什么当时报 client |
|---|---|---|
| `llm.select_modules` 的 `parse` 闭包（输出超长守卫，>60000 字符） | 模型退化/循环 | 借用 `client` 的「不重试」语义（重试只会重复超长） |
| `llm._retry_parse` 的截断转化（`finish_reason=length`） | 输出被 `max_tokens` 截断 | 同上（同参数重试必然同样截断） |
| `_chat_once` 的发送前体积断言 | 请求体过大 | 形态上确实与上游 413 同类，但**没发出去**，也该说「本地」 |

**病与 `real-acceptance/03`（域拒绝）同源**：本地判决（域拒绝 / 输出失败）错报成上游
拒绝，把用户的排查方向指向凭据。03 修了域拒绝那一条，本次是同样的病在输出侧的第三个
现场——**「借 client 的免重试语义」这种用法本身就是把两个正交维度（错误归属 / 重试策略）
混成一个常量**。

`attempts=1` 与 `completion_tokens≈1000` 两个观测值同 `finish_reason=length` 的截断形态
最相符（确定性失败不重试）；超长守卫（60000 字符 ≈ 数万 token）与 token 数不符，但**不能
从观测面区分**——观测里没有 `finish_reason`。这也是本条如实记下的取证边界：

- 复现尝试（`.scratch/real-acceptance/probe-05-transport-capture.py`，逐次打印原始
  `status` / `finish_reason` / `content` 长度）：**2026H/mspm0 3 轮、2024H/mspm0 3 轮
  全部终态 done**——该失败是**偶发**的，六轮没撞上；
- 失败请求的 `request_bytes=56980` 与库里全部题面 × 平台的 select 装配（按 webapp 同款
  装配逐题量，`.scratch/real-acceptance/probe-05-find-topic.py`）**都不相等**（用户当时
  的题面不在库内 / 与库内题面不同），所以「照原题重跑」这条路也走不通；
- 结论：**修复按 kind 分流做（不依赖具体是哪一支）**，三支的文案都要对；哪一支是本次
  现场，靠 `llm_request_budget` 式的可判读信号还不够——**观测面缺 `finish_reason`**，
  见「未了」。

## 修复

| 改动 | 位置 |
|---|---|
| 新增 `ERROR_KIND_OUTPUT = "output"`（输出侧本地判决：HTTP 200 拿到但输出不能用——截断 / 超长 / 畸形），单源常量 + 注释写明与 `client` 的区别 | `llm.py` |
| 三处「借 client」的抛出点改用 `output`：超长守卫 / 截断转化（保留免重试语义）/ 发送前体积断言 | `llm.py` |
| 新增 `OUTPUT_TRUNCATION_HINT`（参数性确定失败判据单源）：超长 / 截断形态**不重试**（同参数必然同样结果），其余 output 形态（畸形 / 形状不对）**照 parse 同款快重试**——原来这三种一律「一枪毙命」，其中畸形输出本可自愈 | `llm.py` |
| 错误文案新增 output 分支：`AI 服务调用失败：AI 服务这次返回的内容无法使用（响应被截断、超长或不是合法结构）——这通常是一次性的，不是登录凭据或账户问题。请再点一次重试；若反复出现，可在设置页换一个模型后再试。` | `errors.py` |
| 遥测词表补 output 标签（`output: "输出不可用"`）——不补就按回退原样显示英文 `output`（与 `real-acceptance/03` 补 domain 同款） | `static/js/fx/llm.js` |
| CONTEXT「错误映射」行补 output 一格 | `CONTEXT.md` |

**文案政策（与 domain 后缀同）**：只说可操作方向，**不承载可变量**——不写「已自动重试
N 次」（重试次数取决于失败形态，写死就会撒谎），也不删掉「反复出现怎么办」的下一步。

## 验收标准

- [x] 红证：三条新用例在改前红（`ImportError: cannot import name 'ERROR_KIND_OUTPUT'`
      → 改后绿）
      —— `tests/test_errors.py::test_llm_error_output_never_blames_key_or_balance`、
      `::test_llm_error_output_survives_exhausted_retry_text`；
      `tests/test_llm.py::test_truncated_select_failure_reaches_user_without_key_blame`
      （端到端：截断响应 → 异常 → 文案，钉住**用户眼前不再出现 key / 余额**）
- [x] 既有两条「免重试」用例改为断言 `kind == ERROR_KIND_OUTPUT`，**策略断言不动**
      （`len(transport.calls) == 1`）——kind 语义修了，行为（不重试）没变
      （`test_select_modules_oversized_output_fails_fast_without_retry` /
      `test_select_modules_truncated_output_fails_fast_without_retry`）
- [x] 真上游 4xx 语义不变：`kind=client` 仍给「核对 key 与余额」
      （`test_llm_error_upstream_4xx_still_generic_key_hint` 未改动、仍绿）
- [x] 全量 `pytest` **3961 passed**；`node --test tests/js/*.test.mjs` **1430 pass / 0 fail**
- [x] 实测对照（改后逐字）：
      - output：`AI 服务调用失败：AI 服务这次返回的内容无法使用（响应被截断、超长或不是合法结构）——这通常是一次性的，不是登录凭据或账户问题。请再点一次重试；若反复出现，可在设置页换一个模型后再试。`
      - client：`AI 服务拒绝了本次请求（可能是 API key 无效、账户余额不足或请求内容不被接受）。请在设置页核对 API key 与账户余额后重试。`

## 未了（交给下一个人）

1. **观测面缺 `finish_reason`**，所以「截断 vs 超长 vs 畸形」在事后排查时**分不出来**
   （本单只能按 kind 兜住文案，没法从现场证据指认是哪一支）。要闭环就得让
   `LLMError` 带一个机械可读的形态标记（如 `output_form`）并进观测 allowlist
   ——那条 allowlist 有精确相等契约（`tests/test_llm_recent_workflows.py`），是一次
   独立的契约变更，别顺手加。
2. **本文的病根是「借用 client 的免重试语义」**：错误归属（本地 / 上游）与重试策略
   （确定失败 / 概率失败）本应正交。现在 `output` 用 `OUTPUT_TRUNCATION_HINT` 字符串
   成员判据来分「确定失败」，是**可用的近似而不是结构**——下一个想再借 client 的人，
   先想清楚要借的是哪一维。
3. 复现该偶发失败的探针留在 `.scratch/real-acceptance/probe-05-transport-capture.py`
   （逐次打印原始 `status` / `finish_reason` / `content` 长度），下一个撞上现场的人
   直接跑它就能拿到那一支的原始证据。

## 现场证据

- 用户报障文案 + 余额实测（21.57 CNY，`is_available=true`）+ 最小 chat 200：本文「真机现场」
- 失败工作流观测：`GET http://127.0.0.1:8000/api/llm-workflows/recent`
  （两条 `recommend:*`，`select_modules` / `http_status=200` / `parse_status=parse_error`
  / `error_kind=client` / `attempts=1`）——**进程内存 ring buffer，重启即失**，重启后要
  重现只能靠日志；本单已把关键字段抄进本文
- 复现尝试与原始响应探针：`.scratch/real-acceptance/probe-05-transport-capture.py`
- 题面对照量：`.scratch/real-acceptance/probe-05-find-topic.py`（56980 与库内任一题面
  装配都不相等 → 现场题面不在库内）
