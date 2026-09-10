// 冒烟（code-editor-refine/01 未保存退出保护）：真实浏览器验证
// ①脏标签切目录 → 三选模态（消息含计数/路径、三按钮）
// ②取消 → 不切换、编辑保留 ③放弃 → 切换且修改丢弃
// ④保存全部并切换 → 写盘后切换（重开该文件内容一致）
// ⑤beforeunload：脏 → preventDefault；干净 → 不拦截
// 零写库（样例在 .scratch/code-editor-refine/sample-proj）；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const DIR_A = join(OUT, "sample-proj", "a");
const DIR_B = join(OUT, "sample-proj", "b");
mkdirSync(DIR_A, { recursive: true });
mkdirSync(DIR_B, { recursive: true });
writeFileSync(join(DIR_A, "main.c"), "int a = 1;\n");
writeFileSync(join(DIR_B, "other.c"), "int b = 2;\n");

const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
const openDir = (dir) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(dir)}))`);
// openFile(name)：点树节点打开文件。
// 口径修订（2026-09-09 第九轮实跑暴露的偶发红，**基线（stash 产品改动）同样 2/8 复现**
// → 与本轮产品改动无关的既有脚本竞态）：切目录后 #code-tree 会被 loadCodeDir 清成
// 「加载中…」再异步重渲染，`waitFor(节点存在)` 可能被**上一次目录留下的同名节点**
// 满足，两次 Eval 之间的清树使 click 落在已移除节点上（`?.click()` 静默 no-op）→
// 没有活动标签、编辑器空白（实测现场：ta=null / 标签=[]），场景 5b 因等不到 ta 值而假红。
// 修法两层：① 点前等节点**稳定**（连续两次轮询都在场，避开"清树前一瞬"）；
// ② 打开失败即重试（最多 3 次，每次等 1.5s 看是否成为活动标签）——与第八轮
// smoke-02「等 b.c 成为活动标签」同一姿势。
const openFile = async (name) => {
  for (let i = 0; i < 3; i++) {
    await waitFor(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')`, 8000);
    await new Promise((r) => setTimeout(r, 250));
    const stable = await Eval(`!!document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')`);
    if (!stable) continue;
    await Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
    // 就绪判据（第十轮加强）：点完可能有两种落空——
    //   ① 点击落在被移除的节点上（清树瞬间）→ 什么都没发生；
    //   ② 点击命中、但文件读盘未回（本机端点 ≈500ms 量级）→ 活动标签要等一会儿。
    // 原判据只有 1.5s 窗口，①/② 都可能不够。改为「先等树脱离『加载中…』占位，
    // 再等成为活动标签」，单次窗口放到 3s（总预算仍 3 次尝试）。
    await waitFor(`!document.querySelector('#code-tree > .muted')`, 3000);
    const ok = await waitFor(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab()?.path === ${JSON.stringify(name)})`, 3000);
    if (ok) return true;
  }
  return false;
};
// setText(text)：直写 textarea + 派发 input。
// 第十轮加固：原来 `ta.focus()` 对 null 直接抛 TypeError —— 而**调用点是 fire-and-forget**
// （`await setText(...)` 的结果在脚本主流程里被吞掉），异常只让「后续断言」连锁变红，
// 真正的失败点被掩盖（实测现场：某轮 5a 报「label=b、ta 仍脏、磁盘未落盘」，其实是
// 更早一步的文件没打开 → setText 抛错 → 整段后续流程在错的状态上继续跑）。
// 现在：先等 textarea 到场（最多 5s），再写值，并**回报是否写成**；调用点断言它。
const setText = async (text) => {
  const appeared = await waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 5000);
  if (!appeared) return false;
  return Eval(`(() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    ta.focus();
    ta.value = ${JSON.stringify(text)};
    ta.setSelectionRange(0, 0);
    ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
    return ta.value === ${JSON.stringify(text)};
  })()`);
};
const label = () => Eval(`document.getElementById('code-dir-label').textContent`);
const modalOpen = () => Eval(`!!document.querySelector('.code-unsaved-modal')`);
const taValue = () => Eval(`document.querySelector('#code-viewer .code-ta')?.value ?? null`);
const clickAction = (act) => Eval(`document.querySelector('.code-unsaved-modal [data-unsaved-action=${JSON.stringify(act)}]')?.click()`);
const dbg = (tag) => Eval(`(() => ({
  tag: ${JSON.stringify(tag)},
  label: document.getElementById('code-dir-label').textContent,
  modal: !!document.querySelector('.code-unsaved-modal'),
  conflict: !!document.querySelector('.code-conflict-overlay'),
  ta: document.querySelector('#code-viewer .code-ta')?.value ?? null,
}))()`).then((d) => { console.log(JSON.stringify(d)); return d; });

// ---- 场景 1：打开 A，改脏，切 B → 三选模态 ----
await openDir(DIR_A);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
check("1-pre 打开 main.c（树点击命中且成为活动标签）", await openFile("main.c"));
check("1-pre2 编辑器 textarea 到场", await waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 5000));
await setText("int a = 999;\n");
check("1a 修改为脏（ta 值生效）", await taValue() === "int a = 999;\n");
check("1b beforeunload：脏 → 拦截", await Eval(`(() => {
  const ev = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(ev);
  return ev.defaultPrevented;
})()`));

await openDir(DIR_B);
check("2a 弹三选模态", await waitFor(`!!document.querySelector('.code-unsaved-modal')`));
check("2b 消息含计数与路径", await Eval(`document.querySelector('.code-unsaved-modal .confirm-message').textContent.includes('1 个文件未保存')
  && document.querySelector('.code-unsaved-modal .confirm-message').textContent.includes('main.c')`));
check("2c 三按钮齐", await Eval(`['save','discard','cancel'].every((a) => !!document.querySelector('.code-unsaved-modal [data-unsaved-action="' + a + '"]'))`));

// ---- 场景 3：取消 → 不切换、编辑保留 ----
await clickAction("cancel");
await waitFor(`!document.querySelector('.code-unsaved-modal')`);
check("3a 取消后仍为 A", await label() === DIR_A);
check("3b 编辑保留且脏", await taValue() === "int a = 999;\n");

// ---- 场景 4：放弃修改并切换 ----
await openDir(DIR_B);
await waitFor(`!!document.querySelector('.code-unsaved-modal')`);
await clickAction("discard");
await waitFor(`!document.querySelector('.code-unsaved-modal') && document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_B)}`);
check("4a 放弃后为 B", await label() === DIR_B);
check("4b 标签已清（丢弃）", await taValue() === null);

// ---- 场景 5：保存全部并切换 → 写盘 ----
await waitFor(`!!document.querySelector('#code-tree [data-code-file="other.c"]')`);
check("5-pre 打开 other.c（树点击命中且成为活动标签）", await openFile("other.c"));
check("5-pre2 编辑器 textarea 到场", await waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 5000));
check("5-pre3 改脏已写入编辑器", await setText("int b = 777;\n"));
await openDir(DIR_A);
check("5-pre4 切 A 弹三选模态", await waitFor(`!!document.querySelector('.code-unsaved-modal')`, 8000));
await clickAction("save");
check("5-pre5 点「保存全部」后目录切到 A（防「点了没反应」掩盖成 5a/5b 红）",
  await waitFor(`!document.querySelector('.code-unsaved-modal')
    && document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_A)}`, 8000));
await dbg("after-save-switch");
check("5a 保存后为 A", await label() === DIR_A);
// 重开 B 验证写盘（等 ta 内容 = 保存值，防读盘异步）
await openDir(DIR_B);
await waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_B)}
  && !!document.querySelector('#code-tree [data-code-file="other.c"]')`);
