// ux-polish-02 回归走查探针：合并 01-06/08 关键断言 + 截图 + 零 LLM 请求确认。
// 依赖：webapp 8000（已重启带 mtime）+ Chrome 9251。
import { writeFileSync } from "node:fs";
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const FAKE_DIR = "C:/Users/luoji/AppData/Local/Temp/dsh-ux-t04-proj";
const PLAN_PATH = FAKE_DIR.replace(/\//g, "\\") + "\\.contest_tasks.json";
const plan = (tasks) => writeFileSync(PLAN_PATH, JSON.stringify({ version: 1, generated_at: "2026-08-30T00:00:00", tasks, score_points: [] }), "utf8");

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
const jsErrors = [];
let llmCalls = 0;
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    jsErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
  }
  if (msg.method === "Network.requestWillBeSent") {
    const url = msg.params.request.url;
    if (url.includes("/api/recommend") || url.includes("/api/tasks/execute") || url.includes("/api/topics/split")) llmCalls++;
  }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const shot = async (name) => {
  const s = await cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync(new URL("./shot-" + name + ".png", import.meta.url), Buffer.from(s.result.data, "base64"));
};

await cdp("Runtime.enable");
await cdp("Page.enable");
await cdp("Network.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
await cdp("Network.clearBrowserCache");

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const nav = async (tab) => {
  await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find((x) => x.dataset.tab === '${tab}'); if (b) b.click(); })()`);
  await new Promise((r) => setTimeout(r, 400));
};
const noHOverflow = () => Eval(`document.documentElement.scrollWidth <= window.innerWidth + 1`);

const token = "np=" + Date.now();
await cdp("Page.navigate", { url: pageUrl + "?" + token });
for (let i = 0; i < 120; i++) {
  try {
    const st = await Eval(`({ href: location.href, rs: document.readyState, ov: !!document.getElementById('gen-overview') })`);
    if (st.href.includes(token) && st.rs === "complete" && st.ov) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 250));
}

// ── 01 完成态：初始步骤5/7 未完成 ──
const s5 = await Eval(`(() => {
  const card = [...document.querySelectorAll('.gen-steps > .card')].find((c) => {
    const no = c.querySelector('.step-no'); return no && no.textContent.trim() === '5';
  });
  const badge = card.querySelector('.card-step-status');
  return { done: card.classList.contains('done'), badge: badge ? badge.textContent : '' };
})()`);
check("01: 初始步骤5未标完成", !s5.done && s5.badge === "", JSON.stringify(s5));

// ── 02 折叠记忆：折叠卡3 → 刷新保持 → 清理 ──
await Eval(`localStorage.removeItem('firstep.genCardCollapse.v1')`);
await Eval(`(() => { const c = [...document.querySelectorAll('#tab-generate .gen-steps > .card')].find((c) => { const n = c.querySelector('.step-no'); return n && n.textContent.trim() === '3'; }); c.querySelector('h2').click(); })()`);
await new Promise((r) => setTimeout(r, 200));
check("02: 折叠写入记忆", await Eval(`(localStorage.getItem('firstep.genCardCollapse.v1') || '').includes('"3":true')`));
const token2 = "np=" + Date.now();
await cdp("Page.navigate", { url: pageUrl + "?" + token2 });
for (let i = 0; i < 120; i++) {
  const st = await Eval(`({ href: location.href, rs: document.readyState, ov: !!document.getElementById('gen-overview') })`);
  if (st.href.includes(token2) && st.rs === "complete" && st.ov) break;
  await new Promise((r) => setTimeout(r, 250));
}
check("02: 刷新后折叠保持", await Eval(`[...document.querySelectorAll('#tab-generate .gen-steps > .card.collapsed')].some((c) => c.querySelector('.step-no') && c.querySelector('.step-no').textContent.trim() === '3')`));
await Eval(`localStorage.removeItem('firstep.genCardCollapse.v1')`);

// ── 03 设置横幅定位：折叠 AI API 卡 → 点击去设置 → 展开+聚焦 ──
await Eval(`(() => { const card = document.querySelector('[data-collapse-id="llm-api"]'); if (!card.classList.contains('collapsed')) card.querySelector('.card-collapse').click(); })()`);
await Eval(`document.getElementById('gen-banner').classList.remove('hidden')`);
await Eval(`document.getElementById('btn-banner-goto-settings').click()`);
await new Promise((r) => setTimeout(r, 400));
const st3 = await Eval(`({
  active: document.getElementById('tab-settings').classList.contains('active'),
  collapsed: document.querySelector('[data-collapse-id="llm-api"]').classList.contains('collapsed'),
  focused: document.activeElement && document.activeElement.id === 'set-api-key',
})`);
check("03: 横幅定位展开+聚焦", st3.active && !st3.collapsed && st3.focused, JSON.stringify(st3));

// ── 04 去任务推进自动加载（临时工程）──
plan([
  { id: "t1", title: "失败卡", description: "仍是红的", status: "failed", verify: "compile" },
  { id: "t2", title: "待做卡", description: "等跳过", status: "pending", verify: "compile" },
  { id: "t3", title: "执行中卡", description: "进行中", status: "doing", verify: "compile" },
]);
await Eval(`document.getElementById('res-dir').textContent = ${JSON.stringify(FAKE_DIR)}`);
await Eval(`(async () => { const m = await import('/js/ui/goto-tasks.js'); await m.goTaskProgress(); return true; })()`);
await new Promise((r) => setTimeout(r, 900));
const st4 = await Eval(`({
  tasksActive: document.querySelector('#revise-tabs .revise-tab[data-tab="tasks"]').classList.contains('active'),
  dir: document.getElementById('revise-dir-input').value,
  status: document.getElementById('revise-load-status').textContent,
})`);
check("04: 去任务推进自动加载完成", st4.tasksActive && st4.dir === FAKE_DIR && st4.status === "加载完成", JSON.stringify(st4));

// ── 05 failed 无确认通过 + 跳过确认 ──
const st5 = await Eval(`(() => {
  const c = document.querySelector('.task-card[data-task-id="t1"]');
  return { hasMark: !!c.querySelector('.btn-task-mark'), hasRun: !!c.querySelector('.btn-task-run'), hasRevert: !!c.querySelector('.btn-task-revert') };
})()`);
check("05: failed 卡无「确认通过」", !st5.hasMark && st5.hasRun && st5.hasRevert, JSON.stringify(st5));
await Eval(`document.querySelector('.task-card[data-task-id="t2"] .btn-task-skip').click()`);
await new Promise((r) => setTimeout(r, 200));
check("05: 跳过弹确认", await Eval(`(document.querySelector('.ref-files-overlay') || {}).textContent ? true : false`));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]').click()`);

