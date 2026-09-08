// 模拟首次加载时 /api/state 失败/被拒 → 截图 + DOM，与用户截图对比
import { writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9254;
const pageUrl = "http://127.0.0.1:8001/";
const profile = join(ROOT, ".scratch", "bug-editor-type2", "block-profile");
mkdirSync(profile, { recursive: true });
const { execFile } = await import("node:child_process");
execFile("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  ["--headless=new", "--disable-gpu", "--no-first-run", "--remote-debugging-port=" + CDP,
    "--user-data-dir=" + profile, "about:blank"], { windowsHide: true });
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 60 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
await cdp("Page.enable");
await cdp("Network.enable");
await cdp("Network.setBlockedURLs", { urls: ["*://127.0.0.1:8001/api/state*"] });
await cdp("Page.navigate", { url: pageUrl });
await new Promise((r) => setTimeout(r, 6000));
const s = await Eval(`(() => {
  const banner = document.getElementById('gen-banner');
  return {
    platformCards: document.querySelectorAll('#tab-generate .platform-card').length,
    bannerVisible: banner ? !banner.classList.contains('hidden') : null,
    bannerText: banner ? banner.textContent.trim() : null,
    stepDom: document.querySelector('#tab-generate')?.innerHTML.length || 0,
  };
})()`);
console.log(JSON.stringify(s, null, 2));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(ROOT, ".scratch", "bug-editor-type2", "state-failed.png"), Buffer.from(shot.result.data, "base64"));
console.log("screenshot saved");
process.exit(0);
