// 现场捕获（用户已恢复坏状态）：窗口切片 vs 实际滚动位置 vs 命中测试
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT("http://127.0.0.1:9251/json/list")).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
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
const d = await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const edit = document.querySelector('#code-viewer .code-edit');
  const ta = document.querySelector('#code-viewer .code-ta');
  const hl = document.querySelector('#code-viewer .code-hl');
  const gutter = document.querySelector('#code-viewer .code-gutter');
  const marks = document.querySelector('#code-viewer .code-marks');
  const br = box.getBoundingClientRect();
  const er = edit ? edit.getBoundingClientRect() : null;
  const tr = ta ? ta.getBoundingClientRect() : null;
  const hr = hl ? hl.getBoundingClientRect() : null;
  const gutNums = gutter ? Array.from(gutter.querySelectorAll('.code-gutter-line')).map(e => Number(e.dataset.codeLine)) : [];
  const hlLines = hl ? Array.from(hl.querySelectorAll('.code-hl-line')).map(e => Number(e.dataset.codeLine)) : [];
  const spacers = Array.from(document.querySelectorAll('#code-viewer .code-window-spacer')).map(s => s.style.height);
  // 命中测试：每个可见 hl 行的中点（代码区右侧）
  const hits = [];
  for (const ln of (hl ? hl.querySelectorAll('.code-hl-line') : [])) {
    const r = ln.getBoundingClientRect();
    if (r.top >= br.top - 1 && r.top < br.bottom + 1) {
      const el = document.elementFromPoint(Math.min(br.right - 30, br.right - 40), r.top + r.height / 2);
      hits.push({ no: Number(ln.dataset.codeLine), el: el ? (el.className || el.tagName || el.id || '?') : null });
    }
  }
  // 逐行几何 vs 期望（textArea 内行矩形）：hl 行 top - 期望top 的 delta
  let deltaInfo = null;
  if (hl && tr && er) {
    const lh = (() => { const l = hl.querySelector('.code-hl-line'); return l ? parseFloat(getComputedStyle(l).lineHeight) : 20; })();
    const first = hl.querySelector('.code-hl-line');
    if (first) {
      const no = Number(first.dataset.codeLine);
      const fr = first.getBoundingClientRect();
      const expectTop = tr.top + 8 + (no - 1) * lh;   // textarea 顶 padding 8
      deltaInfo = { firstNo: no, firstRectTop: Math.round(fr.top), expectTop: Math.round(expectTop), delta: Math.round(fr.top - expectTop), lh: Math.round(lh * 100) / 100 };
    }
  }
  return {
    tabPath: document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath,
    scrollTop: Math.round(box.scrollTop),
    boxH: Math.round(br.height),
    edit: er ? { top: Math.round(er.top), h: Math.round(er.height), styleH: edit.style.height, styleW: edit.style.width } : null,
    ta: tr ? { top: Math.round(tr.top), h: Math.round(tr.height) } : null,
    hl: hr ? { top: Math.round(hr.top), h: Math.round(hr.height) } : null,
    taLines: ta ? ta.value.split('\\n').length : 0,
    gutterNums: { count: gutNums.length, first: gutNums[0], last: gutNums[gutNums.length - 1] },
    hlNums: { count: hlLines.length, first: hlLines[0], last: hlLines[hlLines.length - 1] },
    spacers,
    marksCount: marks ? marks.querySelectorAll('.code-marks-line').length : 0,
    deltaInfo,
    hits: hits.slice(0, 8).concat(hits.slice(-8)),
    gutterOverflow: gutter ? getComputedStyle(gutter).overflow : '',
    editOverflow: edit ? getComputedStyle(edit).overflow : '',
    boxOverflow: getComputedStyle(box).overflowY,
  };
})()`);
console.log(JSON.stringify(d, null, 2));
process.exit(0);
