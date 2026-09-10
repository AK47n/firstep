// B22（wiki-materials/02）+ B23（wiki-md-repair/04、/06）收口：Markdown 资料库页的
// 浏览器实况验收。
//
// 源工单验收：
//   B22 —— `lckfb-地猛星移植手册/` 批次可见、70 篇 + 2 篇索引全在；过滤「mpu6050」
//          命中 1 篇；预览弹窗渲染正文 + 代码块高亮；刷新 / 清空正常。
//   B23 —— 彩屏篇预览能显示 gif；无图手册（sht30）无异常；列表首列显示中文标题 +
//          文件名小字；预览 / 打开不受影响。
//
// 依赖：webapp 8000 + Chrome headless CDP 9251。零写库（只读浏览 + 打开预览弹窗）。
import { writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect, listTargets } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const PORT = 9251;
const PAGE = "http://127.0.0.1:8000";
const COLOR_MD = "lckfb-地猛星移植手册/screen--0-91-color-screen.md";
const SHT30_MD = "lckfb-地猛星移植手册/sht30.md";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const t = await rebuildTab({ port: PORT });
if (!t) { console.error("重建标签页失败"); process.exit(1); }
const c = await connect({ port: PORT, timeoutMs: 20000 });
const Eval = (e) => c.Eval(e);
const apiJson = async (url) => (await fetch(PAGE + url)).json();

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const shot = async (name) => {
  const s = await c.cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(ROOT, ".scratch", "wiki-materials", name), Buffer.from(s.result.data, "base64"));
  console.log("截图已存档 " + name);
};

