# 04 — 文档与账本收尾（三处旧名字引用 + backlog 两处挂账）

**要做什么：** 把搬完之后会变假的旧名字引用改对，并把 `backlog.md` 里「仍挂账」的两处改成
已落地（写明 C7 是唯一剩下的、且只是验收尺）。**不改任何行为。**

**被谁阻塞：** 01、02（名字已经是新的，才谈得上改引用）

**状态：** ready-for-agent

## 验收标准

- [ ] `static/js/fx/task.js` 那行注释里的 `_running_task_execs` 改成新归属（**只改这一行注释里
      的名字，零行为改动**；跑前端门禁回归确认）
- [ ] `materials_task.ApplyTask` 类 docstring 的「webapp 模块级单例」改成新归属
- [ ] `CONTEXT.md` 任务推进词条里的「webapp 模块级 `_running_task_execs`」改成新归属
- [ ] `.scratch/backlog.md` 第 11 节末：C6 从「仍挂账、未立项」改成「已落地（工单
      webapp-state-into-ctx/01–04）」，并写明 C7 是唯一剩下的、只是验收尺
- [ ] `.scratch/backlog.md` 第 15 节末：「仍然挂账的（评审候选里最后两条）」改成只剩 C7，
      C6 已落地（说明口径：只换归属、语义未变）
- [ ] `docs/agents/local-environment.md` 补一行本轮会话事实（本轮没起服务器 / 读数），
      第 0 节发布落差表不动
- [ ] 全仓 grep 三个旧名字：只剩 `.scratch/` 历史证据与 backlog 的「已落地」叙述，源码 /
      测试 / 前端 / CONTEXT 里一处不剩
- [ ] `python -m pytest -n auto -q` 与 `node --test "tests/js/*.test.mjs"` 全绿

## Comments
