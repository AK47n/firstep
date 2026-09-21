# 01 — 判据单源落地 + 红证先行（喂「收走前那个提交」证明它会红）

**要做什么：** 把这次要钉的四类不变量写成**零依赖纯函数**（共享件，红证与守卫共用同一份），
并用**收走前那个提交**的源码证明它们真的会红——先有能红的判据，才有资格动 index.html。
本工单不改产品代码：前端门禁与浏览器门禁保持全绿。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

## 判据（本次四类，全部作用在"源码文本 + 模块表"上）

| # | 不变量 | 形态 |
|---|---|---|
| ① | **index.html 零 import**（装载根不在 HTML 里） | 数 index.html 内联脚本里的 import 语句条数 |
| ② | **index.html 零 JS 定义**（列 0 的 `function`/`const`/`let`/`var`；含 `export` 前缀写法） | 逐行列 0 匹配 |
| ③ | **接线不在求值期**：③-a 装载清单**零裸装载** ＋ ③-b `boot` 唯一装载来源的 ui 模块列 0 副作用为 0（监听器绑定 / 首帧 DOM 写 / window 桥安装；探针桥形态 `if (typeof window …)` 单列不算） | 模块文本 → 副作用语句清单 |
| ④ | **装载图完整**：每个 fx/ui 模块从装载根可达 ＋ 每条具名 import 都是目标模块真导出的名字（全图对账，注释感知） | 广度优先 + 导出名集合对账 |

> ③ 的适用面为什么不是"11 个模块"：本轮要改的 11 个里，只有 7 个是"boot 唯一装载来源"
> （`generate-revise` / `generate-tasks` / `params` / `delivery` 另有别的 ui 模块 import 它们），
> 剩下 4 个由 ③-a"零裸装载"覆盖。两条合起来正好是 11 个模块的完整判据面。

## 验收标准

- [x] `tests/js/boot-contract.mjs` 落地：上表四类判据的纯函数实现（零依赖、无 npm、
      **不注册 `node:test` 用例**——它是共享件，进闸门不会自己变红；先例
      `tests/js/import-usage.mjs` / `tests/js/ui-dom-contract.mjs`）
- [x] `.scratch/frontend-boot-module/probe-01-red-proof.mjs` 落地，喂 `git show <base>:<path>`
      的源码（只读，不碰工作区），四段读数：
      1. **base 自校验**：base 的 `index.html` 必须**有** 45 条 import、且**没有** `boot.js`、
         且 11 个目标模块各自有求值期接线——不满足就大声失败（选错 base = 假绿，2026-09-20 刚踩过）
      2. **判据作用在 base 上：必红**（① 45 条；③-a 5 条裸装载；③-b 7 个模块 / 49 条列 0 副作用）
      3. **判据强度自检（内存注入，不写盘）**：删一条装载 → 可达性红；摘一个导出 →
         全图对账红；往 index.html 塞一个 `function` → 零定义红；装载指向不存在的模块 →
         对账红；`import` 了 init 却不调用 → 调用点判据红（补上调用即转绿）；
         花括号里的注释不被当导入名
      4. **当前工作树读数**（打印，不作本工单退出条件；收口工单 05 要求它绿）
- [x] base 显式钉住：缺省 `b52022f1`（收走前那个提交），**不写 HEAD**；`--base <rev>` 可覆盖
- [x] 红证原始输出落档：`.scratch/frontend-boot-module/red-proof.txt`（真跑一次，退出码 0）
- [x] base 选错时必须失败：喂一个"已经有 boot.js"或"index.html 已零 import"的 rev →
      自校验拦下并返回非 0（当场实测一次，读数记进 Comments）
- [x] `node --test "tests/js/*.test.mjs"` 全绿（新增共享件不该改变任何既有用例的红绿）

## Comments

### 2026-09-21 实现记录

**红证读数**（`.scratch/frontend-boot-module/red-proof.txt`，退出码 0）：

| 段 | 读数 |
|---|---|
| ① base 自校验 | base `b52022f1`：宿主脚本 **45 条 import**、`boot.js` 不存在、131 个 .js 模块 → 通过 |
| ② base 上必红 | ① 45 条；③-a 裸装载 **5 条**（revise / tasks / params / params-chat / delivery）；③-b **7 个模块 / 49 条**列 0 副作用 |
| ③ 当前工作树 | 判据① 45 条红 / ② 0 条绿 / ④-a 0 处绿 / ④-b 131-131 绿（③ 待 02–04 落地） |
| ④ 强度自检 | **6/6 成立** |
| 结论 | `PASS（判据能红，且不是靠选错 base 红的）` |

