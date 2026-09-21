# spec — 把前端接线搬出 HTML（frontend-boot-module）

## 问题陈述

前端整张模块图的**唯一装载点写在 HTML 里**：`index.html` 末尾一个手写的
`<script type="module">`（实测 476 行 / 36 KB / 45 条 import / 78 个具名 / 5 条裸装载 /
43 条列 0 语句 + 60 行启动调用）。三笔代价都是真的：

1. **HTML 成了模块图的一部分**：清单里提到一个不存在的导出，浏览器解析 import 就抛
   `SyntaxError`，整页脚本全灭——服务端 `/api/*` 与静态资源全 200，看起来像"卡住了"，
   强刷也没用（2026-09-12 真机现场）。
2. **为防它养了一张手抄表**：`static-import-guard` 与 `fx-guard` 两条守卫 + 337 行
   `DOMAINS` 名字登记表——而"某个导出存不存在"这件事被写在**三处**（模块 / 登记表 /
   HTML 清单），错一处就整页死；新增模块还得记得登记。
3. **一批 ui 模块靠"被 index.html 加载"才接线**：它出现在清单里是因为**求值期绑了监听器 /
   写了首帧 DOM**，页面行为藏在那条 import 的副作用里。读 HTML 只知道模块被拉进来了，
   不知道它干了什么、什么时候干的；删掉一行 import，页面不报错，功能静默消失。

## 方案

把装载与接线搬进 module graph，让 HTML 只剩一条装载标签：

- **装载根 = `static/js/boot.js`**：index.html 末尾只留一条
  `<script type="module" src="/js/boot.js"></script>`；import 清单（**逐字保序**）、
  接线调用、跨簇接缝注册、启动 IIFE 全部住 boot.js。分层照 `js/app.js` 的先例：
  boot 可以 import ui/app，**不许被任何 ui/app 模块 import**（否则成环）。
- **11 个"靠被装载才生效"的 ui 模块给出显式 `init()`**（实测口径见"实现决策"）：
  裸装载的 5 个 ＋ boot 是它唯一装载来源且求值期有接线的 6 个。boot 按 import 顺序显式
  调用它们——**"import 即接线"这条隐式边退场**，页面装了什么读 boot.js 的接线区就知道。
- **两张登记表退化成结构不变量**：`index.html` 零 import、零 JS 定义；每个 fx/ui 模块
  从 boot 可达；再补一条**全图 import↔export 对账**（每条具名 import 都必须是目标模块
  真导出的名字）——它是 2026-09-12 那类失败模式在 graph 上的通用形态，不需要任何名字表。
- **行为零变化**：markup 与 CSS（3,100 行 / 555 个 id）一个字节不动，只动
  `<script type="module">` 那一块；迁移墓碑注释随块搬进 boot.js，逐字保留。

## 用户故事

1. 作为维护者，我想在改一个 fx/ui 导出名时只改"模块 + 它的 importer"两处，以便不再因为
   忘了同步 HTML 把整页搞死。
2. 作为维护者，我想让 `index.html` 只剩一条装载标签，以便 HTML 与 JS 各管各的、
   改 HTML 不会伤到模块图。
3. 作为维护者，我想让"这个 ui 模块靠被加载才接线"从隐式副作用变成 boot.js 里一行显式
   调用，以便读一个文件就知道页面装了什么、按什么顺序装的。
4. 作为维护者，我想让 337 行手工登记表退化成结构不变量（零 import / 零定义 / 从装载根
   可达 / 全图对账），以便新增模块不必再登记、忘了登记也不会静默漏保护。
5. 作为探针与浏览器用例的作者，我想让 fx 模块底部的 window 探针桥、以及**加载期监听器
   集合**一字不变，以便既有证据与新证据可比。
6. 作为用户，我想让页面照旧打开就能用（0 pageerror、0 模块图链接错误、四个 spec 26 条
   用例全绿），以便感觉不到这次改动发生过。

## 实现决策

**落点与分层**

- 新增装载根 `static/js/boot.js`；`index.html` 的 `<script type="module">` 块整块搬走，
  原处替换成一条带 `src` 的装载标签。head 里那条主题防闪烁 `<script>`（非 module、
  无 import、无定义）不属本次范围。
- boot.js 结构：文件头（分层规则 + 为什么在这里）→ import 清单（原样保序）→ **接线区**
  （显式 `init*()` 调用，按 import 顺序）→ 原宿主正文（页签分发器 / 跨簇接缝注册 / 启动
  IIFE / 墓碑注释）。
- 禁环：boot 不在任何 ui/app 模块的 import 图上（由结构守卫判：ui/app 不得 import boot）。

**保序（ESM 求值顺序 = import 书写顺序）**

- 清单逐字保序，不排序、不分组、不合并同类项。
- 今天所有 ui 模块的顶层接线发生在**各自的求值期**（即 import 顺序），且早于宿主正文；
  搬运后，接线区位于 boot 正文最前、按同一顺序调用 → 接线之间的相对顺序不变。
  scoped 模块与"求值期仍接线"的模块之间的边界顺序会有位移，**用加载期监听器记账证明
  集合与 target 逐条相同**（改前 / 改后同一支冒烟，照
  `.scratch/frontend-import-fossils/smoke-page.mjs` 的做法）。

**显式 init() 的范围（实测，B 档）**

| 档 | 模块 | 判据 |
|---|---|---|
| 裸装载 5 | generate-revise / generate-tasks / params / params-chat / delivery | boot 零具名导入，存在意义就是"被加载即接线" |
| 唯一装载来源 6 | generate-core / library / master / reference / topic / code-fix-panel | boot 是它唯一的装载来源（别的模块都不 import 它）且求值期有接线副作用 |

