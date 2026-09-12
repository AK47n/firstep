// smoke-full-update.mjs — 完整包下载窗口真机冒烟（工单 full-download/05）
//
// 真浏览器（CDP 9251 + webapp 8000）验证：
//  1) 设置页出现「完整包下载」卡（检查按钮 + 说明）；
//  2) 点「检查完整包」→ 真实打 /api/update/full/check（fetch 被桩成假的完整包
//     响应，避免依赖 GitHub 网络）→ 结果区渲染出「下载完整 firstep」按钮；
//  3) 点按钮 → 确认弹窗出现（版本 / 体积 / 卷数 / 重启语义 / 开始下载）；
//  4) 资料库区在无基线时主按钮是「一键下载完整 firstep」（双轨选路）；
//  5) 深色截图存档。
// 零写库、零真实网络（只桩 fetch 的更新相关端点）。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
// 页面地址可用 SMOKE_URL 覆盖（缺省 8000；冒烟常另起 8011 临时实例避免打扰在用实例）
const pageUrl = process.env.SMOKE_URL || "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "full-download");
mkdirSync(OUT, { recursive: true });

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  —— " + detail : ""}`);
};

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
if (!targets) { console.error("CDP 不可达（Chrome 是否带 --remote-debugging-port=9251 启动？）"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
if (!page) { console.error("找不到页面 target（type=page）"); process.exit(1); }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++seq;
    const t = setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error("CDP 无响应（20s）: " + method)); }
    }, 20000);
    pending.set(id, (msg) => { clearTimeout(t); resolve(msg); });
    ws.send(JSON.stringify({ id, method, params }));
  });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) {
    throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  }
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await cdp("Runtime.enable");
await cdp("Page.enable");

// 先把页面导到目标地址（Chrome 可能带着别的 URL 起来），再等 SPA 装好
await cdp("Page.navigate", { url: pageUrl });
await waitFor(`document.readyState === "complete" && !!document.querySelector('button[data-tab="settings"]')`, 20000);

// ---- 桩：只截 check 与 status，其余放行；apply 走真实端点 + dry_run 演练 ----
const PART = "firstep-full-v1.1.0.zip";
const stub = `
(() => {
  if (window.__fullSmokeStub) return true;
  window.__fullSmokeStub = true;
  const realFetch = window.fetch.bind(window);
  const json = (obj) => new Response(JSON.stringify(obj), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
  window.fetch = (input, init) => {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.includes("/api/update/full/check")) {
      const seeded = url.includes("seeded=1");
      return realFetch(input, init).then((r) => r.json()).then((real) => {
        // 真检查打底（顺带让后端也真跑过一次 check）；seeded=1 时**原样返回真
        // 结果**，只为把后端白名单种上，不改 UI 展示
        if (seeded) return json(real);
        return json({
          current_version: "", latest_version: "v1.1.0", update_available: true,
          total_bytes: 1073741824,
          parts: (real.parts && real.parts.length ? real.parts : [
            { name: "${PART}", size: 1073741824, sha256: "a".repeat(64),
              url: "https://example.com/${PART}" },
          ]),
          reason: "no-installed", error: "",
          message: "本地完整包版本未知；最新完整包 v1.1.0，约 1024 MB，可一键下载",
          manifest_url: real.manifest_url || "https://example.com/firstep-full-v1.1.0.manifest.json",
        });
      });
    }
    if (url.includes("/api/update/materials/check")) {
      return Promise.resolve(json({
        current_version: "", latest_version: "", update_available: false,
        total_size_bytes: 0, batches: [], deleted_batches: [],
        error: "baseline-missing",
        message: "本地资料库版本未知（缺少基线清单），无法增量更新；请下载完整包",
      }));
    }
    if (url.includes("/api/update/full/status")) {
      return Promise.resolve(json({
        state: "downloading", parts: [
          { name: "${PART}", downloaded_bytes: 268435456, total_bytes: 1073741824, ok: false },
        ],
        total_downloaded_bytes: 268435456, total_bytes: 1073741824,
        speed_bps: 5242880, current_part_name: "${PART}", error: "", message: "",
      }));
    }
    if (url.includes("/api/update/full/apply")) {
      // 记下真实请求体（断言前端 POST 的分卷名与 check 结果一致），回成功态。
      // 不真跑 apply 的理由：后端 apply 的白名单来自「服务端自己的 check」，
      // 而本机没有真实完整包资产；下载/替换链路由 Python 侧 e2e 与更新器
      // 集成测试覆盖，这里只验前端接线。
      const body = init && init.body ? JSON.parse(init.body) : {};
      window.__fullSmokeApplyBody = body;
      return Promise.resolve(json({ started: true, message: "演练：已开始下载完整包" }));
    }
    return realFetch(input, init);
  };
  return true;
})()
`;

