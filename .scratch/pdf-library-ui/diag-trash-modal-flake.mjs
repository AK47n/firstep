// 取证（第十轮）：pdf-library-ui/smoke.mjs 场景 06 在「合成重复对 → 点删除钮」处确定性失败
// （Cannot read properties of null (reading 'textContent') —— `.ref-files-overlay` 不在场）。
//
// 复现 = 与 smoke.mjs 同一段流程，但**分步计时**：
//   ① 写两份同内容合成 PDF（zz-smoke-pair）→ reload
//   ② 点 [data-pdf-trash=<rel1>] → 每 50ms 采样一次：overlay 在不在、行在不在
//   ③ 记录 overlay 首次出现的时间；同时量点前那次真实请求
//      GET /api/pdfs/{rel_path}/refs（openPdfTrashConfirm 弹窗前先 await 它）的墙钟
// 判据：若 ②③ 显示「overlay 出现晚于 smoke 的固定 400ms 等待」→ 脚本等待写死是根因；
//       若 overlay 永不到场 → 产品路径有真缺陷（点没接上 / 弹窗被吞）。
import { mkdirSync, writeFileSync, rmSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const MATERIALS = join(ROOT, "sources", "materials");
const TRASH = join(ROOT, "sources", ".trash-pdf");
const pageUrl = "http://127.0.0.1:8000/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dateStr = (() => {
  const t = new Date(), p = (n) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`;
})();

await rebuildTab({ port: 9251, pageUrl, settleMs: 2000 });
const c = await connect({ port: 9251, pageUrl });
await c.cdp("Page.enable");
const Eval = (e) => c.Eval(e);

await Eval(`(async () => {
  const ui = { pdf: await import('/js/ui/pdf.js') };
  window.__probe = { ui, pdfs: await (await fetch('/api/pdfs')).json(),
    reload: async () => { window.__probe.pdfs = await (await fetch('/api/pdfs')).json();
      await window.__probe.ui.pdf.loadPdfs(); return window.__probe.pdfs.length; } };
  return window.__probe.pdfs.length;
})()`);
await c.ready(`document.readyState === 'complete' && !!document.getElementById('pdf-rows') && !!window.__probe`);
const smokeBatch = await Eval(`(async () => {
  const tab = [...document.querySelectorAll('nav button')].find((b) => b.dataset.tab === 'pdf');
  if (tab) tab.click();
  await new Promise((r) => setTimeout(r, 600));
  return window.__probe.pdfs[0].batch;
})()`);
console.log("smokeBatch =", smokeBatch);

const rel1 = smokeBatch + "/zz-smoke-dup/zz-smoke-pair.pdf";
const rel2 = smokeBatch + "/zz-smoke-dup-2/zz-smoke-pair.pdf";
const bytes = "%PDF-1.4\nzz smoke pair（第十轮取证）";
const abs = [rel1, rel2].map((r) => join(MATERIALS, r));
const dirs = [
  join(MATERIALS, smokeBatch, "zz-smoke-dup"), join(MATERIALS, smokeBatch, "zz-smoke-dup-2"),
  join(TRASH, dateStr, smokeBatch, "zz-smoke-dup"), join(TRASH, dateStr, smokeBatch, "zz-smoke-dup-2"),
];
for (const d of dirs) mkdirSync(d, { recursive: true });
writeFileSync(abs[0], bytes);
writeFileSync(abs[1], bytes);

try {
  // ---- ③ 先量后端那一步的墙钟（openPdfTrashConfirm 弹窗前 await 的请求） ----
  const refsMs = await Eval(`(async () => {
    const t0 = performance.now();
    const r = await fetch('/api/pdfs/' + encodeURIComponent(${JSON.stringify(rel1)}) + '/refs');
    const j = await r.json().catch(() => null);
    return { ms: Math.round(performance.now() - t0), titles: j && j.titles ? j.titles.length : null };
  })()`);
  console.log(`GET /api/pdfs/{rel}/refs 墙钟 = ${refsMs.ms}ms（titles=${refsMs.titles}）`);

  // ---- ② 复现：reload → 点删除钮 → 每 50ms 采样 ----
  const res = await Eval(`(async () => {
    await window.__probe.reload();
    await new Promise((r) => setTimeout(r, 250));
    const btn = document.querySelector('#pdf-rows [data-pdf-trash="${rel1}"]');
    if (!btn) return { found: false };
    const t0 = performance.now();
    btn.click();
    const marks = [];
    let firstAt = null;
    for (let i = 0; i < 60; i++) {           // 最长 3s
      await new Promise((r) => setTimeout(r, 50));
      const ov = document.querySelector('.ref-files-overlay');
      if (ov) { firstAt = Math.round(performance.now() - t0); break; }
      if (i === 7) marks.push('400ms 仍无 overlay');
    }
    const ov = document.querySelector('.ref-files-overlay');
    return { found: true, firstAtMs: firstAt, marks,
      overlayCount: document.querySelectorAll('.ref-files-overlay').length,
      hasOk: !!(ov && ov.querySelector('[data-confirm-ok]')),
      text: ov ? ov.textContent.slice(0, 60) : null,
      rowStill: !!document.querySelector('#pdf-rows [data-pdf-trash="${rel1}"]') };
  })()`);
  console.log("点击 → overlay 首现：" + JSON.stringify(res));
  if (res.firstAtMs !== null && res.firstAtMs > 400) {
    console.log(`!! overlay 首现 ${res.firstAtMs}ms > smoke.mjs 写死的 400ms 等待 → 脚本等待过短是根因`);
  }
  // 关掉弹窗（取证不留残留）
  await Eval(`(() => { const o = document.querySelector('.ref-files-overlay [data-confirm-cancel]'); if (o) o.click(); return true; })()`);
  await sleep(300);
  console.log("残留 overlay：" + await Eval(`document.querySelectorAll('.ref-files-overlay').length`));
} finally {
  // 零残留：源文件与回收镜像一起清（本轮不真删任何素材）
  for (const p of abs) if (existsSync(p)) rmSync(p);
  for (const d of dirs) if (existsSync(d)) rmSync(d, { recursive: true, force: true });
  const left = await Eval(`(async () => {
    await window.__probe.reload();
    return window.__probe.pdfs.filter((p) => p.rel_path.includes('zz-smoke')).length;
  })()`);
  console.log("清理后 zz-smoke 残留条目 = " + left);
}
c.close();
