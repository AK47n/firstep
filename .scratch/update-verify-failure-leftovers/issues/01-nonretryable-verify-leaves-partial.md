# 01 — 不可重试的校验失败（发布信息不一致）留下**整卷半成品 + 边车**

**Type:** task
**Status:** open
**发现于：** 沙箱真机演练 B2 场景三（`sandbox-drill/02`，2026-09-18）
**证据：** `.scratch/verify-gate-drills/verify-02-degraded.txt`（含 `verify-02-degraded.json` 的
`scenarios.verify-size` 与文末「修订与更正」第 2 节）；原始产物量在
`%TEMP%\fe02-20260918-231212\drill-updates-archive\full-231339\`

## 现象（真机实测）

fixture：清单把这个卷声明成 **1 MiB**，服务器照真载荷（3,961,701 B）发 —— 客户端一读响应头就判
「发布物与清单不一致」，按 spec 第 125 行这是**不可重试**的 verify 失败。产品行为：

| 判据 | 实测 |
|---|---|
| 终态 | ✅ `failed`（**不重试**，retry_count=0） |
| 错误话术 | ✅ 中文、指明不一致：`下载失败（卷 firstep-full-v1.2.1.zip）：发布信息不一致：清单说 1048576 字节，服务器说 3961701 字节` |
| `error_kind` | ✅ `verify` |
| `updating.lock` / `pending-update.json` | ✅ 都没留下 |
| 旧版本 | ✅ 服务还在、版本没变、工具根 `VERSIONS.md` 逐字节未变 |
| **`updates/full/` 里的残留** | ❌ **整卷 3,961,701 字节的 `firstep-full-v1.2.1.zip` + 边车 73 字节**（`{"url": ".../p?mode=stable", "expected_size": 1048576}`） |

## 期望（spec 明文）

`.scratch/resumable-download/spec.md` 第 147 行：

> 成功 / **校验失败**时**一并删除边车与半成品**，不留孤儿。

这条失败 `error_kind="verify"`（属于「校验失败」那支），却把整卷半成品与边车都留下了。

## 影响（不夸大，但要说清代价）

- **磁盘**：线上完整包 765 MB/卷 → 用户看到「失败」之后，`updates\full\` 里白占 **~765 MB**；
  一个磁盘不宽裕的机器上，这会直接影响他能不能重下（`full/apply` 的磁盘预检正是拿这附近的余量算的）。
- **可自愈**：下次点重试时，本地那份（长度 > 清单声明）会让下载器收到 `416` → `_attempt`
  就地 `clear_partial` 后从 0 重来（工单 08 的处置），所以不会永久坏；但**用户不点重试就一直在**。
- **与「失败要留断点」的边界**：可重试的网络失败**必须**留半成品（那是断点，spec 第 145 行）。
  本单要清的只有**不可重试**那一支——两者不能混（混了就会把断点删掉，退回到工单 08 之前的行为）。

## 建议修法（一个可能的缝）

任务层失败分支（`task_download.download_and_verify` 的异常路径 / 两链路的 `_download_one`）
按 `download_resume.error_kind(exc) == "verify" and not download_resume.is_retryable(exc)`
清掉 `dest` 与边车；`verify` 但**可重试**（内容不符，见决策单
`update-content-mismatch-retry-cap/01`）保持现状（它每轮自己会清）。
判据单源已经在 `download_resume`（`is_retryable` / `error_kind`），不要在任务层另写一张表。

## 验收

```
python .scratch/verify-gate-drills/drill-02-degraded.py --only verify-size
```

期望：`.json` 的 `scenarios.verify-size.checks` 里 **「半成品被清」「边车被清」都成立**，
且 `updates/full/` 目录为空；同时**不能**把网络失败那一支的断点删掉
（`--only cut-retry` 的「成功后边车已清 / 失败态留边车」两条仍要成立）。
