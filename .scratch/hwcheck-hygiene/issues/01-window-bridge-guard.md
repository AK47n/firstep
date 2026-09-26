# 01 — 模块正文不许再靠 window 全局桥解析名字（并把该方向立成守卫）

**要做什么：** 前端模块里**用了却没 import** 的名字不再发生——今天靠 `Object.assign(window, …)`
那条老式全局桥侥幸能跑的那几处改成显式 import，并且这个方向**当场有守卫拦**（现在只有反方向
"import 了没用"的守卫，所以它一路漏到线上）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

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

- [x] 上表 4 处改成显式 import（按各自文件 import 段的既有风格：`ui/hwcheck.js` 并入它那条
      多行 import 块；`ui/codeeditor.js` 的 `esc` 并入既有 fx import 段、`moveTab` 并入
      `fx/codeeditor.js` 那条）；**页面行为零变化**。
- [x] 新增守卫 `tests/js/window-bridge-guard.test.mjs`，**判据本体进 `tests/js/boot-contract.mjs`**
      （单源，照 `export-surface-guard` 的先例）：
      · 口径 = `static/js/{fx,ui}/**` 模块正文经 `maskNonCode` 掩码后，处于**调用位**
        （前面不是 `.`、不是属性名）的自由标识符，不得命中「window 桥发布的名字」；
      · 排除：本模块 import 的本地名（`locals`）、本模块自身的声明（function / const / let / var / class）、
        本模块自身的导出；
      · 桥的发布清单从源码现算（解析 `Object.assign(window, { … })` 的对象字面量键），**不写死名单**。
- [x] 守卫自带两条自检：① **正向对照**——注入一处"只靠桥解析"的调用，必须报出；
      ② **掩码自检**——名字只出现在注释/字符串里时**不算**依赖（照
      `export-surface-guard.test.mjs` 的"注释喂绿自检"先例）。另加一条**边界用例**
      （import 过的 / 本模块声明的 / 属性访问 / 方法定义 / 可选调用五形态）。
- [x] **反证**：撤掉 `ui/hwcheck.js` 那条新 import → 前端门禁红；复原后 sha256 逐字节相同
      （探针落 `.scratch/hwcheck-hygiene/probe-01-red.py`，读数 `probe-01-red.txt`）。
- [x] `tests/js/export-surface-guard.test.mjs` 文件头补一段（**只记账、不改口径**）：
      消费者集合**不许**排除 `tests/js`——实测消费者 169 → 排除后 11、零消费者导出 0 → 171
      （`fx/task.js` 18 / `fx/module.js` 16 / `fx/hwcheck.js` 15 …）；并写明"桥依赖归零之后，
      判据 D 的产品侧口径才真的成立"。