const reopened = await openFile("other.c");
// 第十轮·决定性取证：这一支在批内偶发红（6 轮里 2 次，**总是卡在这里**），
// 且落盘/切目录全好（5-pre5 绿、磁盘已 777）——即「点击丢失」而非保存问题。
// 失败时把**树的实况 + 端点实况 + 活动标签**一起打出来（判定三种可能：
// ① 树停在旧目录清单；② 树是 B 但点击丢失；③ 端点本身没回 other.c）。
if (!reopened) {
  const s = await Eval(`(async () => {
    const box = document.getElementById('code-tree');
    const api = await fetch('/api/code/open', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dir: ${JSON.stringify(DIR_B)} }) }).then((r) => r.json()).catch((e) => ({ err: String(e) }));
    const ed = await import('/js/ui/codeeditor.js');
    return {
      label: document.getElementById('code-dir-label').textContent,
      treeText: box.textContent.trim().slice(0, 60),
      treeFiles: [...box.querySelectorAll('[data-code-file]')].map((b) => b.dataset.codeFile),
      activeTab: (ed.getActiveTab() || {}).path || null,
      openTabs: ed.openTabPaths(),
      modal: !!document.querySelector('.code-unsaved-modal'),
      conflict: !!document.querySelector('.code-conflict-overlay'),
      toasts: [...document.querySelectorAll('.toast')].map((x) => x.textContent),
      apiFiles: (api.files || []).map((f) => f.path), apiErr: api.err || null,
    };
  })()`);
  console.log("   现场（重开 B 失败）：" + JSON.stringify(s, null, 1));
}
await waitFor(`document.querySelector('#code-viewer .code-ta')?.value === "int b = 777;\\n"`);
check("5b B 磁盘内容已含修改", await (async () => {
  const v = await taValue();
  const disk = await Eval(`fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(DIR_B)})
    + '&path=' + encodeURIComponent('other.c')).then((r) => r.json()).then((j) => j.content).catch(() => '(读盘失败)')`);
  // 失败时把「编辑器看到的」与「磁盘上的」一起打出来（第九轮排查用：
  // 两者不一致 = 客户端缓存陈旧；一致但非 777 = 保存没落盘）
  return v === "int b = 777;\n" && disk === "int b = 777;\n"
    ? true
    : (console.log("   现场：ta=" + JSON.stringify(v) + " 磁盘=" + JSON.stringify(disk)
      + " 标签=" + JSON.stringify(await Eval(`(async () => (await import('/js/ui/codeeditor.js')).openTabPaths())()`))),
      false);
})());

// ---- 场景 6：干净态 beforeunload 不拦截 ----
await openDir(DIR_A);   // 无脏 → 直通（顺带验证无脏切换不弹窗）
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
check("6a 无脏切目录不弹窗", await Eval(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_A)}
  && !document.querySelector('.code-unsaved-modal')`));
check("6b beforeunload：干净 → 不拦截", await Eval(`(() => {
  const ev = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(ev);
  return !ev.defaultPrevented;
})()`));

console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
