# 01 — 模块正文不许再靠 window 全局桥解析名字（并把该方向立成守卫）

**要做什么：** 前端模块里**用了却没 import** 的名字不再发生——今天靠 `Object.assign(window, …)`
那条老式全局桥侥幸能跑的那几处改成显式 import，并且这个方向**当场有守卫拦**（现在只有反方向
"import 了没用"的守卫，所以它一路漏到线上）。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

**来源**：立项实测（`.scratch/hwcheck-hygiene/probe-bridge-callsites.mjs` / `.txt`）。
评审 P2-12 原建议是"把 `tests/js` 从导出面判据的消费者集合里排除"，实测照做会红 171 处
（见下方验收第 5 条的读数），本单是它的**正确替代**。

## 现状（实测）

- 全仓前端 **609 个名字**经 **66 个模块**的 `Object.assign(window, { … })` 挂上 `window`。
- 处于**调用位**、既没 import 也没在本模块声明的自由标识符：**4 处 / 2 个模块**：

  | 位置 | 用了谁 | 桥的发布方 |
  |---|---|---|
  | `static/js/ui/hwcheck.js:194` | `hwcheckErrorHTML` | `static/js/fx/hwcheck.js:1330` |
  | `static/js/ui/codeeditor.js:1691` | `esc` | `static/js/fx/core.js:123` |
  | `static/js/ui/codeeditor.js:2976` / `:2982` | `moveTab` | `static/js/fx/codeeditor.js:412` |

- 危害不是"风格"：`ui/hwcheck.js:194` 是工单 `hwcheck-hardening/07` 的产物——真浏览器用例
  （`tests/browser/hwcheck.spec.mjs:701`）**真的绿**（桥兜住了），但那一行没有 import 边，
  所以在导出面判据 D 眼里 `fx/hwcheck.js::hwcheckErrorHTML` **仍然是只被测试消费的死导出**。
  也就是说：产品行为的修复在运行态成立、在守卫眼里不成立。

## 验收标准

- [ ] 上表 4 处改成显式 import（按各自文件 import 段的既有风格：`ui/hwcheck.js` 并入它那条
      多行 import 块；`ui/codeeditor.js` 的 `esc` 并入既有 fx import 段、`moveTab` 并入
      `fx/codeeditor.js` 那条）；**页面行为零变化**。
- [ ] 新增守卫 `tests/js/window-bridge-guard.test.mjs`，**判据本体进 `tests/js/boot-contract.mjs`**
      （单源，照 `export-surface-guard` 的先例）：
      · 口径 = `static/js/{fx,ui}/**` 模块正文经 `maskNonCode` 掩码后，处于**调用位**
        （前面不是 `.`、不是属性名）的自由标识符，不得命中「window 桥发布的名字」；
      · 排除：本模块 import 的本地名（`locals`）、本模块自身的声明（function / const / let / var / class）、
        本模块自身的导出；
      · 桥的发布清单从源码现算（解析 `Object.assign(window, { … })` 的对象字面量键），**不写死名单**。
- [ ] 守卫自带两条自检：① **正向对照**——注入一处"只靠桥解析"的调用，必须报出；
      ② **掩码自检**——名字只出现在注释/字符串里时**不算**依赖（照
      `export-surface-guard.test.mjs` 的"注释喂绿自检"先例）。
- [ ] **反证**：撤掉 `ui/hwcheck.js` 那条新 import → 前端门禁红；复原后 sha256 逐字节相同
      （探针落 `.scratch/hwcheck-hygiene/probe-01-red.py`，读数 `probe-01-red.txt`）。
- [ ] `tests/js/export-surface-guard.test.mjs` 文件头补一段（**只记账、不改口径**）：
      消费者集合**不许**排除 `tests/js`——实测消费者 169 → 排除后 11、零消费者导出 0 → 171
      （`fx/task.js` 18 / `fx/module.js` 16 / `fx/hwcheck.js` 15 …）；并写明"桥依赖归零之后，
      判据 D 的产品侧口径才真的成立"。
- [ ] 读数：前端门禁 `node --test "tests/js/*.test.mjs"` 全绿（1807+）且**条数只增不减**；
      浏览器门禁 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` 全绿
      （本单动了 `ui/hwcheck.js` 与 `ui/codeeditor.js`，二者都在浏览器门禁的落点里）。
- [ ] 顺手记一句：`fx/codeeditor.js` 的 `esc` 与 `moveTab` 现在各自多了一条 import 边，
      导出面判据 D 的消费者计数会变——**别把计数写进任何地方**（本条只是提醒评审时不误判）。