- 只搬**列 0 的非声明语句**（监听器绑定 / 首帧 DOM 写 / window 桥安装）；模块作用域里
  被其它函数读的 `const/let`（如 `distPanel` / `topicPageCache`）留在原地。
- `fx/*.js` 底部的 window 探针桥**一个都不动**（CDP 探针靠它）。
- `ui/delivery.js` 的 `Object.assign(window, {...})` 是既有事实（与 app.js 规则 3 相抵，
  另立）：本轮随接线一起进 init，语义不变（仍在上线前装好、探针按全局名取用照旧）。
- 不做的 9 个模块（settings / generate-recommend / generate-pins / generate-steps /
  generate-fix / step-state / codeview / generate-mainc / usage）顶层接线保持现状——它们
  另有模块 import，"被加载即接线"不是它们唯一的生效路径；本轮记账另立。

**判据单源**

- 新增零依赖共享件 `tests/js/boot-contract.mjs`（照 `import-usage.mjs` /
  `ui-dom-contract.mjs` 先例，放共享件而非 `.test.mjs`，红证脚本也 import 它）：
  读装载根、inline JS 定义集合、**列 0 副作用语句**、**全图 import↔export 对账**、
  **从装载根可达**。判据全部是纯函数，作用在"源码文本 + 模块表"上。
- `unusedImports`（`import-usage.mjs`）与装载图的取数面从 index.html 换到 boot.js。

**守卫退化（验收物，不是可选项）**

| 守卫 | 现在 | 退化成 |
|---|---|---|
| `fx-guard.test.mjs` | 337 行 `DOMAINS` 名字表 + 逐名 `index.html` 定义正则 | **删表**：`index.html` 零 JS 定义（`function`/`const`/`let`/`var`）+ 每个 fx/ui 模块从 boot 可达 |
| `static-import-guard.test.mjs` | 抽 index.html 的 import ↔ 模块导出对账 | **index.html 零 import** + 装载根存在且带清单 + **全图 import↔export 对账**（注释感知的解析器） |
| `import-usage-guard.test.mjs` | 根 = index.html 宿主块 | 根 = boot.js；零未使用具名 ＋ **零裸装载**（裸装载是本次要退场的那条边） |
| `ui-dom-contract`（静态层） | 装载图根 = index.html 宿主块 | 根 = boot.js（"孤立模块"/"init 没人调"两条判据不变） |

**闸门落点跟随**

- 浏览器门禁的落点清单（`tools/prepush.py`）加 `static/js/boot.js`：装载清单搬家了，
  落点不跟随就是"改了装载清单不跑浏览器门禁"；`tests/test_prepush.py` 同步加一条落点用例。

## 测试决策

- **先红证后动手**（先例 `.scratch/release-channel-dedupe/probe-01-pin-red-proof.py`）：
  判据写成纯函数，喂**收走前那个提交**（base 显式钉 `b52022f1`，**不写 HEAD**）的源码证明
  它能红；base 自校验 = "base 的 index.html 有 45 条 import 且没有 boot.js"，选错当场
  大声失败、绝不产出假绿。
- 红证内容：① 零 import 判据在 base 上红（45 条）；② 接线不变量在 base 上红（11 个模块
  的列 0 副作用）；③ 同一套判据作用在当前工作树上绿；④ **判据强度自检**（内存注入）：
  删一条装载 → 可达性红；改一个导出名 → 全图对账红；往 index.html 塞一个 `function` →
  零定义红；把某个 init 调用删掉 → "init 没人调"红。
- 前端门禁 `node --test "tests/js/*.test.mjs"` 全绿（含改写的四条守卫）。
- 浏览器门禁四个 spec / 26 条用例全绿（`tests/browser/`）。
- 真浏览器冒烟（改前 / 改后各跑一次，复用 fossils 的加载期监听器记账做法）：
  0 pageerror / 0 模块图链接错误；监听器记账**逐条相同**；fx 探针桥仍在；
  delivery 的 window 桥仍在、`#delivery-actions` 仍被写。
- 收尾各跑一遍：`python -m pytest -n auto -q` ＋ 前端门禁 ＋ 浏览器门禁。

## 范围外

- **C6**：`index.html` 与 ui 的 555 个 id 耦合改造（本轮只把它保持成可测事实）。
- **C7**：73 个私有符号公开化。
- **删迁移墓碑注释**（随块搬进 boot.js，逐字保留）。
- 被别的模块 import 的那 9 个模块的顶层接线（见"实现决策"表下）。
- `ui/delivery.js` 的 window 挂桥与 `app.js` 规则 3 相抵这条既有事实。
- 产品侧「F5 重载慢过 1.5 秒被判空闲退出」的竞态。
- 不被 boot 装载的模块（`ui/context-menu.js` 等）的顶层接线。

## 补充说明

- 本 spec 的每个数字都有出处，原始读数在 `.scratch/frontend-boot-module/`：
  `survey-01-landing.txt`（清单逐条）、`survey-02-toplevel.txt`（顶层副作用逐条）、
  `survey-03-block.txt`（宿主块构成）、`survey-04-graph.txt`（全图对账 + 可达性基线，
  现状 131/131 全可达）。
- 命名纪律：「装载清单」特指 boot.js 里那张 import 表；「登记表」特指 fx-guard 被删掉的
  `DOMAINS`；「装载根」= boot.js。
- 现场基线（收走前的提交）：`b52022f1`。
