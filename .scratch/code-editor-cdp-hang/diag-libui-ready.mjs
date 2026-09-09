// 诊断：三个库 tab 的列表容器在页面加载后是否自动有行（就绪判据依赖它）。
import { writeSync } from "node:fs";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 15000 });
await c.cdp("Page.enable");
await c.Eval(`window.__smokeMarker = 1; true`);
await c.cdp("Page.reload", { ignoreCache: true });
await sleep(3000);
log("readyState=" + await c.Eval("document.readyState"));
log("marker=" + await c.Eval("String(window.__smokeMarker)"));
const snap = () => c.Eval(`(() => ({
  lib: document.querySelectorAll('#lib-rows tr').length,
  pdf: document.querySelectorAll('#pdf-rows tr').length,
  ref: document.querySelectorAll('#ref-rows tr').length,
  tabs: ['tab-library','tab-pdf','tab-reference'].map((id) => !!document.getElementById(id)),
  stats: {
    lib: (document.getElementById('lib-stats')||{}).textContent || '',
    pdf: (document.getElementById('pdf-stats')||{}).textContent || '',
    ref: (document.getElementById('ref-stats')||{}).textContent || '',
  },
}))()`);
log("加载后： " + JSON.stringify(await snap()));
// 点三个 tab 再看
for (const label of ["模块库", "PDF 资料库", "参考文件库"]) {
  await c.Eval(`(() => { const b = [...document.querySelectorAll('nav button')].find((x) => x.textContent.trim() === ${JSON.stringify(label)}); if (b) b.click(); return !!b; })()`);
  await sleep(1500);
  log(`点「${label}」后： ` + JSON.stringify(await snap()));
}
c.close();
