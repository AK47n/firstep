# 03 — 收口：三套门禁 + 文档回改 + 边界记账

**要做什么：** 把这轮的账做完：三套门禁现跑、真文件反证复核、四处文档回改（守卫注释 / backlog /
CONTEXT 硬数 / 本机环境交接区），并把"够得着 7 条 / 够不着 14 条"的边界写到下一轮接手的人
一眼能看见的地方。

**被谁阻塞：** 01（形态与判据）、02（真像素读数）。

**状态：** ready-for-agent

- [ ] **三套门禁现跑**（顺序照纪律：**先浏览器门禁单独跑，再全量 pytest**，不并行）：
      前端 `node --test "tests/js/*.test.mjs"`、浏览器
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（单独跑）、全量 `pytest -q`；
      三份读数入库 `.scratch/disabled-forms/`。**读数时间戳必须晚于最后一次改产品面的时间。**
- [ ] **真文件反证复核**：照 `.scratch/code-contrast/probe-04-real-file-red-proof.py` 的写法，
      在**真文件**上把 `opacity` 放回三处之一（或注入一条新的 `.x.off { opacity: .4 }`）→
      前端门禁**退出码 1** 且文案逐字点名 → 复原后 sha256 与改前一致。
- [ ] **守卫注释**：把本轮口径写进 `tests/js/css-tokens.test.mjs` 腿⑧ 的头注释（登记表两档类别 /
      反向嫌疑信号 / 双向对账 / `@keyframes` 与 `:not(…)` 的边界 / **14 条不在射程 + 为什么**），
      并订正 ⑥ 原来那句"`.module-card.off` 这类别的类名不在本判据射程——要收得先给它们改名"。
- [ ] **`backlog.md` 开 §33**：本轮账（问题 / 做了什么 / 读数 / 双轴评审处置）+「仍开着的」
      （至少：① 全站 `opacity` 全量登记（腿⑩）与词法代理的边界；② §31/§32 原有的叠加态定价 /
      `--accent` 控件描边非文字 3:1 / `.pin-subtitle` 的 `var(--fg)` 笔误 / 图例色点令牌归属）。
- [ ] **`CONTEXT.md`**：若 01 单动了 `CONTRAST_PAIR_COUNT` / `CONTRAST_FAMILY_CELL_COUNT`，
      「对比度契约」那行的硬数同批回改；词表**不新增条目**（形态口径属样式细节，族面已有记账）。
- [ ] **`docs/agents/local-environment.md` §0**：把"留给下一轮"里的
      「② 禁用态剩下两处"别的类名"的 opacity 形态」划掉，并记本轮交接一句
      （改了什么、读数是几、下一轮的第一件事是什么）。
- [ ] **双轴 code-review**（Standards + Spec）跑一轮，发现逐条处置并记进票尾。
- [ ] **票尾「结论（读数与账）」表**：三套门禁读数 / 真像素 before→after / 红证 / 文档四处 /
      范围外逐条。

**范围外**：发版（另开一轮）；AI 与后端路径（本轮零改动）。
