# 01 — 修「firstep 一打开就卡死、强刷也不行」（index.html 死导入打崩整页）

**要做什么：** 打开 firstep（http://127.0.0.1:8000/）页面能正常初始化——模块库网格、导航、
推荐区都可用；不再出现「页面看着像卡死、强刷也救不回来」的现场。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 真机复现（干净 Chrome，独立 user-data-dir，CDP 读控制台）：
      `Uncaught SyntaxError: The requested module '/js/fx/module.js' does not provide an
      export named 'applyGroupRadio'` + 模块网格 **0 张卡**。
- [x] 排除服务端与缓存：`/api/health` 200、`index.html`/`module.js` 一一 200 且
      `Cache-Control: no-store`；`curl.exe` 落盘的 `module.js` 与仓库**逐字节一致（diff 0 行）**
      ——坏的是磁盘上的文件，不是缓存/服务端。
- [x] 根因：`165665e5`（功能组「显式选择」评审整改）从 `fx/module.js` 删掉 `applyGroupRadio`，
      `index.html:4399` 的 import 漏删该名，且全仓**无调用点** → import 解析即抛 SyntaxError，
      整页脚本（app.js + ui/*）全灭。
- [x] 修复：删掉 `index.html` 的那一个死导入名（一行，无其它改动）。
- [x] 补守卫 `tests/js/static-import-guard.test.mjs`（3 例）：抽 `index.html` 全部 import 清单 →
      逐条对账模块源码导出集合 + 路径存在性 + 抽取器不静默失效。
- [x] 反证（守卫有效性）：把 `applyGroupRadio` 加回 import → 守卫红；删掉 → 绿。
- [x] 真机绿证：干净 Chrome 打开 → `readyState=complete`、**moduleCards=93**、
      `window` 桥三函数齐、导航可点、**运行时异常 0**。
- [x] 回归：`node --test tests/js/*.test.mjs` **1470 pass / 0 fail**（+3 新用例）；
      `pytest -q` **4036 passed, 1 warning**（与修复前同数，零回归）。

## 实施记录（2026-09-13）

**用户报告**：「点开 firstep 后卡住，跟之前一样要 Ctrl+F5 强刷后才行」→ 随后「现在强刷也不行了卡住了」。

**诊断路径（全部只读取证）**：

| 步骤 | 结果 | 说明 |
|---|---|---|
| 服务健康 | `/api/health` 200 `{"ok":true}`；`/` 200（616585 字节） | 后端无辜 |
| 静态资源头 | `Chat no-store` + ETag/Last-Modified | 不是浏览器缓存策略问题 |
| 126 个前端 JS `node --check` | 全绿 | 不是语法错误文件 |
| **CDP 读页面控制台** | **1 条 SyntaxError（死导入）** + moduleCards=0 | 定位到 import 断链 |
| `grep applyGroupRadio` | 只命中 `index.html:4399`（import），**无调用点** | 确认是死导入、可安全删 |
| `git log -S` | `165665e5` 删除该导出、`index.html` 未同步 | 根因提交 |
| 服务端文件 vs 仓库 | `curl.exe` 落盘比对：**逐字节一致**（37562 B / diff 0） | 排除「服务跑的是别处副本」 |
| 干净 Chrome 复现 | 修复前：SyntaxError + 0 卡；修复后：**无异常 + 93 卡** | 红/绿证 |

**为什么既有守卫漏了**：`tests/js/fx-guard.test.mjs` 是**单向**检查——
① 「模块导出 `DOMAINS` 登记的名字」（只看模块侧）；② 「`index.html` 不得重复定义」（防双源回退）。
没有任何用例问「`index.html` 导入的名字，模块里到底有没有」——本次补上这个方向。

**留口**：
1. 用户侧动作：**普通刷新（F5）即可**（静态资源 `no-store`），不必强刷。
2. 同类隐患排查：新守卫一次覆盖 `index.html` 的全部 import（本轮实跑 = 0 处不一致）。
3. 未做（范围外）：把守卫扩到 `ui/*.js` 之间的裸路径 import（浏览器绝对路径 `/js/app.js`
   在 node 侧解析不到，需要 import map 或构造虚拟模块——本轮按「先守住入口页」落最小可用守卫）。
