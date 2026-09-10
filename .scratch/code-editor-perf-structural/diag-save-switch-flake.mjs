// 取证脚本（第十轮，工单 code-editor-refine/01 场景 5 偶发定性）：
// 「保存全部并切换 → 重开该文件内容一致」的两个签名分开抓，各自带**点击时刻**现场。
//
// 背景（第九轮收口登记的两个签名）：
//   ① 无活动标签：切目录后 #code-tree 先被清成「加载中…」再重渲染，而
//      waitFor(节点在场) 会被**上一目录留下的同名节点**满足 → click 落在已移除节点上
//      （`?.click()` 静默 no-op）→ ta=null / 标签=[]。
//   ② 保存未落盘：ta=777 而磁盘仍是旧值。
//
// 本脚本的判据（比旧版严）：
//   - openFileRaw() **返回是否点开了**（旧版忽略返回值，点丢也算「跑过」）；
//   - 点击**之前**再快照一次现场（节点在/不在、树里有没有 other.c、树是否「加载中…」），
//     点丢时能把「点了个已移除的节点」与「点了不存在的节点」区分开；
//   - 签名 ① 与签名 ② 分开计数（旧版只看 ta 一致，两者混在一个 false 里）。
//
// 用法：node .scratch/code-editor-perf-structural/diag-save-switch-flake.mjs [轮数]
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
const ROUNDS = Number(process.argv[2] || 8);

await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/", settleMs: 2000 });
const c = await connect({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const openDir = (d) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(d)}))`);
const setText = (t) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus(); ta.value = ${JSON.stringify(t)}; ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true })); return true; })()`);
const taValue = () => Eval(`document.querySelector('#code-viewer .code-ta')?.value ?? null`);
const tabs = () => Eval(`(async () => (await import('/js/ui/codeeditor.js')).openTabPaths())()`);
const diskOf = (dir, path) => Eval(`fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(dir)})
  + '&path=' + encodeURIComponent(${JSON.stringify(path)})).then((r) => r.json()).then((j) => j.content).catch(() => '(读盘失败)')`);
// 点击时刻现场：节点在不在 / 树里有没有目标 / 树是不是「加载中…」/ 有没有活动标签
const clickScene = (name) => Eval(`(() => {
  const box = document.getElementById('code-tree');
  const n = box.querySelector('[data-code-file=${JSON.stringify(name)}]');
  return { nodePresent: !!n, nodeConnected: !!(n && n.isConnected),
    treeText: box.textContent.trim().slice(0, 24),
    treeFiles: [...box.querySelectorAll('[data-code-file]')].map((b) => b.dataset.codeFile),
    label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop() };
})()`);

