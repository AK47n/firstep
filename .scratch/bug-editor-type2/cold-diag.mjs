// 冷浏览器首次加载诊断：新 profile（无缓存）+ 全新服务实例
// 捕获 console / 异常 / 失败请求 / 关键 DOM 状态，比较首次加载与 F5 重载。
import { execFile } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9253;
const pageUrl = "http://127.0.0.1:8001/";
const profile = join(ROOT, ".scratch", "bug-editor-type2", "cold-profile");

const chrome = execFile("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--remote-debugging-port=" + CDP, "--user-data-dir=" + profile, pageUrl],
  { windowsHide: true });
chrome.stderr.on("data", () => {});

const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
const events = [];
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  else if (msg.method === "Runtime.consoleAPICalled") {
    events.push({ kind: "console", type: msg.params.type,
      text: (msg.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ") });
  } else if (msg.method === "Runtime.exceptionThrown") {
    const d = msg.params.exceptionDetails;
    events.push({ kind: "exception", text: (d.exception && d.exception.description || d.text || "").slice(0, 500) });
  } else if (msg.method === "Network.loadingFailed") {
    events.push({ kind: "netfail", text: msg.params.errorText + " " + (msg.params.requestId || "") });
  }
};
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

await cdp("Runtime.enable");
await cdp("Network.enable");
await cdp("Page.enable");
const t0 = Date.now();
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const snapshot = async (tag) => {
  const s = await Eval(`(() => {
    const g = (id) => document.getElementById(id);
    const platformCards = document.querySelectorAll('#tab-generate .platform-card').length;
    const step1 = !!g('problem');
    const banner = g('gen-banner');
    const welcome = g('welcome-card');
    return {
      tag: ${JSON.stringify(tag)},
      ready: document.readyState,
      platformCards,
      step1Textarea: step1,
      bannerVisible: banner ? !banner.classList.contains('hidden') : null,
      bannerText: banner ? banner.textContent.trim() : null,
      welcomeVisible: welcome ? getComputedStyle(welcome).display !== 'none' : null,
      platformHTML: (document.querySelector('#tab-generate .platform-options') || {}).innerHTML?.slice(0, 200) || null,
    };
  })()`);
  return s;
};
// 等待首帧完成（DOM 就绪 + 若干秒给 boot fetch）
await wait(6000);
const first = await snapshot("首次加载");
console.log("first load @", Date.now() - t0, "ms:", JSON.stringify(first, null, 2));
console.log("事件（首次）:", JSON.stringify(events, null, 2));

// F5 重载对比
await cdp("Page.reload", { ignoreCache: true });
await wait(6000);
const events2 = [];
ws.onmessage = (() => {
  const old = ws.onmessage;
  return null;
})();
// 重新收集事件（简单：直接快照 + 用例内保留旧监听，另开一个数组）
const devNull = [];
const second = await snapshot("F5 重载");
console.log("second load:", JSON.stringify(second, null, 2));
console.log("事件（含重载后）:", JSON.stringify(events.slice(-20), null, 2));
process.exit(0);
