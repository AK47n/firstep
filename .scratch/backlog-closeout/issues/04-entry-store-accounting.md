# 04 — `entry_store.write_json` 的裸写：核实 + 记账（不改代码）

**要做什么：** 把 `record-write-hardening` 留在账上的那句「`entry_store.write_json` 的裸
`write_text`——它靠目录级事务兜底，不是本次这一族」**从断言变成可核对的证据**，
并写进 `backlog.md`（免得下一轮又当新发现重开）。**不改任何产品代码。**

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

## 现状（待核实，带 file:line）

- `src/contest_generator/entry_store.py` 的 `write_json(entry_dir, filename, data)`：
  直接 `(entry_dir / filename).write_text(...)`，**无临时名、无 `os.replace`**。
- 库里声称它由**目录级事务**兜底（`entry_transaction` 那一族：先在暂存目录里写、再整体换入；
  半写不会落在正式条目目录里）——**本单要把这条读实**：
  1. 写侧调用链：哪些写者用 `write_json`（`library.py` / `reference_library.py` /
     `topic_library.py` / `master_store.py`？），它们是否都在 `entry_transaction` 里；
  2. 事务的暂存→换入语义：半写会落在哪里、失败怎么清；
  3. **有没有绕过事务的调用点**（那才是真风险）。

## 验收标准

- [ ] 逐条取证（读代码 + 必要时写一个**只读探针**或小用例）：
      `write_json` 的全部调用点、各自是否在事务里、暂存目录与换入点在哪；
      **结论二选一**：① 全在事务里 → 记为"设计如此，改动无收益"；
      ② 有绕过事务的调用点 → **本单不修**，但把它落成一张新工单的候选（写清 file:line 与后果）。
- [ ] 结论写进 `backlog.md` §24 的那条（把"明确没修"改成"已核实：为什么不需要修/或已开单"），
      附一句**复现方式**（下一个人怎么自己核）。
- [ ] 若发现"绕过事务"的调用点，开单（`.scratch/backlog-closeout/issues/05-*.md`，`ready-for-agent`），
      本票结论段点名它。
- [ ] 反向对照：**不做**任何产品代码改动（`git status` 里 `src/` 零改动）；若最终认为该修，
      在本票结论段写明理由并另开单，别在本单里顺手改。

## 备注

- 本单的价值是**把账做实**：`record-write-hardening` 那批按"范围外"划走了它，
  但只留了一句判断；下一轮盘点会重复问"这条到底要不要修"。
- 判据不新造机器：结论靠**读代码 + 调用点清单**，必要时补一条结构用例把
  "`write_json` 的调用点必须在事务里"钉住（那样才是机器盯，而不是文档承诺）。
