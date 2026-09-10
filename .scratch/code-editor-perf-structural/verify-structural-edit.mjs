// 验收脚本（工单 code-editor-perf-structural/01）：结构性编辑（回车）的
// ① 同步耗时达标（< 50ms 均值 / < 150ms 峰值）② 同步路径零布局强制读
// ③ 滚动位置不跳（删掉「读→写回」后语义仍成立）④ 窗口/行号仍正确。
// 用法：node .scratch/code-editor-perf-structural/verify-structural-edit.mjs
import { mkdirSync, writeFileSync, existsSync } from "node:fs";
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

await rebuildTab({ port: PORT, pageUrl: PAGE_URL, settleMs: 2000 });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 30000 });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e);

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`, 20000);
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click()`);
await c.waitFor(`import('/js/ui/codeeditor.js').then((m) => { const t = m.getActiveTab(); return !!t && t.content.length > 100000; })`, 20000);

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// —— 布局强制读埋点（同 diag：同步路径里出现即算失败）——
await Eval(`(() => {
  const state = { on: false, hits: {} };
  window.__lay = state;
  const key = (n) => { if (state.on) state.hits[n] = (state.hits[n] || 0) + 1; };
  const wrap = (proto, prop) => {
    const d = Object.getOwnPropertyDescriptor(proto, prop);
    if (!d || !d.get) return;
    Object.defineProperty(proto, prop, {
      configurable: true, enumerable: d.enumerable,
      get() { key(prop); return d.get.call(this); },
      set(v) { key(prop + '(set)'); return d.set.call(this, v); },
    });
  };
  ['scrollTop', 'scrollLeft', 'clientHeight', 'offsetHeight', 'offsetTop', 'offsetWidth']
    .forEach((p) => wrap(Element.prototype, p));
  const g = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function () { key('getBoundingClientRect'); return g.apply(this, arguments); };
  return true;
})()`);

// ---- ① 回车同步耗时 + ② 零强制布局读 + 模型真实变更 ----
const enter = await Eval(`(async () => {
  const m = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  await new Promise((r) => requestAnimationFrame(() => r()));
  const before = m.editorViewText();
  const times = [];
  window.__lay.hits = {};
  for (let k = 0; k < 12; k++) {
    ta.setSelectionRange(0, 0);
    window.__lay.on = true;
    const t0 = performance.now();
    ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    const dt = performance.now() - t0;
    window.__lay.on = false;
    if (k >= 2) times.push(dt);
  }
  const after = m.editorViewText();
  return { avg: times.reduce((a, b) => a + b, 0) / times.length, max: Math.max(...times),
    dLines: after.split('\\n').length - before.split('\\n').length,
    dLen: after.length - before.length, hits: window.__lay.hits };
})()`);
check("回车同步耗时 < 50ms（均值）", enter.avg < 50, "avg=" + enter.avg.toFixed(1) + "ms max=" + enter.max.toFixed(1));
check("回车同步耗时 < 150ms（峰值）", enter.max < 150, "max=" + enter.max.toFixed(1));
check("回车真实落库（模型 +12 行 / +12 字符）", enter.dLines === 12 && enter.dLen === 12,
  `dLines=${enter.dLines} dLen=${enter.dLen}`);
const hitKeys = Object.keys(enter.hits);
check("同步路径零布局强制读（scrollTop / clientHeight / GBC 均 0 次）",
  hitKeys.length === 0, hitKeys.length ? JSON.stringify(enter.hits) : "0 次");

// ---- ③ 滚动位置不跳：中部滚动 → 回车 → scrollTop / 窗口首行不变 ----
const scroll = await Eval(`(async () => {
  const box = document.getElementById('code-viewer');
  box.scrollTop = 2500 * 16;   // 大致中部
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const ta = document.querySelector('#code-viewer .code-ta');
  const visibleGutters = () => [...document.querySelectorAll('#code-viewer .code-gutter-line')]
    .map((el) => el.textContent.trim()).filter((t) => /^\\d+$/.test(t));
  const beforeTop = box.scrollTop, beforeGut = visibleGutters();
  const beforeHeight = box.scrollHeight;
  ta.focus();
  ta.setSelectionRange(0, 0);   // 窗口内第一行行首
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  return { beforeTop, afterTop: box.scrollTop, beforeGut, afterGut: visibleGutters(),
    beforeHeight, afterHeight: box.scrollHeight,
    domLines: document.querySelectorAll('#code-viewer .code-hl-line').length };
})()`);
check("中部回车：滚动位置不跳（scrollTop 不变）",
  Math.abs(scroll.afterTop - scroll.beforeTop) < 1, `${scroll.beforeTop} → ${scroll.afterTop}`);
// 视口不位移的判据 = 可见行号序列不变（光标所在行的文本必然被换行改写，
// 行号序列才是「屏幕上看的是同一段」的可观察事实）
check("中部回车：可见窗口行号序列不变（视口不位移）",
  JSON.stringify(scroll.beforeGut) === JSON.stringify(scroll.afterGut)
    && scroll.beforeGut.length > 10,
  `首=${scroll.beforeGut[0]} 行数=${scroll.beforeGut.length}→${scroll.afterGut.length}`);
check("中部回车：内容高度确实变了（+1 行 ⇒ 结构性编辑真的落库）",
  scroll.afterHeight > scroll.beforeHeight, `${scroll.beforeHeight} → ${scroll.afterHeight}`);
check("中部回车：DOM 行数仍有界（窗口化未被破坏）", scroll.domLines < 400, "dom=" + scroll.domLines);

// ---- ④ 回顶 / 滚到尾仍正确（窗口化回归）----
const tail = await Eval(`(async () => {
  const box = document.getElementById('code-viewer');
  box.scrollTop = 0;
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const topGut = document.querySelector('#code-viewer .code-gutter-line')?.textContent.trim();
  box.scrollTop = box.scrollHeight;
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const ta = document.querySelector('#code-viewer .code-ta');
  const model = (await import('/js/ui/codeeditor.js')).getActiveTab().content;
  const lastModelLine = model.split('\\n').pop();
  return { topGut, taHasLastLine: ta.value.includes(lastModelLine.slice(0, 24)),
    domLines: document.querySelectorAll('#code-viewer .code-hl-line').length };
})()`);
check("回顶后窗口从第 1 行开始", tail.topGut === "1", "gut=" + tail.topGut);
check("滚到尾部后窗口覆盖模型末行", tail.taHasLastLine && tail.domLines < 400, "dom=" + tail.domLines);

// ---- 截图存档 ----
mkdirSync(OUT, { recursive: true });
const shot = await c.cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(OUT, "shot-structural-edit-dark.png"), Buffer.from(shot.result.data, "base64"));
console.log("shot-structural-edit-dark.png 已存档");

console.log("---- 验收总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
c.close();
process.exit(failed === 0 ? 0 : 1);