// ── 06 doing 阶段槽 ──
const st6 = await Eval(`(() => {
  const c = document.querySelector('.task-card[data-task-id="t3"]');
  return { phase: !!c.querySelector('.task-phase'), spinner: !!c.querySelector('.task-spinner') };
})()`);
check("06: doing 卡阶段槽", st6.phase && st6.spinner, JSON.stringify(st6));

// ── 08 库页 mtime 排序（模块库）──
await nav("library");
check("08: 模块库 mtime 选项存在", await Eval(`Array.from(document.getElementById('lib-sort').options).some((o) => o.value === 'mtime')`));
await Eval(`document.getElementById('lib-sort').value = 'mtime'; document.getElementById('lib-sort').dispatchEvent(new Event('change', { bubbles: true }))`);
await new Promise((r) => setTimeout(r, 200));
check("08: mtime 自动降序", (await Eval(`document.getElementById('lib-sort-dir').textContent`)).includes("降序"));

// ── 溢出与 JS 异常（八个页签逐一）──
let overflowAny = false;
for (const tab of ["generate", "settings", "library", "topic", "reference", "pdf", "master", "guide"]) {
  await nav(tab);
  if (!(await noHOverflow())) overflowAny = true;
}
check("九个页签无横向溢出(1280)", overflowAny === false);
check("无未捕获 JS 异常", jsErrors.length === 0, jsErrors.join(" | ").slice(0, 300));
check("零真实 LLM 请求（recommend/execute/split）", llmCalls === 0, "llmCalls=" + llmCalls);

// ── 截图（生成页顶部 / 任务推进 / 模块库）──
await nav("generate");
await new Promise((r) => setTimeout(r, 300));
await shot("t09-generate");
await nav("library");
await new Promise((r) => setTimeout(r, 300));
await shot("t09-library");
await Eval(`document.getElementById('res-dir').textContent = ${JSON.stringify(FAKE_DIR)}`);
await Eval(`(async () => { const m = await import('/js/ui/goto-tasks.js'); await m.goTaskProgress(); return true; })()`);
await new Promise((r) => setTimeout(r, 900));
await shot("t09-tasks");

console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
process.exit(failed ? 1 : 0);
