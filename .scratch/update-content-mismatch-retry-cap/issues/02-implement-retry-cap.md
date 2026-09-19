# 02 — 实施：同一卷连续 5 次「内容不符」转终态失败

**要做什么：** 让持久的「内容与清单不符」能收敛：同一卷**连续 5 次**内容不符 → 转终态 `failed`，
中文说清「服务器上这份可能与清单对不上、重下不会有变化、可稍后再试或反馈发布者」。
用户可观察的结果：不再每 60 秒静默重下整整一卷（线上完整包 ≈ 45 GB/小时量级），
而是半分钟内明确失败并给可行动作；**网络类失败仍然无上限重试**。

**被谁阻塞：** 无（与本目录工单 01 的决策单无关；与 `update-verify-failure-leftovers/01`
的清理规则天然相容——本单新增的终态错误同样归 `verify` 且不可重试，会自动落进那条清理）。

**状态：** ready-for-agent

## 验收标准

- [ ] 下载域新增终态错误类型「内容不符 · 已连续多次」：进「重试必然同样结果」那张表、
      `error_kind == "verify"`、中文文案由既有 `describe_network_error` 单源给出且含
      「重下不会有变化」（不再说「会重新下载整卷」）
- [ ] 重试循环里**连续**计数（内容不符 +1；任何别的错误或一次成功清零），
      达上限（模块级常量 5）时抛新终态错误；前 4 次的行为**逐字不变**
      （仍「删半成品 + 退避重试」，进行中摘要照旧）
- [ ] 网络类失败的重试策略零改动（既有「无上限」用例仍绿）
- [ ] 单测（`tests/test_download_resume.py` 同族加格，沿用既有假 opener 夹具）：
      永远坏 → 尝试次数 == 5 且抛新类型、`error_kind == "verify"`、文案含「重下不会有变化」；
      坏 2 次后变好 → 成功且 `retried == True`；坏 → 截断 → 坏 → 计数被清零（连续语义）；
      网络类仍走原路（用测试专用的小 `max_attempts` 剧本）
- [ ] 组合断言：终态之后盘上是干净的（半成品与边车都没了）——防止两条修复各自正确、
      合起来仍留垃圾
- [ ] 反向注入探针（`.scratch/update-content-mismatch-retry-cap/probe-guard-strength.py`）：
      去掉封顶（回到无上限）、把连续改成累计、把新错误从不可重试表里拿掉——三处注入
      **都必须转红**；跑完复原并复核 sha256
- [ ] 真机复跑（`.scratch/update-content-mismatch-retry-cap/run-real-machine.py`，drill-02 零改动）：
      `--only content-mismatch` 的 `.json` 里 `terminal_reached == true`、终态 `failed`、
      `error_kind == "verify"`、`error` 含「重下不会有变化」、`max_retry_count <= 5`；
      脚本同样显式记账「沙箱源码来自工作树」
- [ ] 既有守卫全绿：`tests/test_full_task.py`、`tests/test_materials_task.py`、
      `tests/test_download_status_surface.py`（12 键契约）、`tests/test_task_progress.py` 的下载态用例
