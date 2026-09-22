# 04 — 文档与账本收尾（三处旧名字引用 + backlog 两处挂账）

**要做什么：** 把搬完之后会变假的旧名字引用改对，并把 `backlog.md` 里「仍挂账」的两处改成
已落地（写明 C7 是唯一剩下的、且只是验收尺）。**不改任何行为。**

**被谁阻塞：** 01、02（名字已经是新的，才谈得上改引用）

**状态：** resolved

## 验收标准

- [x] `static/js/fx/task.js` 那行注释里的 `_running_task_execs` 改成新归属（**只改这一行注释里
      的名字，零行为改动**；跑前端门禁回归确认）
- [x] `materials_task.ApplyTask` 类 docstring 的「webapp 模块级单例」改成新归属
- [x] `CONTEXT.md` 任务推进词条里的「webapp 模块级 `_running_task_execs`」改成新归属
- [x] `.scratch/backlog.md` 第 11 节末：C6 从「仍挂账、未立项」改成「已落地（工单
      webapp-state-into-ctx/01–04）」，并写明 C7 是唯一剩下的、只是验收尺
- [x] `.scratch/backlog.md` 第 15 节末：「仍然挂账的（评审候选里最后两条）」改成只剩 C7，
      C6 已落地（说明口径：只换归属、语义未变）
- [x] `docs/agents/local-environment.md` 补一行本轮会话事实（本轮没起服务器 / 读数），
      第 0 节发布落差表不动
- [x] 全仓 grep 三个旧名字：只剩 `.scratch/` 历史证据与 backlog 的「已落地」叙述，
      **加上结构钉自身**（`tests/test_webapp_state_home.py` 的历史拼法名单 + 合成红证字符串，
      删掉即拆判据）与 `tests/test_download_status_surface.py` 里那个**同名局部工厂**
      `def _materials_task(...)`（与旧全局无关）——源码 / 前端 / CONTEXT 里一处不剩
- [x] `python -m pytest -n auto -q` 与 `node --test "tests/js/*.test.mjs"` 全绿

## Comments

### 2026-09-22 落地读数

- **读数**：`python -m pytest -n auto -q` → **5070 passed + 1 skipped**；
  `node --test "tests/js/*.test.mjs"` → **1702 passed / 0 fail**（前端只动过 `fx/task.js` 一行
  注释，属回归确认）。
- **零行为改动核对**：`git diff -U0 -- src tests` 只有 `materials_task.py` 一行 docstring +
  `fx/task.js` 一行 JSDoc，无可执行语句改动、`tests/` 零改动（Spec 轴独立复核）。
- **grep 口径更正（Spec 轴 + Standards 轴都点到）**：验收第 7 条原来写「源码 / 测试 / 前端 /
  CONTEXT 里一处不剩」——**字面做不到**：结构钉 `tests/test_webapp_state_home.py` 里那 40+ 处
  是**检测目标**（历史拼法名单 + 合成红证字符串），删掉等于拆判据；`tests/test_download_status_surface.py`
  另有**同名局部工厂** `def _materials_task(...)`（与旧全局无关）。该条已改成「只剩结构钉的
  检测目标 / `.scratch/` 历史证据 / 同名局部工厂」——留着一条永远勾不掉的假标准比不写更糟。
- **台账**：`backlog.md` 新增 **§17**（C6 的落地账：做法 / 判据三处 / 红证与读数指针 / 剩余），
  第 11、15 节末改成「C6 已落地、**C7 是唯一剩下的且只是验收尺**」，两处都前指 §17。§17 里的
  两条工具事实**退化成指针**（真源在 `docs/agents/local-environment.md` 的本轮会话段，
  UTF-16LE 那条更早的真源是 `tests/js/windows-text-encoding.test.mjs` 的文件头——Standards 轴
  点出「同一事实四处各一份、谁是真源被写乱」，已按建议收成一条链）。
- **本机事实**：本轮一次服务器都没起；收尾 **2026-09-22 18:28** 实测 8000/8020/8021/8791
  都没在听、无残留 python。**中间踩了一脚并如实记账**：18:27 曾在两个内核分配端口
  （11883/13157）看到 `contest_generator.webapp` 子进程——那是**并发跑的全套 pytest 自己起的
  夹具后端**（跑完自行消失），不是孤儿；这条「别把套件的临时后端当残留」也写进了
  `local-environment.md` 的本轮段。
- **留在原地没改的一处**（Spec 轴专门问过）：`full_task.py` 里两处「webapp 模块级单例」说的是
  **完整包链路**（它的会话态今天确实还在 `full_task` 模块级，经 `last_check()` /
  `get_full_task()` 被 webapp 端点使用）——正落在 spec「范围外：完整包链路的模块级会话态
  （另议）」，故不动；措辞上「webapp 模块级」略偏（实际长在 `full_task` 模块），如实记在这里。
- **双轴评审**：Spec 轴（缺 1 条即为上面的 grep 口径 → 已改；范围蔓延 3 条 → §17 与
  local-environment 串成单链、CONTEXT 的括注保留因它标了工单号）；Standards 轴（硬违规 1 条 =
  同一条 grep 口径 → 已改；味道 3 条 → 单源化 + 补锁的命名理由 + 给强度探针补「会真改库内文件、
  别和套件同时跑」的告警）。两轴真跑复核的读数与本节一致。
