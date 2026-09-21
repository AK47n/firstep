# 02 — 装载根搬家：index.html 只留一条标签，清单与启动住 boot.js

**要做什么：** 页面打开后行为一字不变，但 `<script type="module">` 那一块（45 条 import +
78 个具名 + 5 条裸装载 + 页签分发器 + 跨簇接缝注册 + 启动 + 墓碑注释）整块搬进
`static/js/boot.js`；index.html 原处只剩一条装载标签。**装载根搬家了，靠装载根取数的
守卫与夹具同批重定根**——否则闸门要么红、要么静默失去一只眼睛。

**被谁阻塞：** 01（判据与红证先行）

**状态：** resolved

## 验收标准

- [x] `index.html` 里 `<script type="module">…</script>` 整块消失，原处只有
      `<script type="module" src="/js/boot.js"></script>`；head 那条主题防闪烁 `<script>`、
      CSS、markup 一个字节不动（555 个 id 不变）
- [x] **机械判定"这是纯搬运"**：`git show b52022f1:src/contest_generator/static/index.html`
      的块内容（去掉 `<script …>` / `</script>` 两行）与 `boot.js` 去掉新增文件头后
      **逐字相同**；`git diff -U0` 对 index.html 的增删只有标签那一处
- [x] import 清单 **45 条逐字保序**（不排序 / 不分组 / 不合并不删；含 5 条裸装载与全部注释）
- [x] `boot.js` 文件头写清分层规则：boot 可 import ui/app，**不许被任何 ui/app 模块 import**
- [x] 墓碑注释随块搬进 `boot.js` 且逐字保留（数量与文本不变）
- [x] **重定根（装载根取数面从 index.html 换成 boot.js）**，逐处改到位：
      - `tests/js/static-import-guard.test.mjs`：新增"index.html 零 import"不变量；
        清单↔导出对账指向 `boot.js`（等价强度，先原样搬家）
      - `tests/js/import-usage-guard.test.mjs`：根 = `boot.js`（"零未使用具名"照旧绿）
      - `tests/js/ui-dom-contract.mjs` + `.test.mjs`：装载图根 = `boot.js`
        （"孤立模块"/"init 没人调"两条判据不变）
      - `tests/js/tab-nav-guard.test.mjs`（页签分发器搬到 boot.js）、
        `tests/js/glossary-refs.test.mjs`、`tests/js/handoff-note-guard.test.mjs`、
        `tests/js/hwcheck.test.mjs`（"成对接入"断言指向 boot.js）
      - `tests/browser/ui-contract-fixture.mjs` 的 `staticAnchor`（index.html ∪ boot.js）
- [x] 闸门落点跟随：`tools/prepush.py` 的浏览器门禁落点加 `static/js/boot.js`；
      `tests/test_prepush.py` 落点用例补一行（改了装载清单必须跑真浏览器）
- [x] `node --test "tests/js/*.test.mjs"` 全绿
- [x] 浏览器门禁 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` 26 条全绿
- [x] 真浏览器冒烟：0 个 pageerror / 模块图链接错误；**加载期监听器记账与 base 逐条相同**
      （复用 `.scratch/frontend-import-fossils/smoke-page.mjs` 的做法，改前读数先落档）；
      fx 探针桥仍在；`#delivery-actions` 仍被写
- [x] `python -m pytest -n auto -q` 全绿

## Comments

### 2026-09-21 实现记录

**搬运是机械的、可复算的**：`.scratch/frontend-boot-module/apply-move.mjs --write`
（自校验不过就拒绝写盘）＋ `verify-move.mjs`（独立复算）→ **7/7 条成立**：

