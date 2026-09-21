# 03 — 新判据进闸门 ＋ 账本收尾

**要做什么：** 把 01 立的判据接进前端门禁（`node --test "tests/js/*.test.mjs"`），**当场生效**：
此后任何模块新增一个自己用不到的具名 import，**推之前就红**。然后按仓库口径收尾：账本更正
（`.scratch/backlog.md` §10 那条候选结清 ＋ **更正工单 02 的记账**）＋ 本机读数写回
`docs/agents/local-environment.md` ＋ 三门禁各跑一遍记数。

**被谁阻塞：** 02（清点处置 12 处 ＋ 级联）

**状态：** ready-for-agent

## 验收标准

- [ ] 用例住**一处**并说明取舍：优先扩**既有** `tests/js/import-usage-guard.test.mjs`（这条不变量本就
      由它守，"一条判据一个文件"）还是新开文件——取舍写进 Comments。
- [ ] 闸门内用例（**每条都能红，不是"断言为空"**）：
      ① **抽取器体检**：模块数 / 语句数 / 具名数三条**保守下限**都在，且**正向对照**——注入一条死 import
      必须报出（抽取器静默失效要当场红，而不是断言为空变真空绿；先例 `ui-dom-contract.test.mjs`
      「那种绿比红更坏」）；
      ② **判据 = 0**：`static/js/**` 全部 132 个模块（含 js/ 根 `app.js` / `boot.js`）零未使用具名；
      ③ **假绿反例与反向对照进闸门**（合成片段，注入自带自检）：注释 / 块注释 / 行尾注释 / 字符串 /
      正则 / 模板文本段 / 更长标识符 / `$` 边界里的同名词**必须报出**；模板表达式 / 再导出清单 /
      别名本地名 / 裸装载**必须不报**（防假红）。
- [ ] 账本：
      ① `.scratch/backlog.md` §10 末那条候选（"9 处清点前就已死的模块级 import"）**结清**，
      并写进**更正**：正确口径实测 **12** 处（不是 17/18）；`WRITE_GUARD_ACTIONS ×4` 是**别名误报**
      （`WG.fix` / `WG.revise` / `WG.task` / `WG.params` 在正文里真被用着，实测是 ×5 处误报）；
      **新发现**：死 import 会给判据 D 当**假消费者**（`fx/core.js::downloadedPercent` 的唯一消费者
      就是一条死 import，本轮级联摘掉它的 `export`）；判据面已从装载根扩到 132 个模块并进闸门。
      ② `docs/agents/local-environment.md`：更新前端门禁 / 浏览器门禁 / pytest 三条读数，
      并补记本轮的判据面与落点（`tests/js/*.test.mjs` 自动进闸门；改动落 `static/js/ui/` 触发浏览器门禁）。
      ③ `CONTEXT.md`「前端纯函数单源」一带如需补一句口径（零未使用具名已覆盖每个模块），按实补。
      ④ **不改**已 resolved 的 `.scratch/export-surface-guard/issues/02-sweep-111-exports.md`
      （照工单 03 先例"那份记录属已 resolved 的工单，本轮不改，如实挂在这里"）——更正写在 ① 与本工单。
- [ ] **三门禁各跑一遍并记数**（最终状态上）：`node --test "tests/js/*.test.mjs"`（基线 1688 ＋ 本工单新增）／
      `python -m pytest -n auto -q`（基线 5049 passed + 1 skipped）／
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（基线 26）——读数与耗时写进 Comments；
      并按工单 02 §⑥ 那条环境事实注明**行尾（LF / CRLF 检出）**对读数的影响。
- [ ] 工单 02 留下的读数复核（`red-proof.txt` / `diff-proof.txt` / `verify-removal.txt`）在**最终状态**上
      仍然成立（新增的守卫文件会进"消费侧模块"计数，若红证读数因此漂移，如实记账）。
- [ ] **未顺手做**（与 spec「范围外」一致，逐条列进 Comments）：常量形态恢复、C6（555 个 id）、
      C7（73 个私有符号）、`.scratch` 一次性探针的失效修复、装载根"零裸装载"的重议、
      `tests/js/**` 与 `tests/browser/**` 自身的未使用具名、零调用私有死函数的清理。

## Comments

（实现时补：落点取舍、闸门内用例清单、账本四处、三门禁读数、未顺手做。）
