# 04 — 状态面新增三字段：retrying / retry_count / error_kind

**要做什么：** 让界面**知道**「现在是在重试、重试了几次、失败属于哪一类」——
在这之前前端只能从 `error` 文案里猜，猜不到就只能把「慢」「卡」「失败」显示成一个样子。

**被谁阻塞：** 03（任务层有重试状态可投影）。

**状态：** ready-for-agent

- [ ] `task_status`（`materials_task.py`）与 `full_task_status`（`full_task.py`）**新增**三个字段：
      `retry_count: int`（当前卷累计自动重试次数）、`retrying: bool`（是否正处在退避等待中）、
      `error_kind: str`（`""` / `"network"` / `"verify"`）。
- [ ] **既有字段一个不改**（`state` / `parts` / `total_downloaded_bytes` / `total_bytes` / `speed_bps` /
      `current_part_name` / `error` / `message`）——前端零破坏；新增字段在 idle 空态也要在场（值 0 / false / ""）。
- [ ] `message` 字段语义定死并接线：**进行中的摘要**（重试中原样透出），**终态清空**（终态原因只走 `error`）。
- [ ] 单测：三字段在 idle / downloading / 重试中 / failed(network) / failed(verify) / done 六态下的取值矩阵；
      以及一条**结构守卫**——断言 status 响应**包含**这 8 个既有键（防以后有人顺手改名）。
- [ ] 端点侧不改协议：`/api/update/full/status` 与资料库 `status` 直接透出新字段即可，**不加新端点**。

## 备注

- `error_kind` 是给前端**选话术**用的，不是给用户看的字符串——前端不许解析 `error` 文案来分类。
- 本单不动前端：前端消费在 05。