// openFileG(name)：带守卫（= smoke-01 现行口径：点前等节点稳定 + 打开失败重试 3 次）。
// 返回 {ok, tries, scenes}。
const openFileG = async (name) => {
  const scenes = [];
  for (let i = 0; i < 3; i++) {
    await c.waitFor(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')`, 8000);
    await sleep(250);
    const stable = await Eval(`!!document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')`);
    if (!stable) { scenes.push({ try: i + 1, skipped: "节点不稳定" }); continue; }
    scenes.push(Object.assign({ try: i + 1 }, await clickScene(name)));
    await Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
    const ok = await c.waitFor(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab()?.path === ${JSON.stringify(name)})`, 1500);
    if (ok) return { ok: true, tries: i + 1, scenes };
  }
  return { ok: false, tries: 3, scenes };
};

// openFileRaw(name)：裸点一次（= 旧版 diag 口径，用来证明「点丢」这件事本身）。
const openFileRaw = async (name) => {
  await c.waitFor(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')`, 8000);
  const scene = await clickScene(name);
  await Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
  const ok = await c.waitFor(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab()?.path === ${JSON.stringify(name)})`, 1500);
  return { ok, scene };
};

const stats = { rounds: ROUNDS, sigNoTab: 0, sigStaleDisk: 0, ok: 0, guardSaved: 0, rawLost: 0, details: [] };

for (let attempt = 1; attempt <= ROUNDS; attempt++) {
  writeFileSync(join(DIR_A, "main.c"), "int a = 1;\n");
  writeFileSync(join(DIR_B, "other.c"), "int b = 2;\n");
  await Eval(`window.__smokeMarker = 1; true`);
  await c.cdp("Page.reload", { ignoreCache: true });
  await c.waitFor(`document.readyState === 'complete'`, 15000);
  await openDir(DIR_A);
  await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`, 15000);
  await openFileG("main.c");
  await c.waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 10000);
  await setText("int a = 999;\n");
  await openDir(DIR_B);
  await c.waitFor(`!!document.querySelector('.code-unsaved-modal')`, 10000);
  await Eval(`document.querySelector('.code-unsaved-modal [data-unsaved-action="discard"]')?.click()`);
  await c.waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_B)}`, 10000);
  await openFileG("other.c");
  await c.waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 10000);
  await setText("int b = 777;\n");
  // —— 保存全部并切换（场景 5 本体）——
  await openDir(DIR_A);
  await c.waitFor(`!!document.querySelector('.code-unsaved-modal')`, 10000);
  await Eval(`document.querySelector('.code-unsaved-modal [data-unsaved-action="save"]')?.click()`);
  await c.waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_A)}`, 15000);
  // 保存落盘判据（签名 ② 的**直接**判据，不依赖重开）：落定后读盘必须已是 777
  const diskAfterSave = await diskOf(DIR_B, "other.c");
  // —— 重开 B/other.c（场景 5b 本体）——
  await openDir(DIR_B);
  await c.waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_B)}`, 15000);
  const raw = await openFileRaw("other.c");        // 先裸点一次：记录「点丢」现象
  const guarded = raw.ok ? { ok: true, tries: 1 } : await openFileG("other.c");  // 点丢则走守卫重试
  if (!raw.ok) stats.rawLost++;
  if (!raw.ok && guarded.ok) stats.guardSaved++;
  let ta = null, disk = null, sig = "ok";
  if (!guarded.ok) {
    sig = "sigNoTab";
    stats.sigNoTab++;
  } else {
    for (let i = 0; i < 40; i++) { ta = await taValue(); if (ta === "int b = 777;\n") break; await sleep(200); }
    disk = await diskOf(DIR_B, "other.c");
    if (ta !== "int b = 777;\n" || disk !== "int b = 777;\n") {
      sig = (ta === "int b = 777;\n" && disk !== "int b = 777;\n") ? "sigStaleDisk" : "sigNoTab";
      stats[sig === "sigStaleDisk" ? "sigStaleDisk" : "sigNoTab"]++;
    } else stats.ok++;
  }
  const line = `attempt ${attempt}: ${sig === "ok" ? "OK" : sig.toUpperCase()}`
    + ` | 落盘后磁盘=${JSON.stringify(diskAfterSave)}`
    + ` | 裸点=${raw.ok ? "命中" : "点丢"}${raw.ok ? "" : `(现场 ${JSON.stringify(raw.scene)})`}`
    + ` | 守卫重试=${guarded.tries}${guarded.ok ? "" : " 仍失败"}`
    + ` | 重开 ta=${JSON.stringify(ta)} 磁盘=${JSON.stringify(disk)}`;
  console.log(line);
  if (sig !== "ok") {
    stats.details.push({ attempt, sig, diskAfterSave, raw, scenes: guarded.scenes,
      tabs: await tabs(), tree: await clickScene("other.c") });
    console.log("  现场：" + JSON.stringify(stats.details.at(-1), null, 1));
  }
}

console.log("\n---- 汇总 ----");
console.log(JSON.stringify({ ...stats, details: undefined }, null, 1));
writeFileSync(join(ROOT, ".scratch", "code-editor-perf-structural", `flake-forensics-${Date.now()}.json`),
  JSON.stringify(stats, null, 2), "utf8");
c.close();
