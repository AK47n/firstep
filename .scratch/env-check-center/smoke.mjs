// 冒烟（工单 env-check-center/01）：设置页「环境体检」卡 → 一键体检 →
// 静态行渲染 → 文本/视觉双通道终态（真实环境允许「未配置/失败」= 终态）。
// 零依赖：node 内置 fetch + WebSocket 直连 Edge CDP（9231）；webapp 8000 提供真实 /api/*。
const CDP = 9231;

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
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
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

let ready = false;
// 重新加载页面：webapp 静态文件实时更新，但浏览器内存中的 JS 需刷新才换新。
// 打标记防竞态：旧文档 readyState 早已 complete，仅靠 readyState 会被旧文档
// 立即满足——等「旧标记消失」（新文档）才继续。
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('btn-env-check')
      && typeof state !== 'undefined' && state`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪（btn-env-check 不存在）"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- 切设置 tab，强制展开 env-check 卡 ----
await Eval(`document.querySelector('[data-tab="settings"]').click()`);
await sleep(300);
await Eval(`(() => {
  const card = document.querySelector('[data-collapse-id="env-check"]');
  if (card) card.classList.remove('collapsed');
  return !!card;
})()`);
await sleep(200);

const cardInfo = await Eval(`(() => {
  const card = document.querySelector('[data-collapse-id="env-check"]');
  return {
    exists: !!card,
    visible: !!card && card.offsetParent !== null,
    btnText: (document.getElementById('btn-env-check') || {}).textContent,
    resultsEmpty: (document.getElementById('env-check-results') || {}).innerHTML === "",
  };
})()`);
check("环境体检卡存在且可见", cardInfo.exists && cardInfo.visible);
check("一键体检按钮就位", (cardInfo.btnText || "").includes("一键体检"), "text=" + cardInfo.btnText);
check("初始结果容器为空", cardInfo.resultsEmpty);

// ---- 点一键体检：先等静态行渲染，再等双通道终态 ----
await Eval(`document.getElementById('btn-env-check').click()`);

let staticDone = false;
for (let i = 0; i < 40 && !staticDone; i++) {
  staticDone = await Eval(`!!document.querySelector('[data-env-row="api"]')
    && !!document.querySelector('[data-env-row="module-library"]')`);
  if (!staticDone) await sleep(250);
}
check("静态行渲染（api + module-library）", staticDone);

const staticRows = await Eval(`(() => {
  const rows = document.querySelectorAll('#env-check-results .env-row');
  const keys = [...document.querySelectorAll('#env-check-results [data-env-row]')].map((r) => r.dataset.envRow);
  return { count: rows.length, keys };
})()`);
check("静态行数>0", staticRows.count > 0, "count=" + staticRows.count);
check("含文本/视觉通道行", staticRows.keys.includes("llm-text") && staticRows.keys.includes("llm-vision"),
  "keys=" + staticRows.keys.join(","));
const pendingCh = await Eval(`(() => {
  const rows = [...document.querySelectorAll('#env-check-results .env-row')];
  const text = rows.find((r) => r.dataset.envRow === 'llm-text');
  const vis = rows.find((r) => r.dataset.envRow === 'llm-vision');
  return { textPending: !!(text && text.textContent.includes('待检查')), visPending: !!(vis && vis.textContent.includes('待检查')) };
})()`);
check("双通道初始「待检查」态", pendingCh.textPending && pendingCh.visPending);

let terminal = false;
let terminalInfo = null;
for (let i = 0; i < 120 && !terminal; i++) {
  terminalInfo = await Eval(`(() => {
    const rows = [...document.querySelectorAll('#env-check-results .env-row')];
    const text = rows.find((r) => r.dataset.envRow === 'llm-text');
    const vis = rows.find((r) => r.dataset.envRow === 'llm-vision');
    const done = (r) => {
      if (!r) return false;
      const b = r.querySelector('.env-badge');
      const t = r.textContent;
      return !t.includes('待检查') && b && (b.classList.contains('env-ok') || b.classList.contains('env-err'));
    };
    if (done(text) && done(vis)) {
      return {
        textBadge: text.querySelector('.env-badge').className,
        textText: text.textContent.slice(0, 80),
        visBadge: vis.querySelector('.env-badge').className,
        visText: vis.textContent.slice(0, 80),
      };
    }
    return null;
  })()`);
  if (terminalInfo) terminal = true; else await sleep(500);
}
check("文本通道终态（✓ 或 ✕）", terminal && /env-(ok|err)/.test(terminalInfo.textBadge), "text=" + (terminal && terminalInfo.textText));
check("视觉通道终态（✓ 或 ✕）", terminal && /env-(ok|err)/.test(terminalInfo.visBadge), "vis=" + (terminal && terminalInfo.visText));

// ---- 按钮恢复 + 崩溃检查 ----
const after = await Eval(`(() => {
  const btn = document.getElementById('btn-env-check');
  return { btnText: btn.textContent, btnDisabled: btn.disabled,
    hasErrorRow: !!document.querySelector('#env-check-results .error') };
})()`);
check("体检完成按钮恢复可用", after.btnText.includes("一键体检") && !after.btnDisabled, "text=" + after.btnText);
check("未出现整块错误行（双通道失败是行内失败非请求失败）", !after.hasErrorRow);

console.log(failed === 0 ? "SMOKE ALL PASS" : "SMOKE FAILED: " + failed);
process.exit(failed === 0 ? 0 : 1);
