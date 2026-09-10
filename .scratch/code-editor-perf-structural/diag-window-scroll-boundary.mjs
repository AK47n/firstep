// 诊断：smoke-08「窗口内滚动零 DOM 变更」的边界算术（顶/底行是否被 5px 跨越）。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SAMPLE = join(ROOT, ".scratch", "code-page-vscode-overhaul", "sample-proj");
await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/", settleMs: 2000 });
const c = await connect({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
await c.cdp("Page.enable");
mkdirSync(SAMPLE, { recursive: true });
if (!(await c.Eval(`1`))) process.exit(1);
const lines = [];
for (let i = 1; i <= 5000; i++) lines.push(`int fn_${i}(int x) { return x + ${i}; }  // line ${i}`);
writeFileSync(join(SAMPLE, "big.c"), lines.join("\n") + "\n");

await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`, 20000);
await c.Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click()`);
await c.waitFor(`import('/js/ui/codeeditor.js').then((m) => { const t = m.getActiveTab(); return !!t && t.content.length > 100000; })`, 20000);

const snap = () => c.Eval(`(() => {
  const b = document.getElementById('code-viewer');
  const hl = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const gut = [...document.querySelectorAll('#code-viewer .code-gutter-line')];
  const cs = getComputedStyle(document.querySelector('#code-viewer .code-hl'));
  return { scrollTop: b.scrollTop, scrollHeight: b.scrollHeight, clientHeight: b.clientHeight,
    lineHeight: cs.lineHeight, fontSize: cs.fontSize,
    hl: hl.length, first: hl[0]?.dataset.codeLine, last: hl[hl.length - 1]?.dataset.codeLine,
    gut: gut.length, firstGut: gut[0]?.dataset.codeLine, lastGut: gut[gut.length - 1]?.dataset.codeLine };
})()`);
const fx = (t, vh, lh, n, ov) => {
  const start = Math.max(0, Math.min(n - 1, Math.floor((t - 8) / lh) - ov));
  const end = Math.max(start + 1, Math.min(n, Math.ceil((t + vh - 8) / lh) + ov));
  return { start: start + 1, end };
};

await c.Eval(`document.getElementById('code-viewer').scrollTop = document.getElementById('code-viewer').scrollHeight * 0.5`);
await new Promise((r) => setTimeout(r, 500));
const a = await snap();
console.log("中部：" + JSON.stringify(a));
await c.Eval(`document.getElementById('code-viewer').scrollTop += 5`);
await new Promise((r) => setTimeout(r, 500));
const b2 = await snap();
console.log("+5px：" + JSON.stringify(b2));
const lh = parseFloat(a.lineHeight);
console.log("纯件窗口 before=" + JSON.stringify(fx(a.scrollTop, a.clientHeight, lh, 5001, 20)));
console.log("纯件窗口 after =" + JSON.stringify(fx(b2.scrollTop, b2.clientHeight, lh, 5001, 20)));
console.log("DOM 变了吗：hl " + a.hl + "→" + b2.hl + "，first " + a.first + "→" + b2.first + "，last " + a.last + "→" + b2.last);
c.close();
