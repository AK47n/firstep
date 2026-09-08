// 几何探针：headless 页面载入真实 motor.c → 测窗口内每行 guide span 的 x 坐标
// vs 期望列（4/8/12 字符位置），确认缩进引导线是否错位、怎么错位。
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const CDP = 9251;
const fetchT = async (url, ms = 6000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));

// 1.5) 滚到 L45 附近让 45-76 进窗口
await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const first = document.querySelector('#code-viewer .code-hl-line[data-code-line="1"]');
  const lh = first ? first.getBoundingClientRect().height : 25;
  box.scrollTop = Math.max(0, (66 - 1 - 20) * lh);
  box.dispatchEvent(new Event('scroll', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
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
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};

// 1) 载入 motor.c
const dir = "C:\\Users\\luoji\\Desktop\\2024H_Auto_Car_MSPM0";
const path = "modules/motor/code/motor.c";
const fileResp = await fetchT(`http://127.0.0.1:8000/api/code/file?dir=${encodeURIComponent(dir)}&path=${encodeURIComponent(path)}`);
const fileJson = await fileResp.json();
console.log("载入:", fileJson.path, "行数:", String(fileJson.content ?? "").split("\n").length);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const c = ${JSON.stringify(fileJson.content)};
  ta.value = c;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 300));

// 1.5) 滚到 L66 附近让 45-76 进窗口
await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const first = document.querySelector('#code-viewer .code-hl-line[data-code-line="1"]');
  const lh = first ? first.getBoundingClientRect().height : 25;
  box.scrollTop = Math.max(0, (66 - 1 - 20) * lh);
  box.dispatchEvent(new Event('scroll', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));

// 2) 几何测量：引导线 span 的 border-box x 与 期望列 x（用 hl 行首个 12 字符 text node 宽度测 chW）
const out = await Eval(`(() => {
  const report = [];
  for (let n = 50; n <= 76; n++) {
    const hlLine = document.querySelector('#code-viewer .code-hl-line[data-code-line="' + n + '"]');
    const mkLine = document.querySelector('#code-viewer .code-marks-line[data-code-line="' + n + '"]');
    if (!hlLine || !mkLine) {
      report.push({ n, missing: !hlLine ? 'hl' : 'marks' });
      continue;
    }
    const text = hlLine.textContent;
    const indent = text.match(/^[ \\t]*/)[0];
    const colWs = indent.replace(/\\t/g, '    ').length;
    // chW：取 hl 行第一个 text node 前 min(12,len) 字符宽（CJK 行跳过）
    const tn = (() => { const w = document.createTreeWalker(hlLine, NodeFilter.SHOW_TEXT); let t = w.nextNode(); return t; })();
    let chW = null;
    if (tn && indent.length > 0 && indent.length <= 12) {
      const r = document.createRange();
      r.setStart(tn, 0);
      r.setEnd(tn, Math.min(12, tn.data.length));
      const rect = r.getBoundingClientRect();
      if (rect.width > 0) chW = rect.width / Math.min(12, tn.data.length);
    }
    const lineRect = hlLine.getBoundingClientRect();
    const guides = [...mkLine.querySelectorAll('.code-mark-guide')].map((g) => {
      const r = g.getBoundingClientRect();
      return { left: Math.round(r.left * 10) / 10, w: Math.round(r.width * 10) / 10 };
    });
    // 期望：guide 在字符 c-1 处（c=4,8,12...），x ≈ lineRect.left + (c-1)*chW
    const expect = [];
    for (let c = 4; c <= colWs; c += 4) expect.push(Math.round((lineRect.left + (c - 1) * (chW || 7.8)) * 10) / 10);
    report.push({ n, indent: JSON.stringify(indent), colWs, chW: chW == null ? null : Math.round(chW * 100) / 100, guides, expect, lineLeft: Math.round(lineRect.left * 10) / 10 });
  }
  return report;
})()`);
for (const r of out) {
  const diffs = r.guides.map((g, i) => r.expect[i] == null ? null : Math.round((g.left - r.expect[i]) * 10) / 10);
  console.log(`L${r.n} indent=${r.indent} col=${r.colWs} chW=${r.chW} guides=${JSON.stringify(r.guides)} expect=${JSON.stringify(r.expect)} diff=${JSON.stringify(diffs)}`);
}
// 3) 目视截图当前区域
const shot = await cdp("Page.captureScreenshot", { format: "png" });
const fs = await import("node:fs");
const shotPath = join(dirname(dirname(dirname(fileURLToPath(import.meta.url)))), ".scratch/code-page-vscode-overhaul/shot-repro-guides.png");
fs.writeFileSync(shotPath, Buffer.from(shot.result.data, "base64"));
console.log("截图:", shotPath);
process.exit(0);
