# 05 — 收口：领域词表补词条 + 台账记账

**要做什么：** 这一轮立起来的缝写进领域词表（下一个人不用读完 `tests/js/` 147 个文件才知道缝在哪、
谁守、怎么扩），并把本轮结果记进 `.scratch/backlog.md`（C5 卡的剩余部分落地、以及仍未立项的那几条）。
端到端行为：读完 `CONTEXT.md` 就知道"ui 层的 interface 是 DOM 契约、由哪两处守、新模块怎么加"。

**被谁阻塞：** 02、03、04（词条要写的是**落地后的事实**，不是计划）。

**状态：** resolved

- [x] `CONTEXT.md` 补词条 **「ui 层测试缝」**（只记领域事实）：缝 = **DOM**；两层守卫
      （静态健全性判据单源 `tests/js/ui-dom-contract.mjs`；行为契约 `tests/browser/ui-contract.spec.mjs`）；
      选件口径一句话；**刻意不判**那条（不要求每个 `init*` 导出都被 index.html 具名导入）也写进去了。
- [x] `docs/agents/workflow.md`「闸门」表补浏览器门禁一行（触发落点 + 命令 + 实测耗时），
      用法代码块补 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`，
      并把「不联网」那条改成「测试不打网络、不吃 secret（CI 装依赖当然要联网）」。
- [x] `docs/agents/local-environment.md` 第 2 节补本机口径与读数（四个 spec / 26 条、跑法必须串行、
      前置 `npm install` + `npx playwright install chromium`、与闸门接线状态、红证工具在哪）。
- [x] `.scratch/backlog.md` 新增第 13 节：C5 卡剩余部分落地；**仍挂账三条写清为什么**
      （id 耦合改造 / 接线搬出 HTML / 产品侧 F5 竞态），另注明 backlog 第 10 节那两条本轮未动。
- [x] `python -m pytest` 全绿（含文档守卫族 `test_repo_language.py` / `test_onboarding_docs.py` /
      `test_readme.py`）+ 前端门禁全绿；提交信息中文。

## Comments

（见下面「落地记录」段。）

## 落地记录

| 项 | 落点 | 说明 |
|---|---|---|
| 领域词条 | `CONTEXT.md` 词表新增「ui 层测试缝」 | 只记事实：缝在 DOM、两层守卫各是谁、选件口径、刻意不判什么；带实现落点三处 |
| 闸门文档 | `docs/agents/workflow.md`「闸门」表 + 用法块 | 浏览器门禁的落点（四类）与命令；「整套」现在含它 |
| 本机口径 | `docs/agents/local-environment.md` 第 2 节 | 26 条用例的总数、串行理由、前置与读数、红证工具位置 |
| 台账 | `.scratch/backlog.md` 第 13 节 | 落地两条 + **仍挂账三条**（都写明为什么） |

`CONTEXT.md` 词条按仓库存档格式写（表格一行、`|` 分隔、左列术语右列实现），未写流程细节与待办
——待办真源是 `.scratch/backlog.md`。文档守卫族 125 passed（`test_repo_language` /
`test_onboarding_docs` / `test_readme` / `test_ci_workflow` / `test_prepush*`）。
