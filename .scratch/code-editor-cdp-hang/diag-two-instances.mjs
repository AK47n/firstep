// 诊断：页面内是否存在**两个 codeeditor.js 模块实例**（DOM 胶水模块被重复求值）。
// 判据：window 上给模块打标记不行（ESM 不挂 window），改用两条独立 import 比较
// 内部状态：先经页面自身入口打开文件，再分别经两次 import 读 openTabPaths()，
// 并对比 DOM 里 #code-tabs 的按钮数。
import { writeSync } from "node:fs";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 10000 });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e, 15000);

// 页面自身入口的实例（动态 import 同一 URL 应命中同一模块记录）
const probe = `import('/js/ui/codeeditor.js').then((m) => ({
  tabs: m.openTabPaths(),
  active: m.getActiveTab() && m.getActiveTab().path,
  domTabs: document.querySelectorAll('#code-tabs .code-tab').length,
}))`;
log("打开目录前： " + JSON.stringify(await Eval(probe)));

const SAMPLE = ".scratch/code-editor-refine/sample-proj";
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="a.c"]')`, 10000);
await Eval(`document.querySelector('#code-tree [data-code-file="a.c"]')?.click()`);
await sleep(800);
log("开 a.c 后： " + JSON.stringify(await Eval(probe)));
await Eval(`document.querySelector('#code-tree [data-code-file="b.c"]')?.click()`);
await sleep(1200);
log("开 b.c 后： " + JSON.stringify(await Eval(probe)));
log("DOM tab 名： " + JSON.stringify(await Eval(
  `Array.from(document.querySelectorAll('#code-tabs .code-tab')).map((b) => b.dataset.tabPath)`)));
// 再点一次 b.c（走 existing 分支的 activateTab）
await Eval(`document.querySelector('#code-tree [data-code-file="b.c"]')?.click()`);
await sleep(800);
log("再点 b.c： " + JSON.stringify(await Eval(probe)));
log("DOM tab 名： " + JSON.stringify(await Eval(
  `Array.from(document.querySelectorAll('#code-tabs .code-tab')).map((b) => b.dataset.tabPath)`)));
c.close();
