# 02 — ui 层第一层缝：id 存在性 + 装载可达性（纯静态，进前端门禁）

**要做什么：** 给 `ui/` 层立起第一条**可测的 interface**：任何一个 `ui/*.js` 里写死的 id，都必须在
「页面真正会出现的声明集合」里找得到；任何一个 `ui/*.js` 模块，都必须真的被页面装载。
端到端行为：把 `$("output-dir")` 写成 `$("outpt-dir")`、或新加一个 `ui/` 模块而忘了在
`index.html` 里 import/调用，`node --test "tests/js/*.test.mjs"` 当场变红并点名文件与 id。

**被谁阻塞：** 无——可立即开始（与 01 互不阻塞）。

**状态：** resolved

- [x] 判据落点 `tests/js/ui-dom-contract.mjs`（判据单源，可复用），断言落点
      `tests/js/ui-dom-contract.test.mjs`。
- [x] **id 存在性**：静态 id 字面量（`$("x")` / `getElementById("x")` / `querySelector("#x…")`）
      对账声明集合（`id="…"` / `.id = "…"` / `id: "…"`，index.html ∪ js/**）；游离即红并点名
      **id + 引用文件:行号**。实测基线：声明 592 / ui 引用 510 / **差集 0**。
- [x] **装载可达性**：从 index.html 宿主脚本沿 import 图（含 ui→ui 边）判可达；
      「import 了某个 `init*` 却找不到调用点」= 红并点名。
- [x] **红证 4 条 + 反证 2 条**（`probe-guard-strength.mjs`，判据纯函数、注入加在内存副本上，
      不动仓库文件）：见下。
- [x] 零新依赖（只吃 `node:` 内置模块）；命令仍是 `node --test "tests/js/*.test.mjs"`。
- [x] 判据不绑写法（改名/两步取元素/可选链都算通过）。
- [x] `node --test "tests/js/*.test.mjs"` **1715 passed / 0 fail**；提交信息中文。

## Comments

### 一、两条判据与实测基线

| 判据 | 判什么 | 当前读数 |
|---|---|---|
| ① id 存在性 | ui 里写死的 id 必须在"页面真会出现的声明集合"里 | 声明 592（index.html 静态 541 + JS 内联 51）/ ui 引用 510 / **差集 0** |
| ② 装载可达性 | 每个 ui 模块从 index.html 沿 import 图到得了；被 import 的 `init*` 必须有调用点 | 57 个 ui 模块全部可达 / 0 条忘调 |

守卫**落地即绿**——它防的是明天（`$("outpt-dir")` 这种静默失效正是"点了没反应"的来源）。

### 二、红证 / 反证（`probe-guard-strength.mjs`，7/7 成立）

```
✔ ① 原样：无游离 id（绿）  —— 0 条
✔ ① 注入：ui 引用一个不存在的 id → 红且点名  —— #outpt-dir-typo ← ui/library.js:502
✔ ① 反证：把 index.html 里被引用的 id 改名 → 红且点名  —— #output-dir ← 11 处引用
✔ ② 原样：无孤立模块、无忘调的 init（绿）
✔ ② 注入：从装载清单摘掉一个模块 → 红且点名「孤立模块」
✔ ② 注入：删掉 init 的调用点（import 还在）→ 红且点名
✔ ② 反证：模块内自调的 init 不误报（绿）
PASS：7/7 条成立
```

口径：判据是纯函数（源码文本进、问题清单出），注入加在**内存副本**上——不动仓库里任何文件，
所以红证可反复跑、不会留下污染。

### 三、红证顺手挖出的两个**假判据**（都是我自己写出来的，记下来）

1. **`名字(` 不是调用点**：第一版用 `identRe("initGlossary(")` 判"有没有调用点"——
   而 `bodyText` 里**含定义那行本身**（`export function initGlossary() {` 也匹配 `initGlossary(`），
   于是"删掉启动区调用点"照样绿。红证第一次跑就把这条抓出来了（"没抓到"）。
   **改法**：先把定义行抠掉再判调用点（`withoutInitDefinitions` + `hasCallSite`）。
2. **`resolveSpec` 的基准键必须是"调用方自己"**：第一版把 hostBody（已剥 import 的正文）
   喂给可达性判据 → 装载图一条边都没有 → 57 个模块全判"孤立"。
   **改法**：判据吃**宿主脚本原文**（import 边就在那里），文档里写明。

### 四、一条"刻意不判"的边界（写给下一个人）

「每个 `init*` 导出都必须被 index.html 具名导入」这条**没有做**：ui 里合法地存在
「模块顶部自己调」的写法（`ui/topic.js` 的 `initTopicToolbar` 在模块底部自调），
一刀切会逼出一批为过守卫而加的假导出。可达性由「孤立模块」那条保证；
「被 import 了就一定要有调用点」那条保留（它才是本轮要防的真实事故形态）。
反向用例钉住了"模块内自调不误报"。
