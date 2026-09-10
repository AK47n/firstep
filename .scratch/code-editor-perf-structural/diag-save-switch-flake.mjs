// 取证脚本（第十/十一轮，工单 code-editor-refine/12 场景 5 偶发定性）：
// 「保存全部并切换 → 重开该文件内容一致」的偶发，按**签名**分开抓，各自带现场。
//
// 第十轮结论（已修）：签名 ①（label=b 而树 = 旧目录清单）= 真产品缺陷 `loadCodeDir`
// 目录加载竞态 → `codeDirSeq` 序号守卫。修完仍剩 ≈1/3 的偶发，失败点收窄到唯一一步
// （场景 5 末尾「切回 B → 重开 other.c → 断言内容 = 777」），形态 = `openFile` 返回
// true（打开确实成功）而断言时 `openTabPaths() = []`、`ta = null`。
//
// 本轮（第十一轮）判据与取证手段：
//   - 每个签名**独立计数**，且「守卫重试救回来」不再算签名（第十轮口径错误：
//     只要裸点丢一次就记 sigNoTab，即便守卫救回、内容比对全好）；
//   - 签名 ② 也打印 toast 文案 + `/api/code/file` 与 `/api/code/save` 的状态码
//     （第九轮要求）；
//   - 目录重入取证**不改产品码**：`loadCodeDir` 每次都会先走
//     `setCodeDir(dir)`，而 setCodeDir 的唯一可观测外部副作用里最先发生的是
//     `/api/disk/*` 探测（probeDiskBaseline → POST /api/code/open）。
//     这里垫 window.fetch，对每次 `/api/code/open` 记 **Error().stack**
//     （= 调用链，能直接看出是哪个调用点发起的）——比改模块命名空间对象可靠
//     （`codeview.js` 里是 import 活绑定，wrap 模块对象拿不到调用）。
//   - 标签生命周期：`openFile` 成功后按 20ms 采样 `openTabPaths()`，记录
//     「标签从有到无」的时刻与当时 label / 树实况。
//
// 用法：node .scratch/code-editor-perf-structural/diag-save-switch-flake.mjs [轮数] [端口]
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
const PORT = Number(process.argv[3] || 9251);

await rebuildTab({ port: PORT, pageUrl: "http://127.0.0.1:8000/", settleMs: 2000 });
const c = await connect({ port: PORT, pageUrl: "http://127.0.0.1:8000/" });
await c.cdp("Page.enable");
await c.cdp("Runtime.enable");   // 未捕获的 promise 拒绝上报（第十轮下一轮建议）
const Eval = (e) => c.Eval(e);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 页面侧：fetch 观测（调用链 + 状态码）+ 标签采样器。
// 注意：观测器**只记不改**——不改请求、不改响应，避免自身影响被测时序。
const INSTALL = `(() => {
  if (window.__diagInstalled) return true;
  window.__diagInstalled = true;
  window.__diagFetch = [];       // {url, method, status, ms, dir, stack}
  window.__diagTabLog = [];      // 标签数变化 {t, n, label}
  const orig = window.fetch;
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = (init && init.method) || (input && input.method) || 'GET';
    let dir = null;
    try { if (init && typeof init.body === 'string') dir = JSON.parse(init.body).dir || null; } catch {}
    const t0 = Date.now();
    // 调用链在发请求**之前**取（await 之后栈就断了）
    const stack = (new Error('diag')).stack.split('\\n').slice(1, 7).map((s) => s.trim()).join(' < ');
    try {
      const r = await orig(input, init);
      if (/\\/api\\/code\\/|\\/api\\/disk\\//.test(url)) {
        window.__diagFetch.push({ url: url.replace(location.origin, ''), method, status: r.status,
          ms: Date.now() - t0, dir, stack });
      }
      return r;
    } catch (e) {
      window.__diagFetch.push({ url: url.replace(location.origin, ''), method, status: 'ERR(' + e.message + ')',
        ms: Date.now() - t0, dir, stack });
      throw e;
    }
  };
  window.__diagSampleTabs = async (rounds) => {
    const ed = await import('/js/ui/codeeditor.js');
    let prev = -1;
    for (let i = 0; i < rounds; i++) {
      const n = ed.openTabPaths().length;
      if (n !== prev) {
        window.__diagTabLog.push({ t: Date.now(), n,
          label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop() });
        prev = n;
      }
      await new Promise((r) => setTimeout(r, 20));
    }
    return window.__diagTabLog.slice();
  };
  window.__diagReset = () => { window.__diagFetch = []; window.__diagTabLog = []; return true; };
  return true;
})()`;

