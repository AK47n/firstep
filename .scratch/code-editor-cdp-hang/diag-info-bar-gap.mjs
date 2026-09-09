// 诊断（code-viewer-editor/smoke-07「折叠后代码区紧贴标签条」FAIL）：
// 量 #code-tabs 底到 #code-viewer 顶的实际间距，并打印中间元素的高度。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeSync } from "node:fs";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const PORT = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-viewer-editor", "sample-proj");
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 10000 });
await c.cdp("Page.enable");
await c.Eval(`localStorage.removeItem('firstep.codeSideCollapsed'); true`);
await c.cdp("Page.reload", { ignoreCache: true });
await c.waitFor(`document.readyState === 'complete' && !!document.getElementById('code-viewer')`, 15000);
await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length >= 2`, 10000);
await c.Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await c.waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 10000);
await sleep(800);

const measure = () => c.Eval(`(() => {
  const tabs = document.getElementById('code-tabs');
  const viewer = document.getElementById('code-viewer');
  const p = document.querySelector('.code-file-path');
  const cs = p ? getComputedStyle(p) : null;
  const between = [];
  let el = tabs && tabs.nextElementSibling;
  while (el && el !== viewer) {
    between.push({ cls: String(el.className).slice(0, 60), h: Math.round(el.getBoundingClientRect().height) });
    el = el.nextElementSibling;
  }
  return {
    gap: viewer.getBoundingClientRect().top - tabs.getBoundingClientRect().bottom,
    tabsBottom: Math.round(tabs.getBoundingClientRect().bottom),
    viewerTop: Math.round(viewer.getBoundingClientRect().top),
    pathDisplay: cs ? cs.display : 'no-el',
    pathHeight: p ? Math.round(p.getBoundingClientRect().height) : -1,
    pathEmpty: p ? p.classList.contains('empty') : null,
    between,
  };
})()`);

log("折叠后（立即）： " + JSON.stringify(await measure()));
await sleep(1000);
log("折叠后（+1s）：  " + JSON.stringify(await measure()));
await sleep(2000);
log("折叠后（+3s）：  " + JSON.stringify(await measure()));
c.close();
