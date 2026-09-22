# 03 — 结构钉扩面：full_task 腿 + src 全域 global = 0

**要做什么：** 把「会话态长在 AppContext 上、不长在模块上」这条不变量从 `webapp` 扩到完整包
链路：现有守卫（`tests/test_webapp_state_home.py`）的规则**参数化**（模块点号名 + 文件显示名 +
搬走的名单 + 正向字段），同一份规则跑两条腿（`webapp` 照旧、`full_task` 新增），并新增一条
`src/` 全域的腿：**`global` 语句 = 0**（收走前实测全域只剩 `full_task.py` 一处）。

**被谁阻塞：** 01（正向字段腿需要字段已在）

**状态：** resolved

## 验收标准

- [x] 规则参数化后，`webapp` 那条腿的判据与既有红证**一字不变**（C6 的
      `.scratch/webapp-state-into-ctx/probe-01-pin-red-proof.py` **不改**，仍能跑 —— 已实测复跑，
      读数落 `c6-pin-probe-recheck.txt`）
- [x] 新增 `full_task` 腿：模块级无「会话态形状」赋值 / 无 `global` / 这两个名字（含历史私有
      拼法）不许回到模块级、不许以跨缝 import **或** monkeypatch 路径字符串 **或** 模块对象
      别名（`import …full_task as ft` 后 `ft._FULL_TASK = None`）三种形状回到测试里
      （另加一条「合法用法放行」的反证：`ft.FullDownloadTask` / `ft.SNAPSHOT_FILENAME` /
      `ft.TaskState` 不算违规）
- [x] 正向腿：`AppContext` 必须含 `full_last_check` / `full_task`（防「把状态删干净」式假绿）
- [x] 新增 `src/` 全域腿：`global` 语句数 = 0（**这是最有牙齿的一条**：整个 `src/` 收走前只剩
      一处；将来若某个懒加载缓存真需要 `global` 重新赋值，出路是就地改或收进 ctx——判据文件头
      写明这条出路）
- [x] 每条新腿各带合成红证，**包括容易被别的腿兜住的那几条**（只靠 `global`、裸注解、真树扫描、
      「老签名仍成立」兼容腿、「全域 global 函数」本体）
- [x] 真红证探针：`.scratch/full-update-state-into-ctx/probe-01-pin-red-proof.py`，**显式钉**
      `c6040566`（不写 HEAD：提交之后 HEAD 就是新代码，红证会静默变绿）；base 版 → **7 条 / 4 类**、
      当前树 → 0 条；**base 自校验**（选错 base 时大声失败）；探针与守卫**共用**同一份聚合判据
      （`full_chain_state_violations`）。**扩了一条**（评审指出 src 全域腿此前只有合成红证）：
      它现在也给该腿出 base/当前两份**真源码**读数
- [x] 判据强度探针：逐条腿 stub → 变红，**17/17**，读数落
      `.scratch/full-update-state-into-ctx/guard-strength.txt`（**会真改库内文件、跑完逐字节
      复原——别和测试套件同时跑**）
- [x] `python -m pytest -n auto -q` 全绿

## Comments

### 2026-09-22 20:0x 落地读数

- **守卫单文件**：**15 passed**（扩面前 7 条）；耗时 9s → 中途 **34s** → 加 `_parse` 的
  `lru_cache` 后 **6.6s**（两条腿 × 每个测试文件 × 三条腿各解析一次 = 同一份源码被反复 parse）。
  内存口径写进文件头（缓存键 = 源码文本，值 = 整棵 AST，驻留本场测试，上限 512）。
- **真红证**：`red-proof.txt` —— base `c6040566` → **7 条 / 4 类**（模块级形状 / global /
  名字回模块级 / AppContext 缺字段 / 三个测试文件跨缝），当前树 → **0 条**。
- **`src/` 全域腿的真读数**（本轮补的）：base **97 个文件里有 1 处**
  （`{'src/contest_generator/full_task.py': [73]}`）→ 当前 **97 个文件 0 处**。文件清单取自
  base（`git ls-tree`）：拿当前树清单去 base 取文件会静默漏掉已删文件。