const openDir = (d) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(d)}))`);
const setText = (t) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return false;
  ta.focus(); ta.value = ${JSON.stringify(t)}; ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true })); return ta.value === ${JSON.stringify(t)};
})()`);
const taValue = () => Eval(`document.querySelector('#code-viewer .code-ta')?.value ?? null`);
const tabs = () => Eval(`(async () => (await import('/js/ui/codeeditor.js')).openTabPaths())()`);
const toasts = () => Eval(`[...document.querySelectorAll('.toast')].map((x) => x.textContent)`);
// 磁盘判据（直接读盘，不依赖重开）+ 该文件的保存/读取请求状态码
const diskOf = (dir, path) => Eval(`fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(dir)})
  + '&path=' + encodeURIComponent(${JSON.stringify(path)})).then((r) => r.json()).then((j) => j.content).catch(() => '(读盘失败)')`);
const clickScene = (name) => Eval(`(() => {
  const box = document.getElementById('code-tree');
  const n = box.querySelector('[data-code-file=${JSON.stringify(name)}]');
  return { nodePresent: !!n, nodeConnected: !!(n && n.isConnected),
    treeText: box.textContent.trim().slice(0, 24),
    treeFiles: [...box.querySelectorAll('[data-code-file]')].map((b) => b.dataset.codeFile),
    label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop() };
})()`);
// openCodeReqs()：本轮核心取证——每次 /api/code/open 的调用链（谁发起的）
const openCodeReqs = () => Eval(`(window.__diagFetch || []).filter((f) => f.url.includes('/api/code/open'))`);
// saveReqs()：本轮第二项取证（第九轮要求）——切目录前的保存是否真的发出了写盘请求、
// 状态码是什么。签名 ②（磁盘未落盘）的直接判据：**没发出 POST** vs **发出但非 2xx**。
const saveReqs = () => Eval(`(window.__diagFetch || []).filter((f) => f.url.includes('/api/code/save'))`);