| 判据 | 读数 |
|---|---|
| ① boot.js 去掉文件头 = 收走前搬走的块内容（逐字，行尾归一后） | 476 行对 476 行 |
| ② index.html 零 import | 0 条（原先 45 条） |
| ③ 装载标签唯一且 src=/js/boot.js | count=1 |
| ④ index.html 除块之外逐字节未动 | 一致（markup / CSS / 墓碑注释都在） |
| ⑤ 装载清单 45 条且逐字保序 | 45 → 45 |
| ⑥ index.html 的 `id="…"` 声明数不变 | **555 → 555** |
| ⑦ index.html 行数 | 5143 → 4668（−475 = 搬走的块 + 两条标签） |

`git diff --stat`：`index.html | 477 +-`（**1 insertion / 476 deletions**，增删全在那一块）。

**行尾**：index.html 是 CRLF、`static/js/` 下既有 JS 全是 LF —— 搬进 boot.js 时按 LF 归一
（搬运内容本身逐字相同，只是行尾随目标文件族）。boot.js 无 BOM（首字节 `47 47 32`）。

**真浏览器冒烟（改前 / 改后同一支，`.scratch/frontend-boot-module/smoke-page.mjs`）**：
改前落 `smoke-before.txt`（临时 `git checkout -- index.html` + 删 boot.js 后跑），改后落
`smoke-after.txt`，两份**逐行相同**（除末行证据文件名）——

- **加载期监听器记账 592 条，原序逐条相同**（不是"集合相同"：顺序也一字不差），排序后指纹
  `2749610313` 两份相等；
- 0 个 pageerror / 0 个模块图链接错误；fx 探针桥 6 个全在；5 个"靠被加载才接线"的模块绑定全在；
  `#delivery-actions` 加载即被写（245 字符）；`#btn-params-chat` 真点击有行为反应；
  平台卡 2 / 步骤导航 13 / 总览 2318 字符 / 词表 1894 字符 / 检测卡 2 —— 全部一致；
- HTTP 400 两条（`POST /api/generate/preview-dir`、`GET /api/code/file`）改前改后都有，
  是既有的"本机未配 AI key"基线（记账不判红）。

**重定根（装载根取数面搬家）**：`static-import-guard`（新增"index.html 零 import"＋装载标签
不变量）、`import-usage-guard`（根 = boot.js）、`ui-dom-contract.test.mjs`（装载图根 = boot.js）、
`tab-nav-guard` / `glossary-refs` / `handoff-note-guard` / `hwcheck`（成对接入指向 boot.js）、
`master-render` / `recommend` / `generate-overwrite`（"宿主不得内联定义"改成 index.html ∪ boot.js
两处都判）、`tests/browser/ui-contract-fixture.mjs` 的 `staticAnchor`；
闸门落点：`tools/prepush.py` 的浏览器门禁落点加 `static/js/boot.js` + `tests/test_prepush.py`
落点用例补一行。

**门禁**：前端门禁 **1716 passed / 0 fail**（比基线 1715 多的一条 = `static-import-guard` 拆出的
"index.html 零 import"不变量）；浏览器门禁 **26 passed / 0 fail**；
`python -m pytest -n auto -q` → **5049 passed + 1 skipped / 0 fail（171.96s）**。

### 2026-09-21 双轴评审整改（规范轴 8 条 + spec 轴 5 条）

两轴都实跑复核了自报读数（`verify-move` 7/7、前端门禁 1716/0、红证 exit 0、
`prepush --changed …/boot.js --dry-run` 确实带起浏览器门禁），并独立复算了关键证据
（`git show b52022f1` 的块正文 vs boot.js 去文件头**逐字节相同**、`numstat` = 1 增 476 删、
id 555→555；两份冒烟记账仅末行文件名与端口行不同）。整改如下：

**规范轴（硬违规 2）**

- **单源文件的自述取数面没跟着搬家**：`import-usage.mjs` 头还写"正文 = `<script type="module">`
  宿主脚本块"、`ui-dom-contract.mjs` 还写"从 index.html 的宿主脚本出发"，而调用方已改喂
  boot.js。两处文件头已按新取数面改写（并写明 `hostScript()` 现在的用途 = **读旧版源码**）。
