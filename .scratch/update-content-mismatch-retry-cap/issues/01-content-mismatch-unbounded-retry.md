# 01 — 决策单：持久「内容与清单不符」会**永远重试**（无终态、每轮整卷重下）

**Type:** task
**状态：** resolved（2026-09-19：**选 1 —— 连续 N 次转终态，N = 5**）
**发现于：** 沙箱真机演练 B2 场景四（`sandbox-drill/02`，2026-09-18），脚本 `.scratch/verify-gate-drills/drill-02-degraded.py --only content-mismatch`
**证据：** `.scratch/verify-gate-drills/verify-02-degraded.txt` / `.json`（`scenarios.content-mismatch`）

## 先说清楚：这**不是**实现缺陷，是 spec 定的行为

`.scratch/resumable-download/spec.md` 第 122 行：

> **下完但内容与清单 SHA256 不符** → **删半成品 + 走退避重试**（从 0 整卷重来，**直到对上或用户取消**）；
> 单列 `DownloadContentMismatchError`，归 `error_kind="verify"`

代码侧也对得上：`download_resume._NOT_RETRYABLE`（第 132 行）只收 `DownloadSizeMismatchError` /
`DownloadLocalCorruptError` / `DownloadRangeNotSatisfiableError`——`DownloadContentMismatchError`
不在其中，于是 `is_retryable()` 判它可重试，而 `resumable_download(max_attempts=None)` 是
**无上限**（第 363 行，产品口径「网络故障要自己扛到成功」）。

## 但真机第一次跑出的后果是这个样子

fixture：本地可控服务器**每次**都把字节改坏 16 个（长度一字不改），清单里的 sha256 是干净载荷的哈希
（等价于线上「服务器上那份坏了」或「清单里的哈希过期了」）。产品端点 `/api/update/full/{check,apply,status}` 全走真的。

| 观察 | 实测 |
|---|---|
| 终态 | **没有**（150 秒观察窗内 6 次重试后仍在 `downloading`） |
| `retry_count` | 1 → 6 持续增长（退避 2、4、8、16、32、60 秒，封顶 60） |
| 服务器台账 | 6 次请求，**起始偏移全是 0**（每轮整卷重下） |
| 进行中摘要 | 「下载内容与清单不符（3961701 字节），已删除重下，会重新下载整卷」（中文 ✓） |
| `error_kind` | `"verify"` |
| 用户能看到的出路 | 只有自己点「取消」 |

**代价**：线上完整包 765 MB/卷，退避封顶后约每 60 秒重下一整卷 ⇒ **约 45 GB/小时**量级的流量黑洞
（按本机观察节奏外推，非实测小时级数据）；而 spec 第 177 行承诺的那句「校验失败 → 明确『重下不会有
变化』」的**终态话术，在这个分支永远不会出现**——因为它压根进不了失败态（那句属于**不可重试**的
verify 分支：416 持久 / 清单 size 与对端矛盾，见 B2 场景三，那一支实测正常：终态 `failed` + 中文）。

## 建议（三选一，动代码前先拍板）

1. **加封顶**：同一卷连续 N 次（如 5 次）「内容不符」→ 转终态 `failed`，中文说清「服务器上这份
   可能与清单对不上，重下不会有变化；可稍后再试或反馈发布者」——把 spec 第 177 行那句承诺真正接上；
2. **不改策略、只加可见性**：摘要里带上「已重试 N 次仍不符（已重下 X MB）」，让用户自己判断要不要停
   （成本最低，但仍会烧流量）；
3. **维持现状**，把「无上限」的理由写进 spec（并接受流量黑洞与「无法失败」的用户体验）。

倾向 1（与「网络故障无上限」区分开：网络是**瞬时**的，内容不符可能是**持久**的——这是两类不同的
不确定性，不该共用同一个无上限策略）。

## 拍板（2026-09-19，澄清一轮后）

**选 1（加封顶），N = 5。** 理由与代价写进 `.scratch/update-content-mismatch-retry-cap/spec.md`：
网络是**瞬时**不确定性（重试有救），内容不符是**持久**不确定性（重试改变不了服务器上那份字节），
两类不该共用同一条无上限策略；备选 2（只加可见性）把判断留给用户但流量照烧，
备选 3（维持现状）与 spec 第 177 行那句「重下不会有变化」的承诺直接冲突。

实施单：`02-implement-retry-cap.md`。真机判据：`drill-02-degraded.py --only content-mismatch`
的 `terminal_reached == true`。

## 验收（任一修法落地后）

```
python .scratch/verify-gate-drills/drill-02-degraded.py --only content-mismatch
```

期望：观察窗内出现终态 `failed`，`error` 是中文且说明「重下不会有变化 / 可稍后再试」，
`retry_count` 停在一个有界的数字上；`.json` 里 `scenarios.content-mismatch.terminal_reached == true`。
