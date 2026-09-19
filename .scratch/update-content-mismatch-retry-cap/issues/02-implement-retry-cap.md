# 02 — 实施：同一卷连续 5 次「内容不符」转终态失败

**要做什么：** 让持久的「内容与清单不符」能收敛：同一卷**连续 5 次**内容不符 → 转终态 `failed`，
中文说清「服务器上这份可能与清单对不上、重下不会有变化、可稍后再试或反馈发布者」。
用户可观察的结果：不再每 60 秒静默重下整整一卷（线上完整包 ≈ 45 GB/小时量级），
而是半分钟内明确失败并给可行动作；**网络类失败仍然无上限重试**。

**被谁阻塞：** 无（与本目录工单 01 的决策单无关；与 `update-verify-failure-leftovers/01`
的清理规则天然相容——本单新增的终态错误同样归 `verify` 且不可重试，会自动落进那条清理）。

**状态：** resolved（2026-09-19，含真机复跑）

**真机复跑完成（2026-09-19）。** 用 `.scratch/verify-gate-drills/run-drill-02-with-workspace-src.py
--evidence-dir .scratch/update-content-mismatch-retry-cap --only content-mismatch`
（drill 零改动，sha256 `30ebf6268f74aaa5…`；harness 把工作树的源码放进沙箱＝用户机上那一代代码）：

| 判据 | 实测 |
|---|---|
| `terminal_reached` | **true**（改动前 150 秒观察窗内都没有终态） |
| 终态 | `failed`，`error_kind = "verify"` |
| 文案 | `下载失败（卷 firstep-full-v1.2.1.zip）：连续 5 次整卷重下后内容仍与清单不符，重下不会有变化（可稍后再试，或把这一卷反馈给发布者）` |
| 收敛速度 | **30.6 秒**（观察窗 150s 内），服务器台账 **5 次请求 / retry_count 4** |
| 收尾 | 沙箱源码逐字节复原、8020 无监听、真身数据目录未动；判红 0 / PASS |

证据：`.scratch/update-content-mismatch-retry-cap/verify-real-machine.{txt,json}` +
`verify-real-machine-content-mismatch.{txt,json}`。

## 完成记录（代码与守卫）

- 新终态错误 `DownloadContentMismatchPersistentError`：进 `_NOT_RETRYABLE`、`error_kind="verify"`、
  `describe_network_error` 原样返回它自己的中文文案（**不再**承诺「会重新下载整卷」）；
- 模块级常量 `MAX_CONTENT_MISMATCH_ATTEMPTS = 5`；重试循环里**连续**计数
  （中途别的错误清零），到上限即抛终态（不调 `before_retry`、不写边车）；前 4 次行为逐字不变；
- 新关键字参数 `max_content_mismatch`（**只有测试假剧本才需要覆盖**，与既有 `max_attempts` 同款纪律）；
- 模块 docstring 的「契约」与「异常谱系」两处同步更新（瞬时 vs 持久两类不确定性的分界写清）。

**判据强度探针 3/3 转红**（`.scratch/update-content-mismatch-retry-cap/verify-02-guard-strength.{txt,json}`）：

| 注入 | 结果 |
|---|---|
| ① 去掉封顶（回到改动前） | 转红 ✓（1 failed） |
| ② 连续改累计（中途别的错误不再清零） | 转红 ✓（1 failed） |
| ③ 新错误从「不可重试」表里拿掉 | 转红 ✓（2 failed） |

**两条修复的接缝也有断言**：`tests/test_task_download.py` 里钉了「终态错误必须被
`is_terminal_verify` 认下、且任务层把半成品与边车清干净」（缺它两条修复各自正确、合起来留垃圾）。

**一处探针工程教训**（已内建防护）：第一次跑 ① 时封顶被去掉、用例当时还没有别的上限，
探针**卡死在 300 秒**、被工具强杀 → `finally` 没跑 → 源文件停在注入态。两条修法都落地了：
① 用例加 `max_attempts=8` 收场；② 两支探针都加了**前置干净性检查**（锚点不在就拒绝开跑并给出
`git checkout` 修法），免得「上一轮没复原」被误读成「探针写坏了」。

聚焦测试：`test_download_resume.py` + `test_task_download.py` 63 passed；
`test_full_task.py` + `test_materials_task.py` + `test_download_status_surface.py` 85 passed。
真机复跑用冻结量具旁边的通用包装器
`.scratch/verify-gate-drills/run-drill-02-with-workspace-src.py`（工单里原写「本目录的
`run-real-machine.py`」——实际写成通用件，与本批另一张单共用一处实现）。

## 验收标准

- [x] 下载域新增终态错误类型「内容不符 · 已连续多次」：进「重试必然同样结果」那张表、
      `error_kind == "verify"`、中文文案由既有 `describe_network_error` 单源给出且含
      「重下不会有变化」（不再说「会重新下载整卷」）
- [x] 重试循环里**连续**计数（内容不符 +1；任何别的错误或一次成功清零），
      达上限（模块级常量 5）时抛新终态错误；前 4 次的行为**逐字不变**
      （仍「删半成品 + 退避重试」，进行中摘要照旧）
- [x] 网络类失败的重试策略零改动（既有「无上限」用例仍绿）
- [x] 单测（`tests/test_download_resume.py` 同族加格，沿用既有假 opener 夹具）：
      永远坏 → 5 次后抛新类型、`error_kind == "verify"`、文案含「重下不会有变化」；
      坏 → 截断 → 坏 → 变好 → 成功（**连续**语义，累计口径会被判死而转红）；
      网络类仍走原路（测试专用的小 `max_attempts` 剧本）
- [x] 组合断言：终态之后盘上是干净的（半成品与边车都没了）——防止两条修复各自正确、
      合起来仍留垃圾（`test_persistent_content_mismatch_clears_leftovers_at_the_task_layer`）
- [x] 反向注入探针（`.scratch/update-content-mismatch-retry-cap/probe-guard-strength.py`）：
      去掉封顶（回到无上限）、把连续改成累计、把新错误从不可重试表里拿掉——三处注入
      **3/3 都转红**；跑完复原并复核 sha256
- [x] 真机复跑（通用包装器 + `drill-02 --only content-mismatch`，drill 零改动）：
      `terminal_reached == true`、终态 `failed`、`error_kind == "verify"`、
      `error` 含「重下不会有变化」、`max_retry_count == 4`（≤5）、30.6 秒收敛；
      脚本显式记账「沙箱源码来自工作树」
- [x] 既有守卫全绿：`tests/test_full_task.py`、`tests/test_materials_task.py`、
      `tests/test_download_status_surface.py`（12 键契约）→ 聚焦 85 passed；
      全套在账本收口时跑一次
