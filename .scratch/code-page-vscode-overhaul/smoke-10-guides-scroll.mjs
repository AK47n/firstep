// 冒烟（补丁：引导线滚动错位修复）——真实浏览器验证：
// ① 初始顶部窗口 marks/hl 层 y 对齐（dy=0）
// ② 滚动到中部后 marks 层带 top spacer（不再整体上移）
// ③ 中部窗口逐行 marks/hl y 对齐 + 引导线数量=缩进层级（4/8/12 列 → 1/2/3 条）
// CDP 9251 + webapp 8000；样本 indent.c：80 行嵌套 if/else，4 空格缩进。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
const lines = [];
lines.push("// 缩进引导线滚动冒烟样本（80 行，4 空格层级）");
lines.push("void fn(void) {");
lines.push("    if (a) {");
lines.push("        if (b) {");
lines.push("            do_x();");
lines.push("            do_y();");
lines.push("        } else if (c) {");
lines.push("            do_z();");
lines.push("        }");
lines.push("    }");
for (let i = 0; i < 40; i++) {
  lines.push("void fn_" + i + "(void) {");
  lines.push("    if (x_" + i + ") {");
  lines.push("        if (y_" + i + ") {");
  lines.push("            do_" + i + "();");
  lines.push("        }");
  lines.push("    }");
}
lines.push("}");
writeFileSync(join(SAMPLE, "indent.c"), lines.join("\n") + "\n");

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
// CDP 超时守卫（第七轮）：渲染进程偶发无响应时命令永不返回 → 脚本静默挂死。
// 20s 无响应即抛错，让失败可见（而不是卡死）。
const cdp = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++seq;
    const t = setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error("CDP 无响应（20s）: " + method + " —— 页面可能已挂死")); }
    }, 20000);
    pending.set(id, (msg) => { clearTimeout(t); resolve(msg); });
    ws.send(JSON.stringify({ id, method, params }));
  });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 10000) => {
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

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="indent.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="indent.c"]')?.click()`);
await waitFor(`(document.querySelector('#code-viewer .code-ta')?.value || '').includes('fn_39')`);

const dyCheck = `(() => {
  const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const mkRows = [...document.querySelectorAll('#code-viewer .code-marks-line')];
  let bad = 0;
  for (let i = 0; i < hlRows.length && i < mkRows.length; i++) {
    const d = mkRows[i].getBoundingClientRect().top - hlRows[i].getBoundingClientRect().top;
    if (Math.abs(d) > 0.5) bad++;
  }
  return { bad, hlCount: hlRows.length };
})()`;

// ① 初始顶部窗口对齐
await Eval(`(() => { const box = document.getElementById('code-viewer'); box.scrollTop = 0; box.dispatchEvent(new Event('scroll', { bubbles: true })); return true; })()`);
await new Promise((r) => setTimeout(r, 400));
{
  const r = await Eval(dyCheck);
  check("初始顶部窗口 marks/hl y 对齐", r.bad === 0, `bad=${r.bad}/${r.hlCount}`);
}

// ② 滚动到 L45（中部）
await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const first = document.querySelector('#code-viewer .code-hl-line[data-code-line="1"]');
  const lh = first ? first.getBoundingClientRect().height : 25;
  box.scrollTop = (45 - 1) * lh;
  box.dispatchEvent(new Event('scroll', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 500));

// ② marks 层带 top spacer
{
  const mkHead = await Eval(`(document.querySelector('#code-viewer .code-marks')?.innerHTML || '').slice(0, 90)`);
  check("中部滚动后 marks 层带头部 spacer", /code-window-spacer/.test(mkHead), mkHead.replace(/\s+/g, " ").slice(0, 70));
}
// ③ 中部窗口逐行对齐 + guide 数量
{
  const r = await Eval(`(() => {
    const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')];
    const mkRows = [...document.querySelectorAll('#code-viewer .code-marks-line')];
    let dyBad = 0, guideBad = [];
    for (let i = 0; i < hlRows.length && i < mkRows.length; i++) {
      const n = parseInt(hlRows[i].dataset.codeLine, 10);
      const d = mkRows[i].getBoundingClientRect().top - hlRows[i].getBoundingClientRect().top;
      if (Math.abs(d) > 0.5) dyBad++;
      if (n >= 44 && n <= 70) {
        const indent = hlRows[i].textContent.match(/^[ ]*/)[0].length;
        const expect = Math.floor(indent / 4);
        const got = mkRows[i].querySelectorAll('.code-mark-guide').length;
        if (got !== expect) guideBad.push(n + ':' + got + '/' + expect);
      }
    }
    return { dyBad, guideBad };
  })()`);
  check("中部滚动后 marks/hl y 对齐", r.dyBad === 0, `bad=${r.dyBad}`);
  check("引导线数量=缩进层级（4/8/12 → 1/2/3）", r.guideBad.length === 0, r.guideBad.join(",") || "ok");
}

// ④ 缩放 80% 后仍对齐（用户场景）
await Eval(`(() => { document.getElementById('code-viewer').style.setProperty('--code-zoom', '0.8'); return true; })()`);
await new Promise((r) => setTimeout(r, 300));
await Eval(`(() => { const box = document.getElementById('code-viewer'); box.scrollTop += 100; box.dispatchEvent(new Event('scroll', { bubbles: true })); return true; })()`);
await new Promise((r) => setTimeout(r, 400));
{
  const r = await Eval(dyCheck);
  check("80% 缩放 + 滚动后 marks/hl y 对齐", r.bad === 0, `bad=${r.bad}`);
}

console.log("---- 冒烟总览 ----");
console.log((failed ? "FAIL " : "PASS ") + passed + " / FAIL " + failed);
process.exit(failed ? 1 : 0);
