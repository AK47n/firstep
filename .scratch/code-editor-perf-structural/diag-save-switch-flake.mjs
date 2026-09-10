// 诊断：refine/smoke-01 场景 5「保存全部并切换 → 重开该文件内容一致」的偶发红
//（基线 1/4 复现，与第九轮改动无关）。抓失败现场：ta.value / 模型 / 窗口 / 磁盘。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const DIR_A = join(OUT, "sample-proj", "a");
const DIR_B = join(OUT, "sample-proj", "b");
mkdirSync(DIR_A, { recursive: true });
mkdirSync(DIR_B, { recursive: true });

await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/", settleMs: 2000 });
const c = await connect({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const openDir = (d) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(d)}))`);
const openFile = (n) => Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(n)}]')?.click()`);
const setText = (t) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus(); ta.value = ${JSON.stringify(t)}; ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true })); return true; })()`);
const ta = () => Eval(`document.querySelector('#code-viewer .code-ta')?.value ?? null`);
const snap = () => Eval(`(async () => {
  const m = await import('/js/ui/codeeditor.js');
  const t = m.getActiveTab();
  const box = document.getElementById('code-viewer');
  return { label: document.getElementById('code-dir-label').textContent,
    ta: document.querySelector('#code-viewer .code-ta')?.value ?? null,
    tabPath: t ? t.path : null, tabDirty: t ? t.content !== t.savedContent : null,
    tabContent: t ? t.content : null,
    scrollTop: box.scrollTop, viewportH: box.clientHeight,
    domLines: document.querySelectorAll('#code-viewer .code-hl-line').length };
})()`);

for (let attempt = 1; attempt <= 4; attempt++) {
  writeFileSync(join(DIR_A, "main.c"), "int a = 1;\n");
  writeFileSync(join(DIR_B, "other.c"), "int b = 2;\n");
  await Eval(`window.__smokeMarker = 1; true`);
  await c.cdp("Page.reload", { ignoreCache: true });
  await c.waitFor(`document.readyState === 'complete'`, 15000);
  await openDir(DIR_A);
  await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`, 15000);
  await openFile("main.c");
  await c.waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 10000);
  await setText("int a = 999;\n");
  await openDir(DIR_B);
  await c.waitFor(`!!document.querySelector('.code-unsaved-modal')`, 10000);
  await Eval(`document.querySelector('.code-unsaved-modal [data-unsaved-action="discard"]')?.click()`);
  await c.waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_B)}`, 10000);
  await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="other.c"]')`, 10000);
  await openFile("other.c");
  await c.waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 10000);
  await setText("int b = 777;\n");
  await openDir(DIR_A);
  await c.waitFor(`!!document.querySelector('.code-unsaved-modal')`, 10000);
  await Eval(`document.querySelector('.code-unsaved-modal [data-unsaved-action="save"]')?.click()`);
  await c.waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_A)}`, 15000);
  await openDir(DIR_B);
  await c.waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_B)}
    && !!document.querySelector('#code-tree [data-code-file="other.c"]')`, 15000);
  await openFile("other.c");
  let ok = false;
  for (let i = 0; i < 40 && !ok; i++) {
    ok = (await ta()) === "int b = 777;\n";
    if (!ok) await sleep(200);
  }
  const disk = await Eval(`fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(DIR_B)})
    + '&path=' + encodeURIComponent('other.c')).then((r) => r.json()).then((j) => j.content)`);
  console.log(`\n=== attempt ${attempt}: ta 一致=${ok} 磁盘=${JSON.stringify(disk)}`);
  if (!ok) {
    console.log("现场：" + JSON.stringify(await snap(), null, 1));
    console.log("toast：" + JSON.stringify(await Eval(`[...document.querySelectorAll('.toast')].map((t) => t.textContent)`)));
    console.log("树 HTML：" + (await Eval(`document.getElementById('code-tree').innerHTML`)).slice(0, 200));
    console.log("标签：" + JSON.stringify(await Eval(`(async () => (await import('/js/ui/codeeditor.js')).openTabPaths())()`)));
    console.log("tree 里 other.c 节点数：" + await Eval(`document.querySelectorAll('#code-tree [data-code-file="other.c"]').length`));
    // 补点一次（判定「点击丢失」还是「点了没反应」）
    await openFile("other.c");
    await sleep(1500);
    console.log("补点后 ta：" + JSON.stringify(await ta())
      + " tab=" + JSON.stringify(await Eval(`(async () => (await import('/js/ui/codeeditor.js')).openTabPaths())()`)));
  }
}
c.close();