const openFileG = async (name) => {
  const scenes = [];
  for (let i = 0; i < 3; i++) {
    await c.waitFor(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')`, 8000);
    await sleep(250);
    const stable = await Eval(`!!document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')`);
    if (!stable) { scenes.push({ try: i + 1, skipped: "节点不稳定" }); continue; }
    scenes.push(Object.assign({ try: i + 1 }, await clickScene(name)));
    await Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
    const ok = await c.waitFor(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab()?.path === ${JSON.stringify(name)})`, 3000);
    if (ok) return { ok: true, tries: i + 1, scenes };
  }
  return { ok: false, tries: 3, scenes };
};

const openFileRaw = async (name) => {
  await c.waitFor(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')`, 8000);
  const scene = await clickScene(name);
  await Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
  const ok = await c.waitFor(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab()?.path === ${JSON.stringify(name)})`, 3000);
  return { ok, scene };
};

const stats = {
  rounds: ROUNDS, ok: 0,
  // 签名表（各自独立、互不掩盖）
  sigNoTab: 0,          // 重开后始终没有活动标签（含守卫重试也失败）
  sigDropped: 0,        // 打开成功（openFile 返回 true）之后标签被清空 —— 第十轮残余
  sigStaleDisk: 0,      // 编辑器有 777 而磁盘不是（保存未落盘）
  rawLost: 0,           // 裸点丢（守卫救回不算签名）
  guardSaved: 0,
  details: [],
};

for (let attempt = 1; attempt <= ROUNDS; attempt++) {
  writeFileSync(join(DIR_A, "main.c"), "int a = 1;\n");
  writeFileSync(join(DIR_B, "other.c"), "int b = 2;\n");
  await Eval(`window.__smokeMarker = 1; true`);
  await c.cdp("Page.reload", { ignoreCache: true });
  await c.waitFor(`document.readyState === 'complete'`, 15000);
  await Eval(INSTALL);
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
  // —— 场景 5 本体：保存全部并切换 ——
  await openDir(DIR_A);
  await c.waitFor(`!!document.querySelector('.code-unsaved-modal')`, 10000);
  await Eval(`document.querySelector('.code-unsaved-modal [data-unsaved-action="save"]')?.click()`);
  await c.waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_A)}`, 15000);
  // 保存请求取证（签名 ② 直接判据）：点「保存全部」前后各自有哪些写盘请求
  const saveReqLog = await saveReqs();
  const diskAfterSave = await diskOf(DIR_B, "other.c");
  // —— 重开 B/other.c ——（本轮观测起点：清空 fetch/tab 日志）
  await Eval(`window.__diagReset()`);
  await openDir(DIR_B);
  await c.waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_B)}`, 15000);
  const raw = await openFileRaw("other.c");
  const guarded = raw.ok ? { ok: true, tries: 1 } : await openFileG("other.c");
  if (!raw.ok) stats.rawLost++;
  if (!raw.ok && guarded.ok) stats.guardSaved++;

  // 采样标签生命周期：打开成功之后 1.2s 内，标签是否被清空
  const tabLog = guarded.ok ? await Eval(`window.__diagSampleTabs(60)`) : [];
  const tabsNow = await tabs();
  const ta = await taValue();
  const disk = await diskOf(DIR_B, "other.c");

  let sig = "ok";
  if (!guarded.ok) sig = "sigNoTab";
  else if (tabsNow.length === 0) sig = "sigDropped";        // 打开成功 → 标签被第三方清空
  else if (ta !== "int b = 777;\n" && disk !== "int b = 777;\n") sig = "sigStaleDisk";
  else if (ta !== "int b = 777;\n") sig = "sigEditorStale"; // 磁盘对、编辑器不对（客户端缓存）
  if (sig !== "ok") stats[sig]++; else stats.ok++;

  const line = `attempt ${attempt}: ${sig === "ok" ? "OK" : sig.toUpperCase()}`
    + ` | 落盘后磁盘=${JSON.stringify(diskAfterSave)}`
    + ` | 写盘请求=${saveReqLog.length ? saveReqLog.map((r) => `${r.method} ${r.status}(${r.ms}ms)`).join(",") : "无"}`
    + ` | 裸点=${raw.ok ? "命中" : "点丢"}${raw.ok ? "" : `(现场 ${JSON.stringify(raw.scene)})`}`
    + ` | 守卫=${guarded.ok ? `ok(${guarded.tries})` : "仍失败"}`
    + ` | 重开 ta=${JSON.stringify(ta)} 标签数=${tabsNow.length} 磁盘=${JSON.stringify(disk)}`;
  console.log(line);
  if (sig !== "ok") {
    const openReqs = await openCodeReqs();
    const detail = {
      attempt, sig, diskAfterSave, saveReqLog, raw, scenes: guarded.scenes,
      tabLog, tabsNow, ta, disk,
      toasts: await toasts(),
      tree: await clickScene("other.c"),
      // 目录重入取证：每次 /api/code/open 的调用链（谁发起的）
      openReqs: openReqs.map((r) => ({ url: r.url, method: r.method, ms: r.ms, dir: r.dir, stack: r.stack })),
    };
    stats.details.push(detail);
    console.log("  现场：" + JSON.stringify(detail, null, 1));
  }
}

console.log("\n---- 汇总 ----");
console.log(JSON.stringify({ ...stats, details: undefined }, null, 1));
writeFileSync(join(ROOT, ".scratch", "code-editor-perf-structural", `flake-forensics-${Date.now()}.json`),
  JSON.stringify(stats, null, 2), "utf8");
c.close();
