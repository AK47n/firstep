// ui-dom-contract.test.mjs — ui 层 DOM 契约的**静态**守卫（工单 ui-dom-contract-gate/02）。
//
// `ui/` 模块的 interface 就是 DOM：它绑哪些选择器、绑上之后用户做什么会看到什么。
// 这条 interface 今天就在（57 个模块 / 17,996 行 / 513 个 addEventListener），但此前
// **没有任何东西守它**：`tests/js/` 里涉及 ui 的断言几乎全是"读源码字符串"
// （`assert.match(ui.includes('from "/js/fx/x.js"'))` 这一类），源码里写了什么它管得住，
// 接上去到底还灵不灵一个字都不知道。本文件管**静态那一半**，两条不变量：
//
//   ① **id 存在性**：ui 源码里写死的 id，必须在"页面真正会出现的声明集合"里找得到。
//      游离的 id 就是"点了没反应"的来源——`$("outpt-dir")` 静默返回 null，事件监听挂空，
//      用户点半天没反应、控制台一片安静。
//   ② **装载可达性**：每个 `ui/*.js` 都必须从 index.html 沿 import 图到得了（"写了却从没
//      进页面"），且导出 `init*` 的模块该 init 必须有人具名导入、有人调用
//      （"导入了却忘调" / 改了名忘了跟）。
//
// 行为那一半（点下去真的变、刷新后记不记得住）在真浏览器上，见
// `tests/browser/ui-contract.spec.mjs`（工单 04）。两层分工：这一层零依赖、毫秒级、进前端门禁；
// 那一层真页面 + 真后端。
//
// 判据本体在 tests/js/ui-dom-contract.mjs（单源——红证/探针脚本也 import 它）。
// 与既有守卫的分工：
//   import-usage-guard.test.mjs   导入的名字必须真的被用（防化石回流）
//   static-import-guard.test.mjs  抽 import ↔ 模块导出对账（防死导入打崩整页）
//   本文件                        id 真的存在 + 模块真的可达、init 真的被调
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  listJs, declaredIds, danglingIds, referencedIds, unreachableModules,
} from "./ui-dom-contract.mjs";
import { hostScript } from "./import-usage.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const read = (p) => readFileSync(STATIC + p, "utf8");

// 全前端源码（index.html + js/**）：声明集合的取数面，也是装载图的模块表
const MODULES = listJs(STATIC + "js")
  .map((path) => ({ key: path.slice(STATIC.length), text: readFileSync(path, "utf8") }));
const UI_SOURCES = MODULES
  .filter((m) => m.key.startsWith("js/ui/"))
  .map((m) => ({ path: m.key.slice(3), text: m.text }));
const HTML = read("index.html");
const HOST_SCRIPT = hostScript(HTML);

test("抽取器不静默失效：声明集合、ui 模块、id 引用都抽得到", () => {
  // 这三条是**判据自己的健康检查**：抽取器写坏时下面的断言会"全绿"，
  // 而那种绿比红更坏（它让人以为有人守着）。
  const declared = declaredIds([{ path: "index.html", text: HTML }, ...MODULES]);
  assert.ok(declared.size >= 400,
    `只抽到 ${declared.size} 个声明 id（index.html 结构变了？抽取器过期？）`);
  assert.ok(UI_SOURCES.length >= 40,
    `只抽到 ${UI_SOURCES.length} 个 ui 模块（目录结构变了？）`);
  const referenced = new Set(UI_SOURCES.flatMap((s) => referencedIds(s.path, s.text).map((r) => r.id)));
  assert.ok(referenced.size >= 300,
    `ui 只引用到 ${referenced.size} 个 id（选择器写法变了？抽取器过期？）`);
  assert.ok(HOST_SCRIPT.length > 0, "index.html 里找不到 <script type=\"module\"> 宿主块");
});

test("ui 引用的 id 必须真的会被声明（防游离选择器 → 点了没反应）", () => {
  const declared = declaredIds([{ path: "index.html", text: HTML }, ...MODULES]);
  const dangling = danglingIds(UI_SOURCES, declared);
  const detail = dangling.map(({ id, refs }) =>
    `#${id} ← ${refs.map((r) => `${r.path}:${r.line}`).join(", ")}`);
  assert.deepEqual(
    detail,
    [],
    "ui 源码引用了页面里根本不存在的 id —— 这类选择器静默拿到 null，"
    + "对应的交互永远不会生效（典型症状：点了没反应、控制台无错）。\n"
    + "要么改对 id，要么在渲染它的地方补上 id（fx/ui 模板串里现生成的也算声明）：\n"
    + detail.join("\n")
  );
});

test("每个 ui 模块都必须从 index.html 装载得到（防写了却从没生效）", () => {
  const problems = unreachableModules(UI_SOURCES, HOST_SCRIPT, MODULES);
  const detail = problems.map((p) => `${p.path} — ${p.why}`);
  assert.deepEqual(
    detail,
    [],
    "有 ui 模块没有被页面装载，或它的 init 没人调用 —— 代码写了、跑了、也测不到，"
    + "用户那边就是\"这个功能从来就没出现过\"。\n"
    + "要么在 index.html 的装载清单里具名 import 并调用 init，"
    + "要么（靠被加载才接线的模块）写成裸 import：\n"
    + detail.join("\n")
  );
});
