# 05 — 收口：领域词表补词条 + 台账记账

**要做什么：** 这一轮立起来的缝写进领域词表（下一个人不用读完 `tests/js/` 147 个文件才知道缝在哪、
谁守、怎么扩），并把本轮结果记进 `.scratch/backlog.md`（C5 卡的剩余部分落地、以及仍未立项的那几条）。
端到端行为：读完 `CONTEXT.md` 就知道"ui 层的 interface 是 DOM 契约、由哪两处守、新模块怎么加"。

**被谁阻塞：** 02、03、04（词条要写的是**落地后的事实**，不是计划）。

**状态：** ready-for-agent

- [ ] `CONTEXT.md` 补一条词条 **「ui 层测试缝」**（只记领域事实，不记待办、不写流程细节）：
      缝的位置 = **DOM**（模块绑的选择器 + 绑上之后的可观察结果就是它的 interface，`initXxx()` 是唯一入口）；
      两层守卫——静态健全性（id 存在性 + 装载可达性，落点在 `tests/js/ui-dom-contract.*`）与
      行为契约（`tests/browser/ui-contract.spec.mjs`，真页面 + 真后端）；选件口径一句话。
- [ ] `CONTEXT.md` 若有涉及「前端门禁」的既有行，把**浏览器门禁**与它并列写清（哪类落点跑哪一支）。
- [ ] `docs/agents/workflow.md`「闸门」表补一行：浏览器门禁的触发落点与命令。
- [ ] `docs/agents/local-environment.md` 第 2 节补一段：本机跑浏览器门禁的命令与前置
      （`npm install` + `npx playwright install chromium`）、夹具的端口策略（**每个 spec
      各向内核要一个空闲端口**，不再固定 8791）、以及本轮实测的读数；把「HEAD 上 6 绿 3 红」
      那句**更新成实测后的真实状态**（该句现在已过期：实测是 **14 绿 7 红**，且根因与修法都变了）。
      注：端口事实已在工单 01 里**当场改过**（CLAUDE.md 的更新纪律），本条只做收口复核。
- [ ] `.scratch/backlog.md`：C5 卡的剩余部分（ui 测试缝 + browser 用例接闸门）标注落地；
      仍然挂账的三条继续留账且写清为什么——① `index.html` 的 555 个 id 耦合**改造**（本轮只让它
      变得可测，没动标记结构）；② 把接线搬出 HTML（`js/boot.js`）；③ 产品侧「F5 重载慢过 1.5 秒
      会被自己关掉」的竞态（本轮只在夹具侧绕开）。
- [ ] `python -m pytest` 全绿（文档守卫族 `tests/test_repo_language.py` / `test_onboarding_docs.py`
      会看这几份文件）+ 前端门禁全绿；提交信息中文。

## Comments