- [x] 读数：前端门禁 `node --test "tests/js/*.test.mjs"` 全绿（1807+）且**条数只增不减**；
      浏览器门禁 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` 全绿
      （本单动了 `ui/hwcheck.js` 与 `ui/codeeditor.js`，二者都在浏览器门禁的落点里）。
- [x] 顺手记一句：`fx/codeeditor.js` 的 `esc` 与 `moveTab` 现在各自多了一条 import 边，
      导出面判据 D 的消费者计数会变——**别把计数写进任何地方**（本条只是提醒评审时不误判）。

## 结论（读数与账）

**改了什么。** 4 处调用位改成显式 import（**改后行号**：`ui/hwcheck.js:194` 的 `hwcheckErrorHTML`
并入 `/js/fx/hwcheck.js` 那条多行 import 块；`ui/codeeditor.js:1693` 的 `esc` 新增一条
`/js/fx/core.js` 的 fx 段 import；`:2978`/`:2984` 的 `moveTab` 并入 `/js/fx/codeeditor.js` 那条
——工单「现状」表里的 `1691`/`2976`/`2982` 是**改动前**的行号，两行 import 插在上面之后各漂 +2）。
桥本身没动（spec「范围外」：桥不删），`fx/core.js` 与 `fx/codeeditor.js` 的桥条目原样保留。

**新守卫。** `tests/js/window-bridge-guard.test.mjs`（5 条用例：取数面体检 / 判据本体 /
正向对照 / 掩码自检 / 边界五形态），判据本体 = `tests/js/boot-contract.mjs` 的判据 ⑧
（`callPositionNames` + `windowBridgeNames` + `bridgeDependencyProblems`）。
调用位口径三条：前面不是 `[\w$.]`、后面是 `(` 或可选调用 `?.(`、**配对 `)` 之后不是 `{`**
（把方法定义与函数声明摘出去）。**判据面 = `fx/**` 与 `ui/**`**。

**实测更正一处（spec / 本工单里的 609 应读作 611）。** 立项探针
（`probe-bridge-callsites.mjs`）按**未掩码原文**逗号切分，被 `fx/task.js` 桥块里的行尾注释
（`:1244-1245` 的 `taskPhaseHTML,   // …`）吞掉两条 → 它报 **609**。守卫按**掩码**切分，现算
**611 个名字 / 66 个模块**（差的正是 `taskDetailsSnapshot` / `taskDetailsRestore`）。
对账量具与读数：`.scratch/hwcheck-hygiene/probe-01-bridge-count.mjs` / `.txt`。
（"66 个模块"两侧一致，那半不用改。）

**反证。** `probe-01-red.py`（字节读写 + 前置干净性检查）：撤掉 `ui/hwcheck.js` 那条 import →
前端门禁 **1812 tests / 1811 pass / 1 fail**，红的正是判据 ⑧ 且点名
`ui/hwcheck.js:194 用了 hwcheckErrorHTML`；复原后 sha256
`f737b6ab41ee0e0e4971b2a2b02a47127ae1983f51112b62434dcf2f49c13689` 逐字节相同，门禁回绿。

**读数（本机实跑，落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 前端门禁 | `node --test "tests/js/*.test.mjs"` | **1812 passed / 0 fail**（基线 1807，+5 即本单新守卫） | `probe-01-js.txt` |
| 浏览器门禁 | `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **44 passed / 0 fail**（≈150s） | `probe-01-browser.txt` |
| 反证 | `python .scratch/hwcheck-hygiene/probe-01-red.py` | 注入态 1812/1 红 → 复原态 1812 全绿，逐字节相同 | `probe-01-red.txt` |

读数落盘用本目录新增的 `readings.py`（`python .scratch/hwcheck-hygiene/readings.py <名> -- <命令>`）：
收全量输出 + 剥 ANSI + 写 UTF-8、带命令/时间/退出码头——PowerShell 的 `>` / `Tee-Object` 写
UTF-16LE（`read` 工具拒读）、`Select-Object -First N` 会掐断上游留下孤儿后端，这两条坑都绕开了。

**双轴评审（Standards / Spec，2026-09-26）与整改。** 两条硬违规、若干判断题，**全部已整改**：

| 评审发现 | 处置 |
|---|---|
| 硬：`boot-contract.mjs` 文件头仍写"七类不变量"、守卫清单没加新守卫 | 头改成"八类"、补 ⑧ 与 `window-bridge-guard`，并把本单写进"判据⑥/⑦ 由哪个工单加入"那一行 |
| 硬：`callPositionEdges` 处写着"调用位这件事只解析一处"，本单却另起一支 | ⑧ 段头新增一节写清**口径为何故意不同**（判据 T 的取数面是 import 边的本地名 + `maskCommentsAndStrings`；本条是整段正文的自由标识符 + `maskNonCode`——合并等于把其中一个改错） |
| 判：桥清单解析与立项探针两份实现、读数分叉（609 vs 611） | 见上「实测更正」；量具落盘，两处文件头都改用现算读数并写明探针低估的原因 |
| 判：`if (m.index < cursor) continue;` 自注"理论不可达"= 死分支 | 删掉（换行计数逻辑不受影响） |
| 判：断言文案与断言反向（模板串那句） | 文案改成"**算**代码（maskNonCode 口径）"，并补一条属性访问的负向断言 |
| 判：掩码自检只断言注释那一侧、字符串那半落空也绿 | 两侧注入各补一条断言 |
| Spec：调用位漏 `probeC?.();` 这一形态 | 正则加 `(?:\?\.)?`，边界用例补 `probeD?.();` |
| Spec：`probe-01-browser.txt` 无命令/时间/退出码头 | 改用 `readings.py` 重跑落盘（头部五行齐全） |
| Spec：已知边界少记一条（`window.X =` 形态） | ⑧ 段头「已知边界」补三条：`window.X =` 不在桥清单（`ui/settings.js` 的 `__priceRef` 目前是同模块自写自读、非桥依赖）、再导出名按"本模块导出"排除、参数遮蔽同名 |

**留给下一个人的一句**：本单**没有**改判据 D 的消费者集合口径（`tests/js` 那些 import 边照旧算消费者），
只在 `export-surface-guard.test.mjs` 文件头记了账——**别把"消费者数""零消费者数"抄进任何判据**，
它们是随提交变动的读数（`probe-dead-exports.txt` 是立项那一刻的）。
