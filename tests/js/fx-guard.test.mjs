// fx-guard.test.mjs — 纯函数单源不回流（工单 frontend-es-modules/11 立，工单
// frontend-boot-module/05 **退化**）。
//
// ## 为什么退化
//
// 这个文件原先养着一张 **337 行手工登记表**（`DOMAINS`：把工单 01-10 累计搬出去的每一个
// 名字逐个列出来，再拿正则去 index.html 里查"有没有被重新定义"）。它有三个代价：
//   · 名字表是手抄的——迁一个新函数忘了登记，守卫就少看一眼；
//   · 检查面只有 index.html——宿主块搬进 boot.js 之后，回退到装载根里它就看不见了；
//   · "某个导出存不存在"这件事被写在三处（模块 / 登记表 / 宿主 import），错一处就整页死。
//
// 工单 05 把它换成**四条结构不变量**（判据单源 = tests/js/boot-contract.mjs，不需要任何名字表）：
//   ① `index.html` 零顶层 JS 定义（HTML 不再是模块图的一部分）
//   ② 装载根 `boot.js` 零顶层定义（纯函数没有"回流到装载根"这条路）
//   ③ index.html 的脚本块恰好两处（head 主题脚本 ＋ 一条装载标签）——补 ①② 抓不到的
//      表达式形态内联 JS（`(function(){…})()`）
//   ④ 每个 fx/ui 模块从装载根可达（掉出模块图 = 静默失效，2026-09-12 那类）
//
// **代价记账的更新**（工单 05 双轴评审指出两条退化掉的代价 → 工单 export-surface-guard/01-03
// 把它们**收回来了**，但收在**另一个**守卫里，本文件仍只管上面四条结构不变量）：
//   · **没人 import 的导出** → 由 **判据 D** 守（`tests/js/export-surface-guard.test.mjs`，
//     判据本体在 boot-contract.mjs）：每条导出必须被一条 import 边消费，消费者 = 页面图 ∪
//     tests/js ∪ tests/browser。清点先例：111 处清成 0（110 摘 `export` ＋ 1 条整条删）——
//     评审当时点出的 7 个（`CCS_PIECE_NAMES` / `maincScrollToRange` / `codeEditorHighlight` /
//     `HWCHECK_VERDICT_FALLBACK` / `BUY_DECISIONS_KEY` / `SETTINGS_DEFAULT_COLLAPSED` / `wfNum`）
//     实测**都是活的定义 ＋ 多余的 `export`**（被本模块内部或 window 探针桥用着），不是死代码。
//   · **类型维度的 fn 轴** → 由 **判据 T** 守（同上那个守卫）：被调用的导入名必须解析成函数形态，
//     跟随再导出链与函数别名链，**解不开按违规算**。
//   · **仍不守**：常量的**值**形态（number/string/object，旧表 28 条 `typeof` 断言的另一半）——
//     无法从用法派生，只能靠名单或生成式快照，而那正是本文件拆掉的东西。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  inlineDefinitions, topLevelDefinitions, readLoadRoot, readJsModules, reachable, scriptBlocks,
} from "./boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const html = readFileSync(STATIC + "index.html", "utf8");
const boot = readLoadRoot(STATIC);
const MODULES = readJsModules(STATIC);
const FX = MODULES.filter((m) => m.key.startsWith("fx/"));
const UI = MODULES.filter((m) => m.key.startsWith("ui/"));

test("抽取器不静默失效：装载根在、模块表抽得到、且判据**能报出**注入的定义", () => {
  assert.ok(boot !== null, "找不到装载根 static/js/boot.js");
  assert.ok(MODULES.length >= 120, `只抽到 ${MODULES.length} 个模块（目录结构变了？）`);
  assert.ok(FX.length >= 60, `只抽到 ${FX.length} 个 fx 模块`);
  assert.ok(UI.length >= 50, `只抽到 ${UI.length} 个 ui 模块`);
  // **正向对照**：下面 ①② 是"断言为空"，抽取器一旦静默失效会**真空绿**
  //（先例 ui-dom-contract.test.mjs：「那种绿比红更坏」）。所以这里先证明判据真的会报。
  assert.equal(topLevelDefinitions("function probeControl() {}").length, 1,
    "topLevelDefinitions 对注入的顶层 function 没反应（抽取器失效？）");
  assert.equal(inlineDefinitions('<script>const probeControl = 1;</script>').length, 1,
    "inlineDefinitions 对注入的内联 const 没反应（抽取器失效？）");
});

test("① index.html 零顶层 JS 定义（HTML 不再是模块图的一部分）", () => {
  const defs = inlineDefinitions(html).map((d) => `  ${d.line}: ${d.text}`);
  assert.deepEqual(defs, [],
    "index.html 里出现顶层 JS 定义 —— 它必须住在 fx/ 或 ui/ 模块里：\n" + defs.join("\n"));
});

test("② 装载根 boot.js 零顶层定义（纯函数没有回流到装载根这条路）", () => {
  const defs = topLevelDefinitions(boot).map((d) => `  ${d.line}: ${d.text}`);
  assert.deepEqual(defs, [],
    "boot.js 里出现顶层定义 —— 装载根只该有 import、接线调用、页签分发器与启动 IIFE：\n"
    + defs.join("\n"));
});

test("③ index.html 的脚本块恰好两处：head 内联主题脚本 ＋ 一条 type=module 装载标签", () => {
  // 这条补 ①② 的缝（工单 05 评审指出）：`(function(){…})()` 这类**表达式**形态的内联 JS
  // 既不是 import 也不是"顶层定义"，①② 都抓不到。直接把"HTML 里还有别的 JS"这件事判死。
  const blocks = scriptBlocks(html).map((b) => ({ src: b.src, attrs: b.attrs.trim(), line: b.line }));
  const inline = blocks.filter((b) => b.src === null);
  const withSrc = blocks.filter((b) => b.src !== null);
  assert.equal(blocks.length, 2, `index.html 的脚本块应为 2 个，实际 ${blocks.length}：`
    + JSON.stringify(blocks));
  assert.equal(inline.length, 1, "只允许 head 里那一条主题防闪烁内联脚本");
  assert.equal(withSrc.length, 1, "只允许一条带 src 的装载标签");
  assert.equal(withSrc[0].src, "/js/boot.js", `装载标签应指向 /js/boot.js（实际 ${withSrc[0].src}）`);
});

test("④ 每个 fx/ui 模块都必须从装载根可达（防写了却从没生效）", () => {
  const { orphans } = reachable(boot, MODULES);
  assert.deepEqual(orphans, [],
    "这些模块掉出了模块图（没有任何路径从装载根走到它）—— 代码写了、跑了、也测不到：\n"
    + orphans.map((o) => "  " + o).join("\n"));
});
