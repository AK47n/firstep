// 取证（第十轮·决定性）：抓「点『保存全部并切换』无效果」的**动作级轨迹**。
//
// 现场（.scratch/code-editor-refine/fail-capture-A-*.txt，A 组第 2 次，单跑即复现）：
//   点 save 三秒后 → label 仍是 b、ta 仍 "int b = 777;\n"（脏标签没被清）、磁盘仍是 "int b = 2;\n"
//   即：**目录没切、保存没发生**——不是「保存了没落盘」，而是「save 动作根本没跑」。
//
// 做法：垫 setCodeDir（ui/codeeditor.js 的导出）+ ui/codeview.js 的导出模块命名空间，
// 记录每次动作的入参/返回/异常 + 当时的动作前状态（脏标签清单 / 激活路径）。
// 不改产品代码；垫片只在本页生命周期内生效。
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
const ROUNDS = Number(process.argv[2] || 3);

await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/", settleMs: 2000 });
const c = await connect({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 垫片：记录 setCodeDir 的每一次调用（入参 / 返回 / 抛错 / 前后状态）
const PATCH = `(async () => {
  if (window.__tracePatched) return 'already';
  window.__tracePatched = true;
  window.__trace = [];
  const ed = await import('/js/ui/codeeditor.js');
  const orig = ed.setCodeDir;
  const snap = () => {
    const t = ed.getActiveTab();
    return { active: t ? t.path : null, dirty: ed.openTabPaths().length,
      dirtyCount: (typeof ed.dirtySavableTabCount === 'function' ? ed.dirtySavableTabCount() : null),
      label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop(),
      modal: !!document.querySelector('.code-unsaved-modal') };
  };
  const wrap = (o, k) => {
    const f = o[k];
    o[k] = async function (...a) {
      const before = snap();
      const rec = { fn: k, arg: String(a[0] || '').split(/[\\\\/]/).pop(), before, t: Math.round(performance.now()) };
      window.__trace.push(rec);
      try { const r = await f.apply(this, a); rec.ret = r; rec.after = snap(); return r; }
      catch (e) { rec.err = String(e && e.message || e); rec.after = snap(); throw e; }
    };
  };
  wrap(ed, 'setCodeDir');
  return 'patched';
})()`;

for (let attempt = 1; attempt <= ROUNDS; attempt++) {
  writeFileSync(join(DIR_A, "main.c"), "int a = 1;\n");
  writeFileSync(join(DIR_B, "other.c"), "int b = 2;\n");
  await Eval(`window.__smokeMarker = 1; true`);
  await c.cdp("Page.reload", { ignoreCache: true });
  await c.waitFor(`document.readyState === 'complete'`, 15000);
  await Eval(PATCH);
  await Eval(`window.__trace = []; true`);

  const r = await Eval(`(async () => {
    const cv = await import('/js/ui/codeview.js');
    const ed = await import('/js/ui/codeeditor.js');
    const sleep = (ms) => new Promise((x) => setTimeout(x, ms));
    const log = [];
    const openFile = async (name) => {
      for (let i = 0; i < 3; i++) {
        for (let k = 0; k < 40 && !document.querySelector('#code-tree [data-code-file="' + name + '"]'); k++) await sleep(200);
        await sleep(250);
        if (!document.querySelector('#code-tree [data-code-file="' + name + '"]')) continue;
        document.querySelector('#code-tree [data-code-file="' + name + '"]').click();
        for (let k = 0; k < 15; k++) { if (ed.getActiveTab() && ed.getActiveTab().path === name) return true; await sleep(200); }
      }
      return false;
    };
    cv.openCodeViewer(${JSON.stringify(DIR_A)});
    log.push('openA');
    await openFile('main.c');
    await sleep(300);
    // 改脏
    const ta = () => document.querySelector('#code-viewer .code-ta');
    ta().focus(); ta().value = 'int a = 999;\\n'; ta().setSelectionRange(0,0);
    ta().dispatchEvent(new InputEvent('input', { bubbles: true }));
    log.push('dirtyA=' + (ed.getActiveTab() ? ed.getActiveTab().content !== ed.getActiveTab().savedContent : null));
    // 切 B（discard）
    cv.openCodeViewer(${JSON.stringify(DIR_B)});
    for (let k = 0; k < 40 && !document.querySelector('.code-unsaved-modal'); k++) await sleep(100);
    document.querySelector('.code-unsaved-modal [data-unsaved-action="discard"]')?.click();
    await sleep(1200);
    log.push('afterDiscard label=' + document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop());
    await openFile('other.c');
    ta().focus(); ta().value = 'int b = 777;\\n'; ta().setSelectionRange(0,0);
    ta().dispatchEvent(new InputEvent('input', { bubbles: true }));
    log.push('dirtyB=' + (ed.getActiveTab() ? ed.getActiveTab().content !== ed.getActiveTab().savedContent : null));
    // 切 A → save
    const tClick = Math.round(performance.now());
    cv.openCodeViewer(${JSON.stringify(DIR_A)});
    let modalAt = null;
    for (let k = 0; k < 60 && !document.querySelector('.code-unsaved-modal'); k++) { await sleep(100); modalAt = Math.round(performance.now()); }
    const btn = document.querySelector('.code-unsaved-modal [data-unsaved-action="save"]');
    log.push('modal=' + !!document.querySelector('.code-unsaved-modal') + ' btn=' + !!btn);
    btn?.click();
    await sleep(3000);
    const box = document.getElementById('code-viewer');
    return { log, tClick, modalAt,
      label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop(),
      ta: document.querySelector('#code-viewer .code-ta')?.value ?? null,
      tabs: ed.openTabPaths(), modal: !!document.querySelector('.code-unsaved-modal'),
      toasts: [...document.querySelectorAll('.toast')].map((x) => x.textContent),
      trace: window.__trace };
  })()`);
  const disk = await Eval(`fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(DIR_B)})
    + '&path=other.c').then((r) => r.json()).then((j) => j.content)`);
  console.log(`\n=== attempt ${attempt} ===`);
  console.log(JSON.stringify({ ...r, diskB: disk }, null, 1));
  // 页面 reload 会让垫片失效 → 每轮重新打（循环开头已 reload + PATCH）
}
c.close();
