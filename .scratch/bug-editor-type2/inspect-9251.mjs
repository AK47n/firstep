// 通过浏览器端点 + flatten session 查看 9251 页面当前状态（截图 + 关键 DOM）
import { writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
async function main() {
  const targets = await (await fetch("http://127.0.0.1:9251/json/list")).json();
  const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
  console.log("page:", page ? page.title + " " + page.url : "NONE");
  const ver = await (await fetch("http://127.0.0.1:9251/json/version")).json();
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0; const pending = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const cdp = (m, p = {}, sid) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p, ...(sid ? { sessionId: sid } : {}) })); });
  const a = await cdp("Target.attachToTarget", { targetId: page.id, flatten: true });
  const sid = a.result.sessionId;
  console.log("attached", sid);
  const r = await Promise.race([
    cdp("Runtime.evaluate", { expression: "({ title: document.title, ready: document.readyState, platforms: document.querySelectorAll('#tab-generate .platform-card').length, hasTa: !!document.getElementById('problem') })", returnByValue: true }, sid),
    new Promise((res) => setTimeout(() => res("TIMEOUT"), 4000)),
  ]);
  console.log("eval:", JSON.stringify(r));
  const shot = await Promise.race([
    cdp("Page.captureScreenshot", { format: "png" }, sid),
    new Promise((res) => setTimeout(() => res("TIMEOUT"), 4000)),
  ]);
  console.log("shot:", typeof shot === "string" ? shot : "ok");
  if (shot && shot.result) {
    writeFileSync(join(ROOT, ".scratch", "bug-editor-type2", "harness-page.png"), Buffer.from(shot.result.data, "base64"));
    console.log("saved harness-page.png");
  }
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });
