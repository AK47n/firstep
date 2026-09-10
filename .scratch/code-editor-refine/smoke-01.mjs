// 冒烟（code-editor-refine/01 未保存退出保护）：真实浏览器验证
// ①脏标签切目录 → 三选模态（消息含计数/路径、三按钮）
// ②取消 → 不切换、编辑保留 ③放弃 → 切换且修改丢弃
// ④保存全部并切换 → 写盘后切换（重开该文件内容一致）
// ⑤beforeunload：脏 → preventDefault；干净 → 不拦截
// 零写库（样例在 .scratch/code-editor-refine/sample-proj）；CDP 9251 + webapp 8000。
//
// 传输层（第十二轮，工单 `code-editor-refine/14-harness-transport-migration.md`）：
// 由 `.scratch/cdp-harness.mjs` 提供，本地不再自带迷你 CDP 客户端——
//   ① `rebuildTab()` 先重建标签页（clean 页 = 无脏缓冲 = 不弹 beforeunload 原生对话框）；
//   ② `connect()` 给**每个命令**加 20s 超时守卫（挂死显式 reject，不静默卡住）并自动应答
//      `Page.javascriptDialogOpening`。
// 切之前的形态（第十一 ~ 第八轮反复出现的假红）：自建 `cdp()` 只有 resolve、没有 reject、
// 没有超时 —— 某个渲染进程侧命令一旦不返回，脚本就停在未落定的 top-level await 上，
// Node 事件循环一空即 **exit 13 且没有任何 FAIL 行**（长连跑劣化 + 对话框挂死两条路径）。
// 切之后：断言失败 = exit 1（有 FAIL 行），传输层/挂死类 = exit 2（带 TRANSPORT 前缀与
// CDP 事件序列），**两类不再混在同一个 exit code 里**。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { connect, pageTarget, rebuildTab } from "../cdp-harness.mjs";

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

// 退出码口径：0 = 全绿；1 = 断言失败（有 FAIL 行）；2 = 传输层/挂死/脚本自身异常。
const EXIT_ASSERT_FAIL = 1;
const EXIT_TRANSPORT = 2;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// 未落定 top-level await 的兜底：以前这类异常就是「无 FAIL 行的 exit 13」，
// 现在带原因显式退出（exit 2），现场一眼能看出是传输层而不是断言。
const bail = (kind) => (e) => {
  console.error(`TRANSPORT(${kind}) ${String((e && e.stack) || e).split("\n").slice(0, 4).join("\n  ")}`);
  process.exit(EXIT_TRANSPORT);
};
process.on("unhandledRejection", bail("unhandledRejection"));
process.on("uncaughtException", bail("uncaughtException"));

const cdpEvents = [];
const dumpEvents = (conn, tag) => {
  const ev = (conn && conn.events) || cdpEvents;
  if (!ev.length) return tag + " 事件序列=（空）";
  return tag + " 事件序列=" + JSON.stringify(ev.map((e) => {
    if (e.method === "Runtime.exceptionThrown") {
      const d = (e.params && e.params.exceptionDetails) || {};
      return [e.method, d.text || (d.exception && d.exception.description) || ""];
    }
    if (e.method === "Page.javascriptDialogOpening") return [e.method, e.params && e.params.type];
    return e.method;
  }).slice(-40));
};

async function main() {
// 前置：CDP 可达（沿用原重试节奏）→ 重建标签页（harness 约定）→ 连接。
let target = null;
for (let i = 0; i < 50 && !target; i++) {
  target = await pageTarget({ port: CDP, pageUrl, anyPage: true });
  if (!target) await sleep(300);
}
if (!target) { console.error("CDP 不可达"); process.exit(EXIT_TRANSPORT); }
await rebuildTab({ port: CDP, pageUrl });
const cdp = await connect({ port: CDP, pageUrl, timeoutMs: 20000, onEvent: (m) => cdpEvents.push(m) });
const { cdp: send, Eval } = cdp;
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await sleep(200);
  }
  return false;
};