- **CONTEXT.md 两处架构事实被本次改动作废**：`ui 层测试缝` 行的"每个 ui 模块必须从 index.html
  沿 import 图到得了"、`架构要点` 里"index.html 模块区仅剩 fx/app/ui imports + 页签分发器 +
  启动 IIFE"——两处都已改成"装载根 = static/js/boot.js"的口径（03-05 的措辞标了"落地中"，
  收口工单 05 定稿）。

**规范轴（判断题 6）**

- **duplicated code（3 份解析器）——本工单**自己**引入了第三份**（`parseModuleImports`），被两轴
  同时点名。已收敛成**一份**：`tests/js/boot-contract.mjs` 是唯一实现（注释感知 + 带 `names`
  源名 / `locals` 本地名 / `raw` 语句切片），`ui-dom-contract.mjs` 的 `importEdges` 与
  `import-usage.mjs` 的 `parseImports` 降为**薄适配器**（旧 import 路径与返回形状保持兼容），
  `listJs` / `ownInitExports` / `hasCallSite` 也搬进 boot-contract 并由 ui-dom-contract 转发
  （原先 `listJsFiles` 与 `listJs` 逐字节相同的两份实现一并消失）。
  **依赖方向单向**：boot-contract 是叶子，ui-dom-contract / import-usage 依赖它。
- **`readLoadRoot` 复用面窄**（7 个测试文件各自 `readFileSync(boot.js)`）：**不改**——那些是
  "读一个文件"的普通取件，而 `readLoadRoot` 是"装载根在哪"的语义取件（守卫与探针用它）；
  为一处 3 行的读盘再套一层反而增加耦合。
- **死分支**：`ui-contract-fixture.staticAnchor` 的第三子句 `hostScript(html)` 恒为空串
  （index.html 已无该字面标签）——已删，文件头"等启动完成"的说明也改成装载根口径。
- **Speculative Generality**（判据 ②③④ 目前只被 `.scratch` 探针消费）：属实，但那是
  **计划内**——03/04 落地接线、05 把判据接进闸门（见 05 工单验收标准）。
- **`boot.js` 的 `"use strict";`**：ESM 恒严格模式下冗余，且按本次"列 0 副作用"的口径会被算成
  一条副作用语句。**本工单不动**（那是逐字搬运的一部分，动了 ①号机械判定就不成立）；
  工单 03 改装载清单时顺手删掉并记账。

**spec 轴（5 条）**

- **（最严重）`tab-nav-guard` 重定根时把 `const html` 直接换成 `const boot`，丢了 index.html
  一侧的断言**——它守护的原事故（裸 `querySelectorAll("nav button")` 把 step-nav 绑进页签 →
  整页黑屏）若写回 HTML 就没人看得见。已改成**两个宿主都判**：裸选择器 index.html ∪ boot.js
  都不许有，`[data-tab]` 限定选择器仍钉在 boot.js（分发器的实际落点）。
- **`fx-guard` 未随根搬家**（仍只扫 index.html 查"双源回退"）：按 spec 的守卫退化表归工单 05，
  属过渡；**已把这一点写进 05 的验收标准**（退化后的不变量要覆盖 boot.js：装载根零 `function`
  定义）。
- **scope creep**：`master-render` / `recommend` / `generate-overwrite` 改成 index.html ∪ boot.js
  双判——工单没要求，但判据面向"宿主不得内联定义"，宿主确实含 boot.js，属防漏加固，保留。
- **证据口径**：工单写"记账 592 条"= **监听器条数**（文件里另有判据行，故非空行更多），
  已核实两口径不矛盾。
- **`verify-move` 的 ⑦（行数算术）偏弱**：接受（它只是旁证；①④⑥ 才是硬判据——① 直接从
  `git show` 重算、不读 `apply-move` 的产物）。
- 评审另外指出 `verify-move.mjs` 是**工单 02 时点**的证据脚本：03/04 会改 boot.js 的装载清单，
  它到那时不再成立（保留为"搬家那次"的复算凭据）。