**base 选错实测**（验收标准最后一条）：喂 `595d96d8`（本仓第一次提交 index.html 的那一代）
→ 自校验拦下、**退出码 2**，指名两条：`宿主脚本只有 0 条 import` +
`11 个模块没有求值期接线`。红证的"静默变绿"这条路被堵死了。

**判据实现踩到的两个坑**（都写进 `boot-contract.mjs` 的注释里了）：

1. **掩码必须按 UTF-16 码元切**：`Array.from(text)` 按码点切，而扫描下标是 UTF-16 单位——
   中文注释里的 `✎/🗑` 之后整体错位一格，注释行的首个 `/` 掩不掉，于是"列 0 副作用"里
   冒出 30+ 条 `"/"`、`"//"` 假阳性。
2. **正则字面量必须单独识别**：本仓库是代码编辑器前端，`/["'`]/`、/```/g` 这类正则遍地，
   把 `/` 一律当除号会让正则里的引号/反引号开启"字符串状态"、一路把几十行代码掩成空白——
   实测 `fx/markdown.js` 的 `export function parseMarkdownBlocks` 被掩掉，静态对账于是
   误报"未导出"（3 处假断裂）。按"前一个有意义字符/关键字"判 `/` 是不是正则起始后，
   全图对账 0 处断裂。

**门禁**：`node --test "tests/js/*.test.mjs"` → **1715 passed / 0 fail**（共享件不注册用例，
既有红绿一个没动）。

### 2026-09-21 双轴评审整改（规范轴 7 条）

评审固定点 `b52022f1`，实跑复现了红证 `PASS` 与门禁 `1715/0`。整改：

- **（规范轴 1，硬违规）探针重抄 `hostScript`**：删掉本地副本，改 import
  `tests/js/import-usage.mjs` 的单源（先例 `.scratch/frontend-import-fossils/guard-red-proof.mjs`
  正是这么做的）。
- **（规范轴 2，硬违规）文档与实现自相矛盾**：`parseModuleExports` 里 `export {…}` 那一段
  扫的是**未掩码**文本（手工去注释），而同函数其余模式扫掩码文本。现在四条模式统一扫掩码
  文本，文件头"注释与字符串必须掩掉"这句才成立。
- **（规范轴 3，最重）判据解析抄成四份且已分叉**：`check-graph.mjs` 那份是"注释盲"解析器，
  它给出 `survey-04-graph.txt` 的「2 处断裂」是**假读数**（真值 0），而 spec 把它当出处引用。
  已把 `survey.mjs` / `survey2.mjs` / `check-graph.mjs` 全部改成 import 判据单源，
  三份读数**重跑重录**（现在 `survey-04-graph.txt` = 0 处断裂、131/131 可达）；
  同一处把 `resolveSpec` 改名 `resolveModuleKey` 并写明键空间差异（`ui/x.js` vs
  `ui-dom-contract` 的 `js/ui/x.js`）——同名不同键空间是下一处漂移的温床。
- **（规范轴 4）探针拿哨兵值凑读数**：装载根还不存在时（工单 02 之前）曾用
  `effects:[{}]` / `line:0` 伪造，读数于是打出"③-a 1 条（红）"这种**编造数字**。
  现在如实打印「（无装载根：判据 ③/④ 无适用面）」，并把这两行补进本工单 Comments 的读数表。
- **（规范轴 5）文档点名不存在的导出**：文件头写 `unreachable(...)`，实际导出 `reachable` ——
  已改。
- **（规范轴 6）Divergent Change / Speculative Generality**：单文件 502 行含词法器 / HTML
  抽块 / ESM 解析 / 图算法 / 读盘五件事，7 个导出当前零消费方。**判断：保留单文件、导出留到
  02/05 消化**——理由是 workflow.md「缝越少越好」：这些函数同属"装载根契约"这一个域，
  拆成两三个文件等于为同一域开多条缝；而 02/05 的守卫与夹具会消费
  `readLoadRoot` / `listJsFiles` / `loadRootTag` / `bareLoads` / `wiringViolations` /
  `reachable` / `graphBreaks` / `indexHtmlImports` / `inlineDefinitions`。
  **收口时（工单 05）复核一遍：仍无消费方的导出删掉**。
- **（规范轴 7）死分支**：`CONTINUATION_RE` 里 `|^\.` 被同一字符类 `^[.)\]},?:]` 覆盖 —— 已删。

### 2026-09-21 工具事故记账（PowerShell 改文本文件）

整改过程中用 `(Get-Content -Raw) -replace … | Set-Content` 改 `tests/js/boot-contract.mjs`，
把文件改坏了：本机 `pwsh` 的 `Get-Content` 按 **GBK** 解码了 UTF-8 源码（→ 中文整片乱码），
`Set-Content -Encoding utf8` 又写上 **BOM**；更糟的是 GBK 双字节硬配对**吞掉了行尾换行符**
（CLAUDE.md 里记着的那条机制，这次咬在 `.js` 上）。已用文件工具整份重写并复核：
首字节 `47 47 32`（无 BOM）、506 行、中文正常、门禁 1715/0。

**纪律**：本仓文本文件（含 `.js` / `.md`）一律用文件工具改，**不要用 PowerShell 的
`Get-Content`/`Set-Content` 往返**——那条路只对纯 ASCII 成立。

### 2026-09-21 双轴评审整改（Spec 轴 4 条）

- **（spec 轴 a1，最该修）判据 ③ 对 4 个裸装载模块没有适用面**：评审实测——把这 4 个
  （generate-revise / generate-tasks / params / delivery）改成具名导入后，③-a 与 ③-b
  双报 0，而它们求值期仍有 47 条接线；**收口时会把"接线没搬"判成绿**。根因：它们另有
  别的 ui 模块 import，"boot 是唯一装载来源"这条结构判据抓不到。
  修法：判据 ③ 明确分成两半——**结构那一半**（boot 唯一装载来源，零名单）＋
  **登记那一半**（`EXPLICIT_WIRING_MODULES`，11 项 = spec 的 B 档交付面）。
  登记表**自带体检** `registryProblems`（键必须存在 / 是 ui/ / 被 boot 装载 / boot 真的
  调用了它导出的某个 `init*`），所以表不会静默腐烂：谁把接线搬出去却忘了登记、或登记了
  却没接线，守卫当场指出来。新增强度自检 ⑦ 专门证明这一半在兜底：**结构判据漏掉 4 个，
  登记判据把 4 个全判红**（7/7 成立）。
  读数随之更正：base 上 ③-b 从「7 个模块 / 49 条」变成 **「11 个模块 / 96 条」**——正是
  spec 表里那 11 个与 96 条（此前的 7/49 是适用面写窄了的产物）。
- **（spec 轴 a2）base 自校验没按 spec 写死 45 条**：原实现是 `< 40`，`--base 810a959a`
  （44 条）能溜过去。改成 **必须恰好 45 条**，选错就大声失败。
- **（spec 轴 b）判据是"超集"**：`inlineDefinitions` 多认 `class`、`indexHtmlImports` 多认
  `export … from` 与动态 `import(`。**保留**（判断：都是"装载根住在 HTML 里"的合法形态，
  多认只会更严、不会放水），并在文件头写明。4 个普查脚本不在工单交付清单，但 spec
  「补充说明」引用它们当读数出处 —— 保留。
- **（spec 轴 c3）证据文件是 UTF-16LE**：本机 PowerShell 的 `> x.txt` 重定向写 UTF-16LE
  （本仓 `tests/js/windows-text-encoding.test.mjs` 明文记过这个坑，只因 `.scratch/` 不在它的
  ROOTS 才没红）。修法：新增 `tee.mjs`，脚本自己用 `fs` 落 **UTF-8**（`--out` 指定路径），
  八份证据全部重跑重录；实测首字节已非 `FF FE`。
- **（spec 轴 c4）评审期间现场在动**（BOM 版 → 无 BOM 版 → `boot.js` 出现 → 门禁 fail 10）：
  属实，那是工单 02 的搬家正在同一棵树上做（旧守卫还指着 index.html 里的宿主块，正是 02
  要重定根的那批）。评审的两轴读数按时间戳归属，无异议。

**整改后复跑**：红证 `PASS`（base 红 / 强度自检 **7/7** / 工作树读数如工单 02 之后的状态），
`red-proof.txt` 已是 UTF-8。