await Eval(`window.__smokeMarker = 1; true`);
await send("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await sleep(300);
}
if (!ready) { console.error("页面未就绪"); process.exit(EXIT_TRANSPORT); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
const openDir = (dir) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(dir)}))`);
// 观测器（第十一轮）：只记不改——包装 window.fetch 记 `/api/code/*` 请求（含
// **调用链**，可直接看出是哪一段代码发起的）；另给标签数采样器。用于把
// 「打开成功后被第三方清标签」这类现场钉死（不改产品码、不影响被测时序）。
await Eval(`(() => {
  if (window.__smokeDiag) return true;
  window.__smokeDiag = { fetch: [], tabs: [], clears: [] };
  const orig = window.fetch;
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = (init && init.method) || (input && input.method) || 'GET';
    let dir = null;
    try { dir = JSON.parse(init.body).dir; } catch {}
    const t0 = Date.now();
    const stack = (new Error('smoke')).stack.split('\\n').slice(1, 6).map((s) => s.trim()).join(' < ');
    try {
      const r = await orig(input, init);
      if (url.includes('/api/code/')) {
        window.__smokeDiag.fetch.push({ url: url.replace(location.origin, ''), method, status: r.status,
          ms: Date.now() - t0, dir: dir && dir.split(/[\\\\/]/).pop(), dirFull: dir, stack });
      }
      return r;
    } catch (e) {
      window.__smokeDiag.fetch.push({ url: url.replace(location.origin, ''), method, status: 'ERR(' + e.message + ')',
        ms: Date.now() - t0, dir: dir && dir.split(/[\\\\/]/).pop(), dirFull: dir, stack });
      throw e;
    }
  };
  window.__smokeSampleTabs = async (rounds) => {
    const ed = await import('/js/ui/codeeditor.js');
    let prev = -1;
    const log = [];
    for (let i = 0; i < rounds; i++) {
      const n = ed.openTabPaths().length;
      if (n !== prev) {
        log.push({ t: Date.now(), n,
          label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop(),
          tree: [...document.querySelectorAll('#code-tree [data-code-file]')].map((b) => b.dataset.codeFile) });
        prev = n;
      }
      await new Promise((r) => setTimeout(r, 20));
    }
    return log;
  };
  window.__smokeDiagReset = () => { window.__smokeDiag.fetch = []; window.__smokeDiag.clears = []; return true; };
  return true;
})()`);

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
    await sleep(250);
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
  const wrote = await Eval(`(() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    if (!ta) return false;
    ta.focus();
    ta.value = ${JSON.stringify(text)};
    ta.setSelectionRange(0, 0);
    ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
    return ta.value === ${JSON.stringify(text)};
  })()`);
  if (!wrote) return false;
  // 第十一轮加固：写值成功 ≠ 模型吃到了。窗口化渲染器可能在写入与读取之间
  // 按模型重装窗口（`taWindowApply`）把直写的值盖回去——那时后续断言会以
  // 「磁盘没落盘」的形态红，掩盖真正的原因（老版 diag-save-switch-flake 的
  // `setText` 就是这个盲点：它在未校验返回值的情况下 20 轮里造出 1 次
  // sigStaleDisk 假红，而写盘请求其实从未发出）。故写后**回读模型**：
  // 模型脏（tab.content ≠ savedContent）才算真的改脏。
  return waitFor(`(async () => {
    const m = await import('/js/ui/codeeditor.js');
    return m.dirtyTabPaths().length > 0;
  })()`, 2000);
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
await Eval(`window.__smokeDiagReset()`);
// 决定性取证（第十一轮）：把 codeeditor 模块的 `setCodeDir` **重新绑定**成包装版
// ——ES 模块命名空间对象是冻结的（改不动），但 `import(...)` 每次返回同一对象，
// 而 `codeview.js` 是 `import { setCodeDir }` 的**活绑定**，拿不到包装（第十轮
// 踩过的坑）。本轮不信这一点：直接在**点击时刻**重绑，然后看**谁**真的调了它。
// 判据只在「标签被清」时才需要——setCodeDir 是 tabs=[] 的唯一路径。
await Eval(`(async () => {
  const m = await import('/js/ui/codeeditor.js');
  try {
    Object.defineProperty(m, 'setCodeDir', { value: async (d) => {
      window.__smokeDiag.clears = window.__smokeDiag.clears || [];
      window.__smokeDiag.clears.push({ t: Date.now(), dir: String(d).split(/[\\\\/]/).pop(),
        label: document.getElementById('code-dir-label').textContent.split(/[\\\\/]/).pop(),
        tabs: m.openTabPaths().slice() });
      return window.__smokeRealSetCodeDir(d);
    }, configurable: true });
    return 'rebound';
  } catch (e) { return 'frozen:' + e.message; }
})()`);
await openDir(DIR_B);
await waitFor(`document.getElementById('code-dir-label').textContent === ${JSON.stringify(DIR_B)}
  && !!document.querySelector('#code-tree [data-code-file="other.c"]')`);
const reopened = await openFile("other.c");
// 第十一轮·决定性取证：打开成功后按 20ms 采样标签数 1.2s——第十轮残余的形态是
// 「openFile 返回 true（打开确实成功）而断言时 openTabPaths()=[]」，即**打开成功
// 之后被第三方清标签**（清标签的唯一路径 = setCodeDir ← loadCodeDir）。采样 +
// `/api/code/open` 的调用链一起，能把「谁在什么时候又跑了一次目录加载」钉死。
const tabLog = await Eval(`window.__smokeSampleTabs(60)`);
const openReqs = await Eval(`window.__smokeDiag.fetch.filter((f) => f.url.includes('/api/code/open'))`);
const diagNow = async () => Eval(`(async () => {
  const ed = await import('/js/ui/codeeditor.js');
  return {
    label: document.getElementById('code-dir-label').textContent,
    treeFiles: [...document.querySelectorAll('#code-tree [data-code-file]')].map((b) => b.dataset.codeFile),
    activeTab: (ed.getActiveTab() || {}).path || null,
    openTabs: ed.openTabPaths(),
    dirty: ed.dirtyTabPaths(),
    modal: !!document.querySelector('.code-unsaved-modal'),
    conflict: !!document.querySelector('.code-conflict-overlay'),
    toasts: [...document.querySelectorAll('.toast')].map((x) => x.textContent),
  };
})()`);
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
  // 两者不一致 = 客户端缓存陈旧；一致但非 777 = 保存没落盘）。
  // 第十一轮补齐第九轮要求的取证面：**toast 文案 + 写盘请求状态码**（签名 ②
  // 「保存未落盘」的直接判据 = 没发出 POST / 发出但非 2xx），外加标签采样与
  // 目录重入调用链。
  return v === "int b = 777;\n" && disk === "int b = 777;\n"
    ? true
    : (console.log("   现场：ta=" + JSON.stringify(v) + " 磁盘=" + JSON.stringify(disk)
      + "\n   现场：打开成功=" + reopened + " 标签采样=" + JSON.stringify(tabLog)
      + "\n   现场：/api/code/open 调用链=" + JSON.stringify(openReqs, null, 1)
      + "\n   现场：写盘请求=" + JSON.stringify(await Eval(
        `window.__smokeDiag.fetch.filter((f) => f.url.includes('/api/code/save'))`))
      + "\n   现场：现状=" + JSON.stringify(await diagNow(), null, 1)),
      false);
})());
check("5b-supp 打开成功后标签未被第三方清空（第十轮残余签名的机器判据）",
  reopened && tabLog.length > 0 && tabLog[tabLog.length - 1].n > 0);

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
if (cdpEvents.length) console.log("   " + dumpEvents(cdp, "[事件]"));
if (cdp.dialogsAccepted) console.log(`   [对话框自动应答] ${cdp.dialogsAccepted} 次`);
cdp.close();
process.exit(failed ? EXIT_ASSERT_FAIL : 0);
}

// 顶层只留一个 await：任何「未落定」都会走上面的 unhandledRejection 兜底（exit 2），
// 不再是「无 FAIL 行的 exit 13」。
try {
  await main();
} catch (e) {
  console.error(`TRANSPORT(${String((e && e.message) || e).slice(0, 200)})`);
  console.error("   " + dumpEvents(null, "[事件]"));
  process.exit(EXIT_TRANSPORT);
}
