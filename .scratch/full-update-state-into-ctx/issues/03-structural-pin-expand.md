# 03 — 结构钉扩面：full_task 腿 + src 全域 global = 0

**要做什么：** 把「会话态长在 AppContext 上、不长在模块上」这条不变量从 `webapp` 扩到完整包
链路：现有守卫（`tests/test_webapp_state_home.py`）的规则**参数化**（模块路径 + 模块对象名 +
搬走的名单 + 正向字段），同一份规则跑两条腿（`webapp` 照旧、`full_task` 新增），并新增一条
`src/` 全域的腿：**`global` 语句 = 0**（收走前实测全域只剩 `full_task.py` 一处）。

**被谁阻塞：** 01（正向字段腿需要字段已在）

**状态：** ready-for-agent

## 验收标准

- [ ] 规则参数化后，`webapp` 那条腿的判据与既有红证**一字不变**（C6 的
      `.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py` **不改**，仍能跑）
- [ ] 新增 `full_task` 腿：模块级无「会话态形状」赋值 / 无 `global` / 这两个名字（含历史私有
      拼法）不许回到模块级、不许以跨缝 import **或** monkeypatch 路径字符串 **或** 模块对象
      别名（`import …full_task as ft` 后 `ft._FULL_TASK = None`）三种形状回到测试里
- [ ] 正向腿：`AppContext` 必须含 `full_last_check` / `full_task`（防「把状态删干净」式假绿）
- [ ] 新增 `src/` 全域腿：`global` 语句数 = 0（**这是最有牙齿的一条**：整个 `src/` 收走前只剩
      一处；将来若某个懒加载缓存真需要 `global` 重新赋值，出路是就地改或收进 ctx——判据文件头
      写明这条出路）
- [ ] 每条新腿各带合成红证，**包括容易被别的腿兜住的那几条**（只靠 `global`、裸注解、真树扫描）
- [ ] 真红证探针：`.scratch/full-update-state-into-ctx/probe-01-*`，**显式钉收走前那个提交**
      （不写 HEAD：提交之后 HEAD 就是新代码，红证会静默变绿）；base 版 → 违规清单非空、
      当前树 → 0 条；**base 自校验**（选错 base 时大声失败，不许产假绿）；探针与守卫**共用**
      同一份聚合判据（不许再写一份会漂移的聚合逻辑）
- [ ] 判据强度探针：逐条腿 stub → 变红，读数落盘（**会真改库内文件、跑完逐字节复原——别和
      测试套件同时跑**）
- [ ] `python -m pytest -n auto -q` 全绿
