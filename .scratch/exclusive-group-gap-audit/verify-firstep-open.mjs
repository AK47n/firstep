// 真机复现：干净 Chrome（独立 user-data-dir）打开 firstep，看控制台错误 + 关键 DOM 是否渲染。
// 用途：验证「一打开就卡死」是否已修（判据 = 无 SyntaxError + 模块网格有卡）。
// 用法：node .scratch/exclusive-group-gap-audit/verify-firstep-open.mjs [url] [port]
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const URL_ = process.argv[2] || "http://127.0.0.1:8000/";
const PORT = Number(process.argv[3] || 9333);
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";

const profile = mkdtempSync(join(tmpdir(), "firstep-verify-"));
const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-gpu",
    "about:blank",
  ],
  { stdio: "ignore", detached: false }
);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchJson(url, tries = 40) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url);
      if (r.ok) return await r.json();
    } catch {}
    await sleep(250);
  }
  throw new Error("调试端口未就绪：" + url);
}

let ws;
try {
  await fetchJson(`http://127.0.0.1:${PORT}/json/version`);
  const targets = await fetchJson(`http://127.0.0.1:${PORT}/json/list`);
  const page = targets.find((t) => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));

  let seq = 1;
  const pending = new Map();
  const errors = [];
  const consoleMsgs = [];
  ws.addEventListener("message", (ev) => {
    let m;
    try { m = JSON.parse(ev.data); } catch { return; }
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === "Runtime.exceptionThrown") {
      const d = m.params.exceptionDetails || {};
      errors.push((d.exception && (d.exception.description || d.exception.value)) || d.text || "异常");
    }
    if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) {
      consoleMsgs.push(
        "[" + m.params.type + "] " +
        (m.params.args || []).map((a) => a.value ?? a.description ?? a.type).join(" ")
      );
    }
    if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
      consoleMsgs.push("[log:error] " + m.params.entry.text);
    }
  });

  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const id = seq++;
      pending.set(id, resolve);
      ws.send(JSON.stringify({ id, method, params }));
    });

  await send("Runtime.enable");
  await send("Log.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: URL_ });
  await sleep(6000); // 页面初始化 + 各 API 首屏

  const evalJs = async (expr) => {
    const res = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
    if (res.result && res.result.exceptionDetails) return "!! " + res.result.exceptionDetails.text;
    return res.result && res.result.result ? res.result.result.value : undefined;
  };

  const dom = await evalJs(`JSON.stringify({
    readyState: document.readyState,
    title: document.title,
    navTabs: document.querySelectorAll('.tab-btn, [data-tab]').length,
    moduleCards: document.querySelectorAll('#module-grid .module-card, .module-card').length,
    groupCards: document.querySelectorAll('.group-card').length,
    recChips: document.querySelectorAll('.rec-chip, .rec-chip-row .chip').length,
    scriptTags: document.querySelectorAll('script').length,
  })`);
  const alive = await evalJs("(() => { const t = Date.now(); let n = 0; while (Date.now() - t < 50) n++; return n; })()");
  const bridge = await evalJs("typeof window.groupOfSlug + '/' + typeof window.applyGroupChoices + '/' + typeof window.renderGroupCards");
  const navWorks = await evalJs(
    "(() => { const b = document.querySelector('.tab-btn, [data-tab]'); if (!b) return 'no-tab'; b.click(); return 'clicked'; })()"
  );

  console.log("URL            :", URL_);
  console.log("readyState     :", JSON.parse(dom).readyState, "/ title:", JSON.parse(dom).title);
  console.log("主线程存活     :", alive + " 次循环/50ms");
  console.log("DOM 计数       :", dom);
  console.log("window 桥      :", bridge);
  console.log("导航按钮点击   :", navWorks);
  console.log("运行时异常     :", errors.length ? "\n  " + errors.join("\n  ") : "（无）");
  console.log("控制台 error   :", consoleMsgs.length ? "\n  " + consoleMsgs.slice(0, 10).join("\n  ") : "（无）");
  console.log(errors.length === 0 ? "\n结论：页面初始化干净（无 SyntaxError）" : "\n结论：仍有运行时异常");
} finally {
  try { ws && ws.close(); } catch {}
  try { chrome.kill(); } catch {}
  await sleep(600);
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
}
