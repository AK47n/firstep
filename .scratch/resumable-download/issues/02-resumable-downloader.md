# 02 — 可续下载域模块：卷内断点 + 卡死判定 + 无上限退避重试

**要做什么：** 让「下载一卷」这个动作本身变得**能接上、能自愈**——
断流/卡死/连接重置之后，下一次尝试**从已经落盘的字节接着下**，而不是从 0 重来；
每次重试都如实计数、可取消，并且**保签名兼容**既有注入点。

**被谁阻塞：** 01（真网络判据就位，才能判「续没续上」）。

**状态：** ready-for-agent

- [ ] 新增 `src/contest_generator/download_resume.py`（与 `materials_task.py` / `full_task.py` 同层的「下载」域模块；
      两者都要用它，故不放任一侧）：
      - `DownloadResult`：`sha256` / `transferred_bytes` / `attempts` / `resumed_from`（0 = 从头）；
      - `resumable_download(url, dest, on_progress, *, cancel=None, before_retry=None, min_resume_bytes=…)`
        ——**前三参位置与语义不变**，新参数全部关键字可选（既有 monkeypatch 点零改动）；
      - `describe_network_error(exc) -> str`：底层异常 → 中文可行动句子（单源文案）；
      - `retry_delay(attempt) -> float`：2、4、8、16、32、60、60…（**不进设置页**，不引新配置项）。
- [ ] 断点契约逐条成立（判据见 spec「断点契约」表）：
      - 本地 0 字节 → 不发 Range，`resumed_from == 0`；
      - 本地 N 字节且卷 > 1 MB → `Range: bytes=N-`，收到 `206` 且 `Content-Range` 与 N 对齐 → 续写，
        `resumed_from == N`；
      - 小卷（≤ 1 MB）不折腾：整卷重下；
      - 服务器返回 `200`（忽略 Range）→ **丢弃半成品从 0 重下**，并把「服务器不支持续传」写进重试消息；
      - 服务器返回 `416` → 本地比远端大 = 本地坏，删掉从 0 重下；
      - 已下字节 == 卷大小 → **不再发请求**，直接进校验；
      - 到点（size 已知且已达）→ 当成功。
- [ ] **截断必须是失败**（工单 01 探针实测到的既有缺陷，见 `verify-01-baseline.txt`）：
      响应给了 `Content-Length` / `Content-Range` 总长、而实收字节少于它 → **抛错**（可重试，半成品保留），
      **不许**像现在的 `download_part` 那样「读到空就当读完、返回自称成功的 SHA256」。
      用户侧对照：修前是「100% → 校验失败 → 从头再来」，修后应是「网络中断 → 自动接着下」。
- [ ] **清单 size 与对端总长矛盾 = 不可重试**：这属于「发布物与清单不一致」，
      重试必然同样结果，故直报中文错误（如「发布信息不一致（清单 X 字节 / 服务器 Y 字节）」），
      不进重试循环——这条与上面那条必须分开，否则会退化成死循环重试。
- [ ] **无上限退避重试**，但每次经 `before_retry` 如实上报（第 N 次 / 原因 / 已下百分比）；
      退避等待用 `cancel.wait(delay)`：**取消在退避中即刻生效**，不再发起下一次尝试。
- [ ] **校验失败不重试**：续传后 SHA256 与清单不符 → 删半成品、中文报「校验失败（重新下载也不会有变化）」，
      不进入重试循环（重下结果一样）。
- [ ] 单测 `tests/test_download_resume.py`（**不碰网络**，用假尝试函数驱动偏移判定）：
      - `describe_network_error` 对 `URLError` / `TimeoutError` / `ConnectionResetError` /
        `IncompleteRead` / 其它 `OSError` / `HTTPError` 的中文映射，且**可重试与不可重试两类语义分得开**；
      - 退避序列正确；取消置位后**不发起下一次尝试**且立即返回；
      - 上述断点契约每一条各一例（含 `200` 回退、`416`、到点）。
- [ ] **与既有实现可互换**：`download_part` 三参形态可直接替换为 `resumable_download`，
      既有 8 处假下载器断言与既有任务用例**原样通过**。
- [ ] 真网络复跑 01 的五个用例：全绿，证据落 `.scratch/resumable-download/verify-02-probe.txt`；
      01 的**反证脚本同时转绿**（改成从 0 开始时它必须还能红——反证件保留可重跑）。
- [ ] 断点判据的**反向验证留痕**：至少一处「故意让断点逻辑失效 → 探针转红」的证据与本单正证分开存。

## 备注

- 「到点」这个分支是必须的：服务器发的字节数可能比清单 `size` 少（代理改写、断尾），
  此时按「已下 == size」判定成功会在校验阶段才炸——所以要显式分清「到点」与「读干净」。
- `min_resume_bytes` 默认 1 MB：小卷重下比发 Range 更省事，也少一堆边界。