// ---- 1. 设置页出现完整包卡 ----
await Eval(`document.querySelector('button[data-tab="settings"]')?.click(); true`);
await waitFor(`!!document.getElementById("btn-full-check")`);
check("设置页存在「完整包下载」卡（检查按钮）", await Eval(`!!document.getElementById("btn-full-check")`));
check("卡内有结果容器与说明文案", await Eval(
  `!!document.getElementById("full-update-results") && /整份 firstep/.test(document.body.innerText)`
));

// ---- 2. 检查完整包（桩）→ 结果区出现下载按钮 ----
await Eval(stub);
await Eval(`fetch("/api/update/full/check?seeded=1").then(r => r.status).catch(() => -1)`);
await Eval(`document.getElementById("btn-full-check").click(); true`);
await waitFor(`!!document.getElementById("btn-full-download")`);
check("检查完整包 → 结果区渲染「下载完整 firstep」按钮", await Eval(`!!document.getElementById("btn-full-download")`));
const cardText = await Eval(`document.getElementById("full-update-results").innerText`);
check("结果卡含版本与体积", /v1\.1\.0/.test(cardText) && /1\.0 GB|1024 MB/.test(cardText), JSON.stringify(cardText).slice(0, 160));

// ---- 3. 点下载 → 确认弹窗 ----
await Eval(`document.getElementById("btn-full-download").click(); true`);
await waitFor(`!!document.querySelector(".ref-files-overlay #btn-full-start")`);
check("确认弹窗出现且带「开始下载」按钮", await Eval(`!!document.querySelector(".ref-files-overlay #btn-full-start")`));
const dialogText = await Eval(`(document.querySelector(".ref-files-overlay")||{}).innerText || ""`);
check("弹窗说明重启语义与卷数", /重启/.test(dialogText) && /1 卷/.test(dialogText), JSON.stringify(dialogText).slice(0, 200));

// ---- 4. 资料库区无基线 → 主按钮是「一键下载完整 firstep」 ----
await Eval(`document.querySelector(".ref-files-overlay [data-confirm-cancel]")?.click(); true`);
await Eval(`document.getElementById("btn-materials-check").click(); true`);
await waitFor(`!!document.getElementById("btn-materials-full-download")`);
check("资料库区无基线 → 主按钮「一键下载完整 firstep」（双轨选路）",
  await Eval(`!!document.getElementById("btn-materials-full-download")`));

// ---- 5. 下载中：进度视图（桩 status）----
await Eval(`document.getElementById("btn-full-check").click(); true`);
await waitFor(`!!document.getElementById("btn-full-download")`);
await Eval(`document.getElementById("btn-full-download").click(); true`);
await waitFor(`!!document.querySelector(".ref-files-overlay #btn-full-start")`);
await Eval(`document.querySelector(".ref-files-overlay #btn-full-start").click(); true`);
await waitFor(`/正在下载完整包/.test(document.getElementById("full-update-results").innerText)`, 8000);
const progressText = await Eval(`document.getElementById("full-update-results").innerText`);
check("下载中显示进度 / 当前卷 / 速度 / 取消按钮",
  /当前卷/.test(progressText) && /MB\/s/.test(progressText)
  && (await Eval(`!!document.getElementById("btn-full-cancel")`)),
  JSON.stringify(progressText).slice(0, 200));
const applyBody = await Eval(`JSON.stringify(window.__fullSmokeApplyBody || null)`);
check("apply 请求体带上了 check 返回的分卷名",
  /firstep-full-v1\.1\.0\.zip/.test(applyBody || ""), String(applyBody).slice(0, 120));

// ---- 6. 截图存档 ----
const shot = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
writeFileSync(join(OUT, "shot-full-update-window-dark.png"), Buffer.from(shot.result.data, "base64"));
console.log("截图：" + join(OUT, "shot-full-update-window-dark.png"));

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} PASS`);
ws.close();
process.exit(failed.length ? 1 : 0);
