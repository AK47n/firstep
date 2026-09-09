// 诊断（code-editor-refine/smoke-02 场景 2 偶发 FAIL）：Ctrl+W 关脏标签确认后
// 剩下的是「干净 a.c」还是「脏 b.c」？逐检查点打印 tab 列表 / 活动 tab / ta 值。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, writeFileSync, writeSync } from "node:fs";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const PORT = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "a.c"), "int a = 1;\n");
writeFileSync(join(SAMPLE, "b.c"), "int b = 2;\n");
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 10000 });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e, 10000);
const state = (tag) => Eval(`import('/js/ui/codeeditor.js').then((m) => ({
  tag: ${JSON.stringify(tag)},
  tabs: m.openTabPaths(),
  active: m.getActiveTab() && m.getActiveTab().path,
  dirty: m.dirtyTabPaths(),
  tabOn: document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath ?? null,
  modal: document.querySelectorAll('.ref-files-overlay').length,
  taVal: document.querySelector('#code-viewer .code-ta')?.value ?? null,
}))`);

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="a.c"]')`, 10000);
await Eval(`document.querySelector('#code-tree [data-code-file="a.c"]')?.click()`);
await sleep(500);
log(JSON.stringify(await state("open a.c")));
await Eval(`document.querySelector('#code-tree [data-code-file="b.c"]')?.click()`);
await c.waitFor(`document.querySelectorAll('#code-tabs .code-tab').length === 2`, 8000);
log(JSON.stringify(await state("open b.c")));

// 造脏（smoke-02 的 setText）
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.value = "int b = 999;\\n"; ta.setSelectionRange(0,0); ta.dispatchEvent(new InputEvent('input', { bubbles: true })); return true; })()`);
await sleep(500);
log(JSON.stringify(await state("after setText")));

const pressOn = (sel, opts) => Eval(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return false; el.dispatchEvent(new KeyboardEvent('keydown', ${JSON.stringify(opts)})); return true; })()`);

await pressOn('#code-viewer .code-ta', { key: "w", ctrlKey: true, bubbles: true, cancelable: true });
await c.waitFor(`document.querySelectorAll('.ref-files-overlay').length >= 1`, 8000);
log(JSON.stringify(await state("modal open #1")));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]')?.click(); true`);
await c.waitFor(`document.querySelectorAll('.ref-files-overlay').length === 0`, 8000);
await sleep(400);
log(JSON.stringify(await state("after cancel")));

await pressOn('#code-viewer .code-ta', { key: "w", ctrlKey: true, bubbles: true, cancelable: true });
await c.waitFor(`document.querySelectorAll('.ref-files-overlay').length === 1`, 8000);
log(JSON.stringify(await state("modal open #2")));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]')?.click(); true`);
await sleep(1200);
log(JSON.stringify(await state("after confirm ok")));
c.close();