- **判据强度**：`guard-strength.txt` —— **17/17 条腿 stub 后变红**，逐字节复原（sha256
  `8719c95bda23…`）。stub 签名一律 `(*args, **kwargs)`：判据加尾参数缺省后，旧签名 stub 会以
  `TypeError` **假红**（比假绿更阴）。
- **兼容性实测**（不是纸面承诺）：C6 的红证探针**一字未改**仍成立（base `5c9fc8b0` → 6 条，
  当前 → 0 条），读数落 `c6-pin-probe-recheck.txt`。
  ⚠ 跑它要 `PYTHONIOENCODING=utf-8`：它是「先 print 再写 `--out`」，而本机控制台 GBK 打不出 `✗`
  ——这是**既有环境事实**，按验收要求我们不改它的文件；我自己的探针与 C6 的强度探针都已改成
  「先落盘再打印」+ 重设输出流编码。
- **全量**：`python -m pytest -n auto -q` → **5081 passed + 1 skipped / 106.2s**
  （02 收尾 5073 ＋ 本单 8 条结构钉）；前端门禁 **1702 passed / 0 fail**（本单零前端字节）。
- **双轴评审**（固定点 `fe79f57b`，两轴各一个并行子代理）：
  - **Standards 轴：1 条硬违规（H1），已修**——webapp 腿的守卫用例**内联了第二份聚合**
    （`|` + 交集），与文件头自约「不另写一份聚合逻辑」冲突，而且那份副本用的是 `module_object_uses`
    的**缺省**落点（参数化后已经是一份会漂的副本）。**修法**：抽出 `cross_seam_hits(home,
    test_sources)`（三条腿与名单求交集的唯一出处），聚合与两条逐文件用例都从它派生。
  - 判断题的处置：① `StateHome.path` 全程无人读 → **删掉**（模块路径仍由 `WEBAPP_PATH` /
    `FULL_TASK_PATH` 提供；`StateHome` 不再存一份没人读的路径）；② `_EXPECTED_FIELDS` 更名
    `_WEBAPP_EXPECTED_FIELDS` 与 `_FULL_TASK_*` 对称，而 `_MOVED_STATE` **刻意保留旧名**
    （C6 探针 import 它）并在原地写明原因；③ `module_state_violations` 的两个裸源码串位置参数
    易写反（本判据第一版就把 `full_task.py` 当成 `AppContext` 的出处、当场假红）→ 改成
    **关键词参数**；④ `webapp_attribute_paths` → 更名 **`module_attribute_paths`**（C6 的红证
    探针不用它，更名不破坏那条验收；强度探针的 stub 名同步改）。
  - **另一条如实记账**（Divergent Change）：`src/` 全域腿与前两条腿不是严格同一条不变量，仍
    同住本文件的理由与非改名的代价都写进了文件头（**文件不能改名**：C6 探针按模块名 import）。
  - **Spec 轴：无缺失**，两条要求补做 → 已补：① full_task 腿的**「只靠 `global`」「裸注解」
    两格合成红证**（原先只有 webapp 腿有，而那句 docstring 还自称有——一并改准）；② 上面那条
    `src/` 全域腿的真读数；③ 兼容性读数落盘。
  - **范围蔓延两条如实记账**（都不在工单字面，都被评审点出）：① 维护 C6 的强度探针（stub 签名
    / 补新腿 / 落盘顺序与输出编码）——**必需**，否则参数化后旧签名 stub 会产假红；② `_parse`
    的 `lru_cache` —— 性能（三档读数见上），纯函数、调用方只读。同一处还记一条**归属错位**：
    强度探针是**整个守卫文件**的自检，仍住在 C6 目录，读数落本目录（已在探针 docstring 写明）。
- **收尾**：评审子代理落在仓库根的 `standards-review-03.md` 已折进本条并删除；`git status` 只剩
  本单改动。
