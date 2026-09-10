// 诊断（工单 code-editor-perf-structural/01）：回车（结构性编辑）路径的
// **布局强制读**取证——把 Element.prototype 的布局触发访问器（scrollTop /
// clientHeight / offsetHeight / getBoundingClientRect）包一层计数 + 抓栈，
// 在 5000 行 big.c 上派发一次回车，看同步路径里到底是谁在强制布局。
// 用法：node .scratch/code-editor-perf-structural/diag-enter-path.mjs
import { mkdirSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const PORT = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-perf-structural");
const SAMPLE = join(OUT, "sample-proj");
const bigPath = join(SAMPLE, "big.c");
if (!existsSync(bigPath)) {
  mkdirSync(SAMPLE, { recursive: true });
  const lines = [];
  for (let i = 1; i <= 5000; i++) lines.push(`int fn_${i}(int x) { return x + ${i}; }  // line ${i}`);
  writeFileSync(bigPath, lines.join("\n") + "\n");
}
console.log("big.c 行数 = " + readFileSync(bigPath, "utf8").split("\n").length);

await rebuildTab({ port: PORT, pageUrl: PAGE_URL, settleMs: 2000 });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 30000 });
await c.cdp("Page.enable");

await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`, 20000);
await c.Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click()`);
await c.waitFor(`import('/js/ui/codeeditor.js').then((m) => { const t = m.getActiveTab(); return !!t && t.content.length > 100000; })`, 20000);

// —— 布局触发访问器埋点（只统计同步路径；栈取前 3 帧）——
const instrument = `(() => {
  const state = { on: false, hits: {}, ms: {}, stacks: {}, t: 0 };
  window.__lay = state;
  const key = (name, stack, dt) => {
    if (!state.on) return;
    state.hits[name] = (state.hits[name] || 0) + 1;
    state.ms[name] = (state.ms[name] || 0) + dt;
    if (!state.stacks[name]) {
      const frames = String(stack || '').split('\\n').slice(1, 5).map((s) => s.trim().slice(0, 120));
      state.stacks[name] = frames;
    }
  };
  const wrap = (proto, prop) => {
    const d = Object.getOwnPropertyDescriptor(proto, prop);
    if (!d || !d.get) return;
    Object.defineProperty(proto, prop, {
      configurable: true, enumerable: d.enumerable,
      get() { const t0 = performance.now(); const v = d.get.call(this); key(prop, new Error().stack, performance.now() - t0); return v; },
      set(v) { const t0 = performance.now(); const r = d.set.call(this, v); key(prop + '(set)', new Error().stack, performance.now() - t0); return r; },
    });
  };
  ['scrollTop', 'scrollLeft', 'clientHeight', 'clientWidth', 'offsetHeight', 'offsetTop', 'offsetWidth']
    .forEach((p) => wrap(Element.prototype, p));
  const gbcr = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function () {
    const t0 = performance.now();
    const r = gbcr.apply(this, arguments);
    key('getBoundingClientRect', new Error().stack, performance.now() - t0);
    return r;
  };
  const ch = Object.getOwnPropertyDescriptor(Element.prototype, 'clientHeight');
  return { wrapped: !!ch, calls: true };
})()`;
console.log("埋点：" + JSON.stringify(await c.Eval(instrument)));

const run = async (label, key, gapKey) => {
  const r = await c.Eval(`(async () => {
    const m = await import('/js/ui/codeeditor.js');
    const ta = document.querySelector('#code-viewer .code-ta');
    ta.focus();
    window.__lay.on = false;
    // 先落定一次（避免把上一次的残留算进来）
    await new Promise((res) => requestAnimationFrame(() => res()));
    ta.setSelectionRange(0, 0);
    const before = m.editorViewText();
    window.__lay.hits = {}; window.__lay.stacks = {}; window.__lay.ms = {};
    const t0 = performance.now();
    window.__lay.on = true;
    for (let k = 0; k < 5; k++) {
      ta.setSelectionRange(0, 0);
      ta.dispatchEvent(new KeyboardEvent('keydown', { key: ${JSON.stringify(key)}, bubbles: true, cancelable: true }));
    }
    window.__lay.on = false;
    const ms = (performance.now() - t0) / 5;
    const after = m.editorViewText();
    return { label: ${JSON.stringify(label)}, ms, hits: window.__lay.hits, msBy: window.__lay.ms,
      stacks: window.__lay.stacks,
      dLines: after.split('\\n').length - before.split('\\n').length,
      dLen: after.length - before.length,
      domLines: document.querySelectorAll('#code-viewer .code-hl-line').length };
  })()`);
  console.log(`\n=== ${label}：${r.ms.toFixed(1)}ms/次（5 次均值），dLines=${r.dLines} dLen=${r.dLen} DOM行=${r.domLines}`);
  for (const [k, v] of Object.entries(r.hits)) {
    console.log(`    ${k} × ${v}  合计 ${(r.msBy[k] || 0).toFixed(1)}ms（${((r.msBy[k] || 0) / 5).toFixed(1)}ms/次）`);
  }
  for (const [k, v] of Object.entries(r.stacks)) console.log(`    [${k}]\n        ${v.join("\n        ")}`);
  return r;
};

await run("回车（结构性编辑）", "Enter");
await run("Tab（非结构性）", "Tab");

c.close();
