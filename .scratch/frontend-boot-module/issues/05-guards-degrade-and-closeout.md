# 05 — 337 行登记表退化 + 不变量进闸门 + 收尾

**要做什么：** 把两张手工守护网换成结构不变量：`fx-guard` 的 337 行 `DOMAINS` 名字表删掉，
`static-import-guard` 的"装载根对账"扩成**全图对账**；新增的不变量（从 boot 可达 / 求值期
零副作用）进前端门禁。然后按仓库口径收尾：红证复跑（base 红 / 工作树绿）、三门禁各一遍、
账本更新。

**被谁阻塞：** 04

**状态：** ready-for-agent

## 验收标准

- [ ] `tests/js/fx-guard.test.mjs` 的 `DOMAINS` 表**删除**（337 行 → 结构不变量），换成：
      ① `index.html` 零 JS 定义（`function`/`const`/`let`/`var`，含 `export` 前缀写法）；
      ② **装载根 `boot.js` 零 `function` 定义**（纯函数单源在 fx/——宿主块搬进 boot.js 之后，
      "双源回退"的检查面必须跟过去，只判 index.html 会半盲；这条同时替代原来逐名正则的
      "宿主不得重定义"语义，且更严：装载根一个 `function` 都不许有）；
      ③ 每个 fx/ui 模块从装载根（boot.js）可达（掉出模块图 = 静默失效，2026-09-12 那类）
- [ ] `tests/js/static-import-guard.test.mjs`：保留"index.html 零 import"＋"清单↔导出对账"
      （根 = boot.js），**新增全图 import↔export 对账**：每个前端模块的每条具名 import 都
      必须是目标模块真导出的名字（解析器要**注释感知**——`import {\n // 注释\n name\n}` 形态
      在现状里真实存在，探针第一版就在这里误报过）
- [ ] `tests/js/import-usage-guard.test.mjs`：根 = boot.js ＋ **零裸装载**（裸装载正是本次
      退场的那条边；清单里再有裸装载 = 回退）
- [ ] **接线不变量进闸门**：boot 装载的 ui 模块中，凡"boot 是唯一装载来源"者 ＋
      `EXPLICIT_WIRING_MODULES` 登记的 11 个，求值期列 0 副作用必须为 0（判据住
      `tests/js/boot-contract.mjs`；登记表自带的 `registryProblems` 体检也要绿——
      "登记了却没搬/没调用"当场红）
- [ ] 守卫自身健康检查：抽取器不静默失效（零 import / 清单条数 / 可达模块数下限），
      照既有守卫先例
- [ ] **红证复跑**：`node .scratch/frontend-boot-module/probe-01-red-proof.mjs` →
      ① base 自校验通过、② ①③ 判据在 base 上红、④ 强度自检四条全成立、③ **当前工作树绿**；
      输出落 `.scratch/frontend-boot-module/red-proof.txt`
- [ ] 收尾三门禁各跑一遍并记数：`python -m pytest -n auto -q`、
      `node --test "tests/js/*.test.mjs"`、`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
- [ ] 账本更新：`CONTEXT.md`（前端纯函数单源/架构要点里"index.html 模块区仅剩 …"那句要
      改成"装载根 = boot.js"的口径）、`.scratch/backlog.md` 第 10 / 13 节那两条挂账结清；
      实测读数（前端门禁 / 浏览器门禁 / pytest 条数）写进 Comments
- [ ] 未顺手做：C6（555 个 id 耦合）、C7（73 个私有符号）、删墓碑注释、9 个"另有 importer"
      模块的顶层接线、`ui/delivery.js` 挂桥的既有事实、F5 竞态

## Comments

（收尾时补：三门禁读数、红证复跑读数、账本改动清单）
