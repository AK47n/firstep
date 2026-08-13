# 01 — DeepSeek 网络瞬断退避重试（网络类与解析类分策略）

**What to build:** 现 `_retry_parse`（llm.py:800）对 LLMError 一律 3 次**立即**重试、无 sleep——网络层瞬断（Windows 10054 连接重置 / URLError / 超时）3 连快重试大概率仍断，整轮推荐作废。工单 reference-library-hygiene/03 真机 3/3 次运行撞此形态（重试 3 次仍断，失败轮次每次不同）。改：LLMError 区分错误类别（network / parse），网络类走指数退避（5 次 × 1/2/4/8s 或 2/4/8/16s，实施定、测试钉死），解析类（空内容 / 畸形 JSON）保持 3 次快重试。select_modules / clarify / fix_compile_errors / 归档判定 / 参考简介等全部 _retry_parse 调用点自动受益。

**Status:** resolved

## 现状（已核实 2026-08-13）

- llm.py:596 `except urllib.error.HTTPError` / :599 `except (urllib.error.URLError, OSError)` → 网络错误转 LLMError，与解析失败**同形**（无类别标记）
- `_retry_parse`（llm.py:800）：SUMMARY_RETRY_LIMIT=3 次即时循环，无退避（llm.py 全文无 sleep）
- 真机证据：工单 03 进程内真机 3 次运行均中途遇连接重置 10054 / 空内容，快重试 3 次仍断 → 整轮作废（PR #51 的兜底挡不住网络瞬断）
- 测试先例：fakes.py FakeTransport；time.sleep 需 monkeypatch llm 模块命名空间（测试不可真睡）
- 既有文案测试可能锚定「连续 3 次调用失败」——grep 同步

## 实施

1. LLMError 加类别：可选字段（如 `kind: str = "parse"` 缺省向后兼容）或子类 LLMNetworkError——`_chat` 网络异常转换点（HTTPError / URLError / OSError 处）标记 network；解析失败路径保持缺省 parse
2. `_retry_parse` 分策略：network → NETWORK_RETRY_LIMIT（5）× 指数退避（sleep 序列测试钉死）；parse → SUMMARY_RETRY_LIMIT（3）快重试不变
3. 失败汇总文案「连续 N 次调用失败」随 N 变化——既有文案测试定位同步（grep「连续」）
4. 测试 tests/test_llm.py：
   - FakeTransport 抛 ConnectionResetError → 断言 5 次调用 + sleep 序列记录（monkeypatch）
   - URLError 同；HTTPError（5xx）同策略
   - 空内容 / 畸形 JSON → 仍 3 次、sleep 零调用
   - 混合：前 2 次网络失败后 1 次成功 → 退避后正常返回
   - 红证先行：改前形态（无类别）下网络类 3 次即抛、零 sleep
5. 真机：瞬断不可复现，单测钉死即可；真机观察留待下次真实推荐流程（真机日志里网络重试次数可见）

## 验收

- pytest 全绿 + mypy src 干净
- 网络类 5 次退避、解析类 3 次快重试；重试次数与 sleep 序列被测试钉死
- 协议文本零改动（提示词不动，仅错误文案 N 同步）

## 文件边界

`src/contest_generator/llm.py`、`tests/test_llm.py`、`tests/fakes.py`（如需）

**明确不动的：** webapp、前端、selection、素材库数据、DeepSeek 网关侧。

## 验收记录（2026-08-13）

- **实施**：LLMError 加 `kind` 可选字段（缺省 parse 向后兼容，`ERROR_KIND_NETWORK` / `ERROR_KIND_PARSE` 字符串常量单源）；`UrllibTransport` 的 URLError / OSError 转换点标记 network；`_chat` 状态码 5xx 标记 network（4xx 保持缺省 parse，与旧行为一致）；`_retry_parse` 分策略——network 类 `NETWORK_RETRY_LIMIT=5` 次、按连续网络失败次数指数退避 1/2/4/8s（`_backoff_sleep` 独立接缝，monkeypatch 它而非全局 time.sleep），parse 类保持 `SUMMARY_RETRY_LIMIT=3` 快重试；失败文案「连续 N 次」随实际次数（N = attempts 计数）。
- **测试**：tests/test_llm.py +9（网络类 5 次退避 + sleep 序列 [1,2,4,8] 钉死、5xx 同策略、前 2 次网络失败后退避成功、解析类 3 次零 sleep、kind 缺省、UrllibTransport URLError/ConnectionResetError → kind=network 逐例断言）；既有 502 用例 4 个同步到网络类预期（文案 N=3→5、sleep 序列断言）——`_FlakyTransport` 注释补 502=5xx=网络类。
- **红证**：先落类别管道（kind 常量 + 转换点 + sleep 接缝）不改策略——7 个网络策略用例全红（旧行为 3 次即抛、`assert [] == [1.0, 2.0]` 零 sleep），解析类 3 次快重试用例与类别管道用例已绿；再落 `_retry_parse` 分策略——162 绿。
- **回归**：pytest 全量 1282 绿 + mypy src 干净；协议文本零改动（提示词一字未动，仅错误文案 N 随次数）。
- **真机**：瞬断不可复现，按工单以单测钉死；真机观察留待下次真实推荐流程（真机日志里网络重试次数可见）。
