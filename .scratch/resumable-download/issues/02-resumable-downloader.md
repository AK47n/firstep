# 02 — 可续下载域模块：卷内断点 + 卡死判定 + 无上限退避重试

**要做什么：** 让「下载一卷」这个动作本身变得**能接上、能自愈**——
断流/卡死/连接重置之后，下一次尝试**从已经落盘的字节接着下**，而不是从 0 重来；
每次重试都如实计数、可取消，并且**保签名兼容**既有注入点。

**被谁阻塞：** 01（真网络判据就位，才能判「续没续上」）。

**状态：** resolved

- [x] 新增 `src/contest_generator/download_resume.py`（与 `materials_task.py` / `full_task.py` 同层的「下载」域模块；
      两者都要用它，故不放任一侧）：
      - `DownloadResult`：`sha256` / `transferred_bytes` / `attempts` / `resumed_from`（0 = 从头）；
      - `resumable_download(url, dest, on_progress, *, cancel=None, before_retry=None,
        expected_size=0, expected_sha256="", min_resume_bytes=…, max_attempts=None, opener=None)`
        ——**前三参位置与语义不变**，新参数全部关键字可选（既有 monkeypatch 点零改动）；
      - `describe_network_error(exc) -> str`：底层异常 → 中文可行动句子（单源文案）；
      - `retry_delay(attempt) -> float`：2、4、8、16、32、60、60…（**不进设置页**，不引新配置项）；
      - `is_retryable(exc)` / `error_kind(exc)`：给任务层分类用，**不解析文案**。
- [x] 断点契约逐条成立（判据见 spec「断点契约」表）：
      本地 0 字节不发 Range；本地 N 字节且卷 > 阈值 → `Range: bytes=N-` 且 `206` 起点对齐才续写；
      小卷（≤ `min_resume_bytes`）整卷重下；服务器返回 `200`（忽略 Range）→ 丢弃半成品从 0 重下；
      服务器 `416`/本地比远端大 → 删掉重下；已下字节 == 卷大小 → 不再发请求直接进校验；到点即成功。
- [x] **截断必须是失败**：对端声明了长度却没给够 → `DownloadTruncatedError`（可重试，半成品保留）；
      判据是 **已落盘 + 本次收到 < 声明总长**（见「验收记录」第 1 条：初版判据会误伤正常续传）。
- [x] **清单 size 与对端总长矛盾 = 不可重试**：`DownloadSizeMismatchError` 直报中文，不进重试循环。
- [x] **无上限退避重试**，每次经 `before_retry` 如实上报（第 N 次 / 原因 / 已落盘字节）；
      退避等待用 `cancel.wait(delay)`：**取消在退避中即刻生效**，不再发起下一次尝试。
- [x] **校验失败不重试**：`expected_sha256` 给了就按内容判——不符则清掉整份重下再验
      （这一条同时解掉了「尺寸到点但内容坏」的死局，见「验收记录」第 2 条）。
- [x] 单测 `tests/test_download_resume.py`（**25 条，不碰网络**）：策略与文案 / 偏移判定 / 截断与矛盾 /
      本地坏 / 阈值 / 取消 / 观测面，分组见 `verify-02-probe.txt` 第三节。
- [x] **与既有实现可互换**：三参形态可直接替换为 `resumable_download`；
      `tests/test_full_task.py` / `test_materials_task.py` / `test_full_apply.py` 既有断言**原样通过**。
- [x] 真网络复跑 01 的五个用例：**总判 PASS**，证据 `verify-02-probe.txt` + `verify-02-probe.json`
      （`cut` 起始偏移 `[0, 838860, 1342176, 1644166]`；`stall` 30 秒读超时判出后从 `786432` 接上）。
- [x] 01 的**反证复跑仍红**（对照实现偏移序列全 0、总判 FAIL、退出码 1）——判据没被调软。
- [x] 全套回归：**4374 passed / 1 skipped**（唯一一处失败是本单测试自己的算术写死，已修）。

## 验收记录（2026-09-13）

**同一套判据由红转绿**：工单 01 预登记的红是「被截断却自称成功 + 偏移恒为 0」，
本单跑出「截断算失败 + 偏移逐次接续」。完整证据与读法见 `verify-02-probe.txt`。

**本单踩到并修掉的四个真坑**（每个都留了判据，别再犯）：

| # | 坑 | 为什么危险 | 现在怎么防 |
|---|---|---|---|
| 1 | 拿「本次收到 < `Content-Range` 总长」判截断 | **误伤每一次正常续传**（本地 102400 + 本次 204800 被判「连接中断」），把好端端的续传打断 | 判据改 **已落盘 + 本次收到** < 总长；单测 `test_resume_continues_from_offset_after_cut` |
| 2 | 只给 `expected_size`、不给 `expected_sha256` | 「尺寸到点但内容坏」成死局：服务器见起点=整卷大小就不发字节，重试每轮收 0 字节（实测报「重试 4 次仍未下完（307200 / 307200）」） | 内容不符 → 清掉整份重下；`test_declared_total_shorter_than_manifest_is_not_retried` 等钉住 |
| 3 | 长度判定写在重试循环**外** | 第一次尝试结束就 `break`，`continue` 永远走不到——**「自动重试」形同虚设** | 判定移到循环内；`test_truncation_is_a_failure_not_a_success` |
| 4 | `min_resume_bytes` 定 1 MB | 探针实测：断在 800 KB 时走的是「整卷重下」，门槛含义是「一次断流最多白下多少」 | 改 64 KB；探针 `cut` 用例的偏移序列即为回归判据 |

**探针/模拟器同时被修的三处**（判据自身的卫生问题，属于工单 01 的资产）：

- 模拟器 `cut`/`stall` 原来**永远切**：每次只剩 40%，数学上收敛（0.6^n）但工程上要几十轮 ⇒ 探针跑到天荒地老。
  改为「只切前 N 次」（`cut_runs`），这才是「坏一阵就好」的真实形态。
- 模拟器 `stall` 的安静时长原为 8 秒 < 客户端读超时 30 秒 ⇒ 先关连接的是服务器，
  走的是「读干净但没读满」那条路，**没验到超时**。改为 35 秒（长于读超时），才真的验到「零字节卡死被判出来」。
- 探针每例前**没清落盘点**：上一轮留下的完整文件被实现直接复用（它还带 sha 校验），
  于是「断了能不能接上」根本不发生——`stall` 曾以 0.02 秒"通过"。
  现在每例前清文件 + `sim.reset()` 清请求台账。

**本单没做的事**（留给下一单）：产品默认值还没换——两条任务链路的 `download` 缺省仍是
`download_part`，所以**用户侧行为此刻没有变化**；半成品保留、重试计数与状态面投影是工单 03/04。
