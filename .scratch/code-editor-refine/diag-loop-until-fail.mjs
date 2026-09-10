// 取证（第十轮·循环抓失败）：smoke-01 场景 5 的「点保存全部并切换后目录没切」偶发
// （现场见 fail-capture-A-*.txt：label=b / ta 仍脏 / 磁盘未变 / 模态已关）——
// 打**模态生命周期**轨迹（出现/点了哪个钮/解析的动作），失败即打印现场。
//
// 用法：node .scratch/code-editor-refine/diag-loop-until-fail.mjs [最多次数]
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
const ROUNDS = Number(process.argv[2] || 10);

await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/", settleMs: 2000 });
const c = await connect({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e);

// 页面内一次性探针：MutationObserver 记录 .code-unsaved-modal 的出现/消失 + 点击目标 +
// 每次 setCodeDir 派发的「保存全部」动作按钮点击；再记录 label 变化时间线。
const PATCH = `(() => {
  if (window.__modalTrace) return 'already';
  window.__modalTrace = [];
  const T = () => Math.round(performance.now());
  const push = (o) => window.__modalTrace.push(Object.assign({ t: T() }, o));
  new MutationObserver((muts) => {
    for (const m of muts) {
      for (const n of m.addedNodes) {
        if (n.nodeType === 1 && n.classList && n.classList.contains('code-unsaved-modal')) {
          push({ ev: 'modal-open', msg: (n.querySelector('.confirm-message') || {}).textContent || null });
        }
      }
      for (const n of m.removedNodes) {
        if (n.nodeType === 1 && n.classList && n.classList.contains('code-unsaved-modal')) push({ ev: 'modal-close' });
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
  // 捕获阶段记录「模态内按钮」的点击（谁被按了）
  document.addEventListener('click', (e) => {
    const b = e.target && e.target.closest && e.target.closest('.code-unsaved-modal [data-unsaved-action]');
    if (b) push({ ev: 'click', action: b.dataset.unsavedAction });
  }, true);
  // label 变化时间线
  const lbl = document.getElementById('code-dir-label');
  new MutationObserver(() => push({ ev: 'label', value: lbl.textContent.split(/[\\\\/]/).pop() }))
    .observe(lbl, { childList: true, characterData: true, subtree: true });
  return 'patched';
})()`;

let fails = 0;
for (let attempt = 1; attempt <= ROUNDS; attempt++) {
  writeFileSync(join(DIR_A, "main.c"), "int a = 1;\n");
  writeFileSync(join(DIR_B, "other.c"), "int b = 2;\n");
  await Eval(`window.__smokeMarker = 1; true`);
  await c.cdp("Page.reload", { ignoreCache: true });
  await c.waitFor(`document.readyState === 'complete'`, 15000);
  await Eval(PATCH);

  const r = await Eval(`(async () => {
    const cv = await import('/js/ui/codeview.js');
    const ed = await import('/js/ui/codeeditor.js');
    const sleep = (ms) => new Promise((x) => setTimeout(x, ms));
    const ta = () => document.querySelector('#code-viewer .code-ta');
    const waitTa = async () => { for (let k = 0; k < 50 && !ta(); k++) await sleep(100); };
    const openFile = async (name) => {
      for (let i = 0; i < 3; i++) {
        for (let k = 0; k < 40 && !document.querySelector('#code-tree [data-code-file="' + name + '"]'); k++) await sleep(200);
        await sleep(250);
        if (!document.querySelector('#code-tree [data-code-file="' + name + '"]')) continue;
        document.querySelector('#code-tree [data-code-file="' + name + '"]').click();
        for (let k = 0; k < 20; k++) { if (ed.getActiveTab() && ed.getActiveTab().path === name) return true; await sleep(200); }
      }
      return false;
    };
    const setDirty = (v) => { ta().focus(); ta().value = v; ta().setSelectionRange(0, 0);
      ta().dispatchEvent(new InputEvent('input', { bubbles: true })); };

    cv.openCodeViewer(${JSON.stringify(DIR_A)});
    await openFile('main.c'); await waitTa(); await sleep(200);
    setDirty('int a = 999;\\n');
    cv.openCodeViewer(${JSON.stringify(DIR_B)});
    for (let k = 0; k < 60 && !document.querySelector('.code-unsaved-modal'); k++) await sleep(100);
    document.querySelector('.code-unsaved-modal [data-unsaved-action="discard"]')?.click();
    await sleep(1200);
    await openFile('other.c'); await waitTa(); await sleep(200);
    setDirty('int b = 777;\\n');
    const dirtyBefore = ed.getActiveTab() ? ed.getActiveTab().content !== ed.getActiveTab().savedContent : null;
    // —— 场景 5：切 A 并点「保存全部」——
    cv.openCodeViewer(${JSON.stringify(DIR_A)});
    for (let k = 0; k < 80 && !document.querySelector('.code-unsaved-modal'); k++) await sleep(50);
    const hadModal = !!document.querySelector('.code-unsaved-modal');
    document.querySelector('.code-unsaved-modal [data-unsaved-action="save"]')?.click();
    await sleep(4000);
    const t2 = ed.getActiveTab();
    return { dirtyBefore, hadModal,
      label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop(),
      ta: document.querySelector('#code-viewer .code-ta')?.value ?? null,
      tabs: ed.openTabPaths(), modalOpen: !!document.querySelector('.code-unsaved-modal'),
      tabContent: t2 ? t2.content : null, tabSaved: t2 ? t2.savedContent : null,
      toasts: [...document.querySelectorAll('.toast')].map((x) => x.textContent),
      trace: window.__modalTrace };
  })()`);
  const diskB = await Eval(`fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(DIR_B)})
    + '&path=other.c').then((x) => x.json()).then((j) => j.content)`);
  const ok = r.label === "a" && diskB === "int b = 777;\n" && r.tabs.length === 0;
  console.log(`attempt ${attempt}: ${ok ? "OK" : "FAIL"} label=${r.label} ta=${JSON.stringify(r.ta)} diskB=${JSON.stringify(diskB)} tabs=${JSON.stringify(r.tabs)}`);
  if (!ok) {
    fails++;
    console.log("现场：" + JSON.stringify({ ...r, diskB }, null, 1));
    const f = join(OUT, `save-action-fail-${Date.now()}.json`);
    writeFileSync(f, JSON.stringify({ attempt, ...r, diskB }, null, 1), "utf8");
    console.log("已落盘 " + f);
  }
}
console.log(`\n---- ${ROUNDS} 次里失败 ${fails} 次 ----`);
c.close();
