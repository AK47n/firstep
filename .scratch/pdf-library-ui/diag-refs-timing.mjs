// 取证（第十轮，pdf-library-ui 场景 06）：把「弹窗晚到」拆到具体请求上量墙钟。
// 疑点：openPdfTrashConfirm 弹窗前先 `await apiGet(pdfRefsUrl(rel_path))`；
// diag-trash-modal-flake.mjs 实测该请求 ≈600ms，而 smoke.mjs 只等写死的 400ms。
import { rebuildTab, connect } from "../cdp-harness.mjs";

const pageUrl = "http://127.0.0.1:8000/";
await rebuildTab({ port: 9251, pageUrl, settleMs: 2000 });
const c = await connect({ port: 9251, pageUrl });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e);

const out = await Eval(`(async () => {
  const time = async (label, fn) => { const t0 = performance.now(); const v = await fn();
    return { label, ms: Math.round(performance.now() - t0), n: v }; };
  const pdfs = await (await fetch('/api/pdfs')).json();
  const batch = pdfs[0].batch;
  const rel = batch + '/zz-smoke-dup/zz-smoke-pair.pdf';
  // 一个真实存在的条目（不存在的 rel 会被后端拒绝，量不到真实成本）
  const real = pdfs.find((p) => p.rel_path.endsWith('.pdf')).rel_path;
  const rows = [];
  rows.push(await time('GET /api/pdfs', async () => (await (await fetch('/api/pdfs')).json()).length));
  rows.push(await time('GET /api/pdfs（第二次）', async () => (await (await fetch('/api/pdfs')).json()).length));
  rows.push(await time('GET /api/pdfs/<真实文件>/refs', async () =>
    (await (await fetch('/api/pdfs/' + encodeURIComponent(real) + '/refs')).json()).titles.length));
  rows.push(await time('GET /api/pdfs/<真实文件>/refs（第二次）', async () =>
    (await (await fetch('/api/pdfs/' + encodeURIComponent(real) + '/refs')).json()).titles.length));
  rows.push(await time('GET /api/references', async () => (await (await fetch('/api/references')).json()).length));
  rows.push(await time('GET /api/state', async () => 1));
  return { rel, real, rows };
})()`);
console.log("样本文件：" + out.real);
for (const r of out.rows) console.log(`  ${String(r.ms).padStart(6)}ms  ${r.label}（n=${r.n}）`);
c.close();