for (let i = 0; i < 120; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.querySelector('nav button[data-tab="md"]')`)) break;
  await sleep(250);
}

// ---- 切「Markdown 资料」页签 ----
await Eval(`document.querySelector('nav button[data-tab="md"]').click()`);
const rowsReady = async (n = 1) => {
  for (let i = 0; i < 60; i++) {
    if (await Eval(`document.querySelectorAll('#md-rows tr').length`) >= n) return true;
    await sleep(250);
  }
  return false;
};
check("B22 页签打开后列表已加载", await rowsReady(), "rows=" + await Eval(`document.querySelectorAll('#md-rows tr').length`));

// ---- 期望值：与 UI 同源（GET /api/materials-md 无参全量，客户端过滤）----
const raw = await apiJson("/api/materials-md");
const files = Array.isArray(raw) ? raw : (raw.files || raw.items || []);
const rowCount = await Eval(`document.querySelectorAll('#md-rows tr').length`);
check("B22 列表行数 = 端点全量条数", rowCount === files.length && rowCount > 0, `rows=${rowCount} api=${files.length}`);
check("B22 总量 ≥ 72（70 篇手册 + 2 篇索引）", files.length >= 72, "files=" + files.length);
const batches = [...new Set(files.map((f) => f.batch))];
const dmx = files.filter((f) => f.batch === "lckfb-地猛星移植手册");
const chips = await Eval(`[...document.querySelectorAll('#md-batch-chips [data-md-chip]')].map((b) => b.dataset.mdChip)`);
check("B22 批次 chips 含 lckfb-地猛星移植手册", chips.includes("lckfb-地猛星移植手册"), JSON.stringify(chips.slice(0, 4)));
check("B22 该批次手册数 ≥ 70", dmx.length >= 70, "count=" + dmx.length);
const idxFiles = files.filter((f) => /索引|index/i.test(f.name || "") || /索引/.test(f.title || ""));
check("B22 两篇索引在列（名称含「索引」）", idxFiles.length >= 2, JSON.stringify(idxFiles.map((f) => f.name)));

// ---- 过滤「mpu6050」----
const expectHit = files.filter((f) => [f.name, f.title, f.batch, f.rel_path, f.subdir].some((v) => String(v || "").toLowerCase().includes("mpu6050")));
await Eval(`(() => { const el = document.getElementById('md-filter'); el.value = 'mpu6050'; el.dispatchEvent(new Event('input', { bubbles: true })); })()`);
await sleep(400);
const hitRows = await Eval(`document.querySelectorAll('#md-rows tr').length`);
check("B22 过滤「mpu6050」命中数与端点同源（≥1）", hitRows === expectHit.length && hitRows >= 1, `rows=${hitRows} api=${expectHit.length}`);
const hitText = await Eval(`document.querySelector('#md-rows tr .desc-cell a')?.textContent || ''`);
check("B22 命中行确实是 mpu6050 篇", hitText.toLowerCase().includes("mpu6050"), JSON.stringify(hitText));

// ---- 清空过滤 ----
await Eval(`document.getElementById('md-filter-clear').click()`);
await sleep(400);
check("B22 清空过滤 → 恢复全量", await Eval(`document.querySelectorAll('#md-rows tr').length`) === files.length,
  "rows=" + await Eval(`document.querySelectorAll('#md-rows tr').length`));

// ---- B23：列表首列 = 中文标题 + 文件名小字 ----
const firstCell = await Eval(`(() => {
  const rows = [...document.querySelectorAll('#md-rows tr')];
  const withFile = rows.find((r) => r.querySelector('.md-row-file'));
  const r = withFile || rows[0];
  return { title: r.querySelector('.desc-cell a')?.textContent || '', file: r.querySelector('.md-row-file')?.textContent || '',
           titleFont: getComputedStyle(r.querySelector('.desc-cell a')).fontSize,
           fileFont: withFile ? getComputedStyle(r.querySelector('.md-row-file')).fontSize : null,
           path: r.querySelector('.desc-cell a')?.dataset.openMd || '' };
})()`);
check("B23 首列有中文标题 + 文件名小字（字号更小）",
  !!firstCell.title && !!firstCell.file && firstCell.file !== firstCell.title
  && parseFloat(firstCell.fileFont) < parseFloat(firstCell.titleFont),
  JSON.stringify(firstCell));

// ---- B23：彩屏篇预览能显示 gif ----
// 素材端点吃的是**相对素材根**的路径（含批次目录），与页面里 mdAssetImageUrl 同口径
const gifUrl = "/api/materials-md-assets/" + encodeURIComponent("lckfb-地猛星移植手册/images/0-91-color-screen/img1.gif");
const gifRes = await fetch(PAGE + gifUrl);
check("B23 图片端点直取 gif 200 + image/gif", gifRes.status === 200
  && String(gifRes.headers.get("content-type") || "").includes("gif"), `status=${gifRes.status} type=${gifRes.headers.get("content-type")} url=${gifUrl}`);
await Eval(`document.querySelector('#md-rows [data-md-preview=${JSON.stringify(COLOR_MD)}]')?.click()`);
let preview = null;
for (let i = 0; i < 40; i++) {
  preview = await Eval(`(() => {
    const body = document.querySelector('.ref-files-overlay [data-md-body]');
    if (!body) return null;
    const img = body.querySelector('img');
    return {
      html: body.innerHTML.length,
      h1: body.querySelectorAll('h1, h2').length,
      pre: body.querySelectorAll('pre').length,
      tok: body.querySelectorAll('[class*="tok-"]').length,
      imgs: body.querySelectorAll('img').length,
      imgSrc: img ? img.getAttribute('src') : null,
      imgNatural: img ? img.naturalWidth : 0,
      status: (body.querySelector('.md-preview-status') || {}).textContent || '',
    };
  })()`);
  if (preview && preview.imgs > 0 && preview.imgNatural > 0) break;
  await sleep(300);
}
check("B22 预览弹窗渲染正文（标题/段落 HTML）", !!preview && preview.h1 > 0 && preview.html > 500, JSON.stringify(preview && { h1: preview.h1, html: preview.html }));
check("B22 预览含代码块高亮（tok-* span 或 pre）", !!preview && preview.pre > 0 && preview.tok > 0, JSON.stringify(preview && { pre: preview.pre, tok: preview.tok }));
check("B23 彩屏篇预览显示 gif（img src 走素材端点 + 已解码）",
  !!preview && preview.imgs > 0 && String(preview.imgSrc).includes("/api/materials-md-assets/")
  && String(preview.imgSrc).includes("img1.gif") && preview.imgNatural > 0,
  JSON.stringify(preview && { imgs: preview.imgs, src: preview.imgSrc, naturalW: preview.imgNatural }));
// 截图前把预览正文滚到图片处（否则长文首屏只有文字，目视看不到 gif）
await Eval(`(() => { const img = document.querySelector('.ref-files-overlay [data-md-body] img');
  if (img) img.scrollIntoView({ block: 'center' }); })()`);
await sleep(500);
await shot("shot-md-color-preview.png");
await Eval(`document.querySelector('.ref-files-overlay .ref-files-close')?.click()`);
await sleep(300);

// ---- B23：无图手册（sht30）预览无异常 ----
await Eval(`(() => { const el = document.getElementById('md-filter'); el.value = 'sht30'; el.dispatchEvent(new Event('input', { bubbles: true })); })()`);
await sleep(400);
const shtRel = await Eval(`document.querySelector('#md-rows [data-md-preview]')?.dataset.mdPreview || ''`);
await Eval(`document.querySelector('#md-rows [data-md-preview]')?.click()`);
await sleep(1500);
const sht = await Eval(`(() => {
  const body = document.querySelector('.ref-files-overlay [data-md-body]');
  if (!body) return null;
  return { html: body.innerHTML.length, imgs: body.querySelectorAll('img').length, h: body.querySelectorAll('h1,h2,h3').length,
           danger: !!body.querySelector('.md-preview-status.danger'), text: (body.textContent || '').slice(0, 60) };
})()`);
check("B23 无图手册预览正常（有正文、无图、无错误态）",
  !!sht && sht.html > 300 && sht.h > 0 && !sht.danger && sht.imgs === 0, JSON.stringify({ rel: shtRel, ...sht }));
await Eval(`document.querySelector('.ref-files-overlay .ref-files-close')?.click()`);
await sleep(300);
await Eval(`document.getElementById('md-filter-clear').click()`);
await sleep(400);

// ---- B22：刷新按钮 ----
await Eval(`document.getElementById('md-refresh').click()`);
await sleep(1200);
check("B22 刷新后列表仍为全量", await Eval(`document.querySelectorAll('#md-rows tr').length`) === files.length,
  "rows=" + await Eval(`document.querySelectorAll('#md-rows tr').length`));

// ---- B23：「打开」按钮走新标签（不破坏列表）----
// 注意：`element.click()` 是**非可信**事件，headless 下 window.open 会被弹窗拦截
// （实测：点完标签页数不变）⇒ 用 CDP Input 派发**可信**鼠标事件。
const before = (await listTargets(PORT)).filter((x) => x.type === "page").length;
const rect = await Eval(`(() => {
  const el = document.querySelector('#md-rows [data-open-md]');
  el.scrollIntoView({ block: 'center' });
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), rel: el.dataset.openMd };
})()`);
await c.cdp("Input.dispatchMouseEvent", { type: "mousePressed", x: rect.x, y: rect.y, button: "left", clickCount: 1 });
await c.cdp("Input.dispatchMouseEvent", { type: "mouseReleased", x: rect.x, y: rect.y, button: "left", clickCount: 1 });
await sleep(1500);
const openedPages = (await listTargets(PORT)).filter((x) => x.type === "page");
const after = openedPages.length;
const openedRaw = openedPages.find((x) => String(x.url).includes("/api/materials-md/"));
check("B23 点「打开」原文 → 新标签页（可信点击，窗口未被弹窗拦截）", after > before,
  `before=${before} after=${after} opened=${openedRaw ? openedRaw.url.slice(0, 70) : "(未找到原文页)"}`);
if (openedRaw) {
  const raw = await fetch(openedRaw.url.startsWith("http") ? openedRaw.url : PAGE + new URL(openedRaw.url).pathname).catch(() => null);
  check("B23 新标签页 URL 指向该手册原文（端点 200）", !!raw && raw.status === 200, `status=${raw ? raw.status : "n/a"}`);
}
for (const extra of openedPages.filter((x) => String(x.url).includes("/api/materials-md/"))) {
  await fetch(`http://127.0.0.1:${PORT}/json/close/${extra.id}`).catch(() => {});
}
check("B23 列表在打开原文后仍完整", await Eval(`document.querySelectorAll('#md-rows tr').length`) === files.length);

// 列表截图（回到顶部、无过滤）
await Eval(`document.getElementById('md-filter-clear').click(); document.querySelector('#tab-md')?.scrollIntoView({ block: 'start' })`);
await sleep(400);
await shot("shot-md-list.png");

console.log("---- B22/B23 总览 ----");
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
c.close();
process.exit(failed ? 1 : 0);
