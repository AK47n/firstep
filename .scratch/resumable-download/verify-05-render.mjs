// verify-05-render.mjs — 工单 05 目视证据第二步：**真前端纯函数**渲染 + 截图
// （工单 resumable-download/05）。
//
// 输入 `.scratch/resumable-download/verify-05-payloads.json`（真任务跑出来的状态载荷，
// 见 `verify-05-capture.py`）；这里用 fx/full-update.js 与 fx/materials-update.js 的
// **真函数**渲染成 HTML，再截两张图：
//   · `verify-05-ui-progress.png`：慢 / 在重试 / 正常 —— 进度区的三种样子
//   · `verify-05-ui-failed.png`：两种失败话术（verify / network）
//
// 判据不靠"看图"：截图前先把关键文案**断言一遍**（缺了就直接失败并落证据），
// 图是给人看的旁证，不是判据本体。
//
// 用法：`node .scratch/resumable-download/verify-05-render.mjs`
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const REPO = fileURLToPath(new URL("../../", import.meta.url));
const FX = pathToFileURL(`${REPO}src/contest_generator/static/js/fx/`).href;

const payloads = JSON.parse(readFileSync(`${HERE}verify-05-payloads.json`, "utf8"));
const byId = Object.fromEntries(payloads.cases.map((c) => [c.id, c.status]));

const { fullProgressHTML } = await import(`${FX}full-update.js`);
const { materialsProgressHTML } = await import(`${FX}materials-update.js`);

// 两条链路的载荷**都是真任务跑出来的**（`verify-05-capture.py`），这里不再手写任何字段
const views = [
  { title: "慢（弱网但连接正常）· 完整包", html: fullProgressHTML(byId.slow),
    must: [/网络较慢/], mustNot: [/网络中断/, /正在自动重试/, /btn-full-retry/] },
  { title: "在重试（退避等待中）· 完整包", html: fullProgressHTML(byId.retrying),
    must: [/正在自动重试（第 1 次）/, /从 39% 接着下/, /btn-full-cancel/],
    mustNot: [/btn-full-retry/] },
  { title: "在重试 · 资料库", html: materialsProgressHTML(byId["materials-retrying"]),
    must: [/正在自动重试（第 1 次）/, /从 39% 接着下/], mustNot: [/网络中断（已下载/] },
  { title: "失败·网络类 · 完整包", html: fullProgressHTML(byId["failed-network"]),
    must: [/网络中断（已下载 40%）/, /点击重试会从这里接着下/, /btn-full-retry/],
    mustNot: [/重新下载也不会有变化/] },
  { title: "失败·校验类（verify）· 完整包", html: fullProgressHTML(byId["failed-verify"]),
    must: [/校验失败/, /重新下载也不会有变化/],
    mustNot: [/点击重试会从这里接着下/, /btn-full-retry/] },
  { title: "失败·校验类（verify）· 资料库",
    html: materialsProgressHTML(byId["materials-failed-verify"]),
    must: [/重新下载也不会有变化/], mustNot: [/点击重试会从这里接着下/] },
];

// ---- 判据（先断言，再截图）-------------------------------------------------
const problems = [];
for (const view of views) {
  for (const re of view.must) {
    if (!re.test(view.html)) problems.push(`${view.title}：缺少 ${re}`);
  }
  for (const re of view.mustNot) {
    if (re.test(view.html)) problems.push(`${view.title}：不该出现 ${re}`);
  }
}
if (problems.length) {
  writeFileSync(`${HERE}verify-05-ui-problems.txt`, problems.join("\n"), "utf8");
  console.error("判据未过，详见 verify-05-ui-problems.txt");
  for (const p of problems) console.error("  ·", p);
  process.exit(1);
}

// ---- 渲染 + 截图 -----------------------------------------------------------
const page = await chromium.launch().then((b) => b.newPage({ viewport: { width: 980, height: 900 } }));
const styles = `<style>
  body { font: 14px/1.6 "Microsoft YaHei", system-ui, sans-serif; background: #f6f7f9;
         margin: 0; padding: 20px; color: #202124; }
  h2 { font-size: 15px; margin: 18px 0 6px; color: #5f6368; }
  .card { background: #fff; border: 1px solid #e3e6ea; border-radius: 10px;
          padding: 14px 16px; max-width: 880px; }
  .progress { height: 8px; background: #e8eaed; border-radius: 4px; overflow: hidden; }
  .progress-fill { height: 100%; background: #1a73e8; }
  .muted { color: #5f6368; } .warning { color: #b26a00; } .error { color: #c5221f; }
  .ok { color: #137333; } .row { display: flex; gap: 8px; align-items: center; }
  button { font: inherit; padding: 4px 10px; }
  .materials-part-row { display: flex; justify-content: space-between; max-width: 420px; }
  .materials-part-meta { color: #5f6368; }
</style>`;

async function shot(file, subset) {
  const body = subset.map((v) => `<h2>${v.title}</h2><div class="card">${v.html}</div>`).join("");
  await page.setContent(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">${styles}</head><body>${body}</body></html>`);
  await page.screenshot({ path: `${HERE}${file}`, fullPage: true });
  console.log("截图：", file);
}

await shot("verify-05-ui-progress.png", views.slice(0, 3));
await shot("verify-05-ui-failed.png", views.slice(3, 6));
await page.context().browser().close();

writeFileSync(`${HERE}verify-05-ui.txt`, [
  "# 工单 05 目视证据：下载进度与失败话术（resumable-download/05）",
  "",
  "载荷来源：`verify-05-capture.py` 跑**真任务**（真 socket 打 sim-server.py）导出的",
  "状态面载荷 → `verify-05-payloads.json`；渲染用的是 `static/js/fx/*.js` 的**真函数**。",
  "",
  "| 图 | 看什么 |",
  "|---|---|",
  "| `verify-05-ui-progress.png` | 慢（弱网但正常，明写「网络较慢」）／在重试（明写第几次、从多少接着下、可取消）／资料库同款口径 |",
  "| `verify-05-ui-failed.png` | 两种失败话术：网络类（已下 40% + 会接着下）／校验类（重下也不会有变化）；资料库与完整包同源 |",
  "",
  "判据（截图前逐条断言，缺一即失败并落 `verify-05-ui-problems.txt`）：",
  ...views.flatMap((v) => [
    `- ${v.title}：必须含 ${v.must.map(String).join("、")}；不得含 ${v.mustNot.map(String).join("、")}`,
  ]),
  "",
].join("\n"), "utf8");
console.log("证据说明已写：verify-05-ui.txt");
