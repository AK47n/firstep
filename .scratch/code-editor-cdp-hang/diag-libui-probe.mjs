// 诊断：三个库 tab 的 DOM 与数据端点实况（重写 smoke 脚本前的事实采集）。
// 用法：node .scratch/code-editor-cdp-hang/diag-libui-probe.mjs
import { writeSync } from "node:fs";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const log = (s) => writeSync(1, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 20000 });
await c.cdp("Page.enable");
await c.Eval(`window.__smokeMarker = 1; true`);
await c.cdp("Page.reload", { ignoreCache: true });
await sleep(3500);
log("readyState=" + await c.Eval("document.readyState"));

// 端点形状
for (const url of ["/api/modules", "/api/pdfs", "/api/references"]) {
  const s = await c.Eval(`(async () => {
    const r = await fetch(${JSON.stringify(url)});
    const j = await r.json();
    const arr = Array.isArray(j) ? j : (j.entries || j.modules || j.items || []);
    return { status: r.status, isArr: Array.isArray(j), keys: Array.isArray(j) ? null : Object.keys(j),
             n: arr.length, first: arr[0] ? Object.keys(arr[0]) : null };
  })()`);
  log(url + " → " + JSON.stringify(s));
}

const tabs = [
  ["模块库", "tab-library", "#lib-rows tr", "#lib-stats"],
  ["PDF 资料库", "tab-pdf", "#pdf-rows tr", "#pdf-stats"],
  ["参考文件库", "tab-reference", "#ref-rows tr", "#ref-stats"],
];
for (const [label, tabId, rowSel, statsSel] of tabs) {
  await c.Eval(`(() => { const b = [...document.querySelectorAll('nav button')].find((x) => x.textContent.trim() === ${JSON.stringify(label)}); if (b) b.click(); return !!b; })()`);
  await sleep(1800);
  const snap = await c.Eval(`(() => ({
    tab: !!document.getElementById(${JSON.stringify(tabId)}),
    rows: document.querySelectorAll(${JSON.stringify(rowSel)}).length,
    stats: (document.querySelector(${JSON.stringify(statsSel)})||{}).textContent || '',
  }))()`);
  log(`${label} → ` + JSON.stringify(snap));
}

// 页面内 import 取纯件与 state 的可行性
const imp = await c.Eval(`(async () => {
  const out = {};
  try { const m = await import('/js/fx/module.js'); out.module = ['libFilterModules','libStats','libStatsText'].every((k) => typeof m[k] === 'function'); } catch (e) { out.module = 'ERR ' + e.message; }
  try { const m = await import('/js/fx/pdf.js'); out.pdf = ['pdfFilterEntries','pdfSortEntries','pdfStats','pdfHealth','pdfRowHTML'].every((k) => typeof m[k] === 'function'); } catch (e) { out.pdf = 'ERR ' + e.message; }
  try { const m = await import('/js/fx/reference.js'); out.ref = ['refFilterEntries','refSortEntries','refStats','refDanglingAnchors'].every((k) => typeof m[k] === 'function'); } catch (e) { out.ref = 'ERR ' + e.message; }
  try { const m = await import('/js/app.js'); out.state = Array.isArray(m.state && m.state.modules) ? m.state.modules.length : 'no'; } catch (e) { out.state = 'ERR ' + e.message; }
  try { const m = await import('/js/ui/pdf.js'); out.loadPdfs = typeof m.loadPdfs; } catch (e) { out.loadPdfs = 'ERR'; }
  try { const m = await import('/js/ui/reference.js'); out.loadReferences = typeof m.loadReferences; out.loadKitVocabulary = typeof m.loadKitVocabulary; } catch (e) { out.loadReferences = 'ERR'; }
  try { const m = await import('/js/ui/library.js'); out.loadLibrary = typeof m.loadLibrary; } catch (e) { out.loadLibrary = 'ERR'; }
  return out;
})()`);
log("页面内 import → " + JSON.stringify(imp));

// 关键 DOM id 在场性
const ids = await c.Eval(`(() => {
  const want = ['lib-search','lib-sort','lib-sort-dir','lib-filter-clear','lib-stats','lib-platform-chips','lib-status-chips','lib-rows','lib-msg',
    'pdf-filter','pdf-sort','pdf-sort-dir','pdf-filter-clear','pdf-batch-chips','pdf-stats','pdf-rows','pdf-msg','pdf-refresh',
    'ref-filter','ref-sort','ref-sort-dir','ref-filter-clear','ref-stats','ref-platform-chips','ref-anchor-chips','ref-rows','ref-msg',
    'add-sec-basic','add-sec-files','add-sec-adv','add-sec-ref-basic','add-sec-ref-material','add-sec-ref-platform','ref-files','btn-ref-add-file-row','btn-ref-add'];
  const miss = want.filter((i) => !document.getElementById(i));
  return { total: want.length, miss };
})()`);
log("DOM id → " + JSON.stringify(ids));
c.close();
