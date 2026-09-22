# 04 — 账本与文档收尾（C6 的尾巴结清）

**要做什么：** 把这次换归属之后**变成假话**的旧描述改对，并把账记进该记的地方：`CONTEXT.md`
的一键全量下载词条、`full_task.py` 的两处「webapp 模块级单例」话术与 `set_full_task` 的
docstring、`backlog.md` 新增一节、`docs/agents/local-environment.md` 补本轮会话段。

**被谁阻塞：** 01、02、03

**状态：** ready-for-agent

## 验收标准

- [x] `full_task.py` 的两处「webapp 模块级单例」话术（模块级注释块、`FullDownloadTask` 类
      docstring）与 `set_last_check` 的「状态单源在本模块」**已随工单 01 改对**——删掉模块状态
      那一刻它们就成了假话，那时一并改的；本条**不重复做**，只核对
- [ ] `CONTEXT.md` 一键全量下载词条：照 C6 给任务推进词条补
      `AppContext.running_task_execs` 的同款写法，把状态归属补明（含工单号）
- [ ] `backlog.md` 新增一节：做法（只换归属 + 补一把锁）/ 判据三处 / 红证与读数指针 / 剩余；
      并写明**C6 的尾巴就此结清**（架构评审候选里只剩 C7，而 C7 只是验收尺、未立项）
- [ ] `docs/agents/local-environment.md` 补本轮会话段：本轮不起服务器、收尾端口实测（8000 /
      8020 / 8021 / 8791 与残留 python 进程）、三条读数（pytest / 前端门禁）、本轮量到的工具
      事实（若有）；**第 0 节的发布落差表不动**（本轮不进任何发布包）
- [ ] 零行为改动核对：`git diff -U0 -- src tests` 只应有 docstring / 注释级改动（在 01/02 之后）
- [ ] 双轴评审（固定点 = 01 之前那个提交，两轴各一个并行子代理），结论落账；范围蔓延一条
      不留（C6 那次抓到的两条：判定次序被挪、顺手抽常量——本轮的对照检查项）
- [ ] `python -m pytest -n auto -q` 全绿；`node --test "tests/js/*.test.mjs"` 全绿
