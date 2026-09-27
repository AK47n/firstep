# 05 — 库更新路径的元数据写盘不是原子的（事务只盖住"新建"那半边）

**要做什么：** 三个库的**更新**动作把元数据 JSON 直接写进**活着的条目目录**——进程被杀
（不是抛异常）会留下**截断的元数据**，那一条目从此读不出来；把这几处收进共享原语
（`atomic_io.atomic_write_text`），既有的"异常期恢复"逻辑保留不动。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

## 现状（实读盘取证，工单 `backlog-closeout/04` 的产物）

`entry_store.write_json` 的 7 个调用点里，**新建**那半边在事务里，**更新**那半边不在：

| 调用点 | 是否在 `entry_transaction` 里 | 备注 |
|---|---|---|
| `library.py:454`（`add_module`） | ✅ 在（`:437`） | 新建模块 |
| `reference_library.py:985`（`add_reference`） | ✅ 在（`:983`） | 新建参考 |
| `reference_library.py:1148`（`archive_reference`） | ✅ 在（`:1144`） | 归档入库 |
| `topic_library.py:229`（`confirm_topics`） | ✅ 在（`:223`） | 一次建多条 |
| `my_devices.py:306` | ✅ 靠目录级 staging + rename | 自建件 |
| **`library.py:712`（`_write_manifest`）** | ❌ **不在** | 调用链：`save_manifest`（`:335`）← `update_platform_identity:367` / `update_module_description:484` / `add_platform_files:545` / `remove_platform_files:586` |
| **`reference_library.py:1085`（`update_reference`）** | ❌ **不在** | 活条目目录上直接写 `reference.json` |
| **`topic_library.py:502`（`update_topic`）** | ❌ **不在** | 活条目目录上直接写 `manifest.json` |

**后果（这条才是要点）**：这三处都有**异常期恢复**（`except` 里删新文件 / 写回旧文本），
但 `write_text` 被**强杀/断电**打断时 `except` 根本不会跑——盘上留下的是**半截 JSON**，
`read_json` 抛 `StoreParseError`，该条目在界面上就是一个打不开的坏条目。
这正是 `record-write-hardening` 那一批在治的同一类病（固定临时名/裸写 → 原子写），
只是当时按"`entry_store` 靠目录级事务兜底"一句放过了——**那句话只对新建立成立**。

## 验收标准

- [ ] 三处改成 `atomic_io.atomic_write_text`（唯一临时名 + 换入 + 清残渣），
      **既有异常期恢复逻辑保留**（原子写解决"被杀"，恢复逻辑解决"业务失败"——两件事都要）。
- [ ] 结构守卫（`tests/test_atomic_io.py::ATOMIC_WRITE_EXCEPTIONS`）不动它（这几处不是"手搓临时名"，
      是**裸写**——守卫现在扫的是前者；若顺手把"裸 `write_text` 到条目目录"也纳入扫描面，
      得先把这份清单钉住，别让它变成永远红的噪音）。
- [ ] 判据（每个库各一条，形状照 `tests/test_materials_apply.py` 的 `test_apply_manifest_write_is_atomic`）：
      注入写失败（目标位置占成目录 / patch 原语）→ **零杂散文件**且**旧元数据不动**；
      再加一条"强杀"模拟（写临时文件后直接抛，不走 `except` 恢复）→ 条目仍可读。
- [ ] 反证探针：撤掉原子写 → 对应判据红（逐条声明 + 对账 + 复原 sha256 逐字节）。
- [ ] 读数落盘：定向（三库）+ 全量 `python -m pytest -n auto -q`。

## 备注

- 射程**只到"元数据 JSON 写盘"**：条目目录里的**内容文件**（`reference_library` 的
  `add_files`/`_write_files`、`topic_library` 的题面 .md）仍是裸写 + 异常期恢复——
  要不要一起原子化，是下一张单的判断（它们更大、更慢，成本不同）。
- 这条与 `backlog-closeout/04` 是一对：**04 只说"核实在案"，05 才是修**。
