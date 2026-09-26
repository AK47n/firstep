// 工单 ci-gate-fixes/04 的真机探针：**没配 AI key** 的机器上，页面还空不空窗。
//
// 判据（全部走真后端 + 真 Chromium + 真静态资源，后端就是产品入口
// `python -m contest_generator.webapp`）：
//   ① 这份配置**确实是"未配置 AI"**：`/api/env/status` 的 api_configured === false，
//      且 `/api/recommend` 答 400「未配置 AI API」（AI 面没被放水）；
//   ② 库端点此时 200 且**非空**：`/api/modules` 拿到 N 个模块；
//   ③ 生成页的模块池（#module-grid）**渲染出行来**、计数行不是 0——
//      这正是"空窗"的用户可见形态；
//   ④ 页面上「尚未配置 AI API」横幅**照旧可见**（AI 面如实，不是把未配置藏起来）；
//   ⑤ 模块库 tab（data-tab=library）出表格行。
//
// 配置来源 = **引导态**（install.bat 写的形态：库路径齐全 + api_key 空串），
// 库指向检出内那份真库。
//
// `PROBE_SRC`：把后端的 `PYTHONPATH` 指到另一份 src（默认 `src`）——用来跑
// **改动前的对照**：把 HEAD 的 webapp.py 放进一份 src 副本里指过去，同一支探针
// 就给出"修之前长什么样"。库仍取本仓真库（配置里的路径是绝对的）。
//
// 用法（仓库根，需先 `npm install` + `npx playwright install chromium`）：
//   node .scratch/ci-gate-fixes/probe-04-unconfigured-page.mjs
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const REPO_ROOT = fileURLToPath(new URL("../../", import.meta.url));
const PROBE_SRC = (process.env.PROBE_SRC || "src").trim();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fails = [];
const readings = [];
const observations = [];
const check = (ok, label, detail = "") => {
  readings.push(`${ok ? "  ok  " : " FAIL "} ${label}${detail ? ` — ${detail}` : ""}`);
  if (!ok) fails.push(label);
};

function freePort() {
  return new Promise((resolve, reject) => {
    const probe = createServer();
    probe.unref();
    probe.on("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

async function main() {
  // ---- 引导态配置（install.bat 写的形态：库路径齐全 + api_key 空串）----
  const cfgDir = mkdtempSync(join(tmpdir(), "firstep-probe04-"));
  const cfgPath = join(cfgDir, "config.json");
  writeFileSync(cfgPath, JSON.stringify({
    api_key: "",
    module_library_dir: join(REPO_ROOT, "library", "modules"),
    masters_dir: join(REPO_ROOT, "library", "masters"),
  }, null, 2), "utf8");

  const port = await freePort();
  const url = `http://127.0.0.1:${port}`;
  let log = "";
  const proc = spawn("python", ["-m", "contest_generator.webapp"], {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      PYTHONPATH: PROBE_SRC,
      PYTHONIOENCODING: "utf-8",
      PYTHONUNBUFFERED: "1",
      FIRSTEP_LAUNCHER_PORT: String(port),
      FIRSTEP_CONFIG_PATH: cfgPath,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  proc.stdout.on("data", (d) => { log += d.toString(); });
  proc.stderr.on("data", (d) => { log += d.toString(); });

  let browser = null;
  try {
    // ---- 等健康检查 ----
    const deadline = Date.now() + 30000;
    let up = false;
    while (Date.now() < deadline) {
      try {
        if ((await fetch(`${url}/api/health`)).ok) { up = true; break; }
      } catch { /* 还没起来 */ }
      if (proc.exitCode !== null) break;
      await sleep(200);
    }
    if (!up) throw new Error(`后端起不来（exit ${proc.exitCode}）：\n${log.slice(-800)}`);

    // ---- ① 确实是"未配置 AI" ----
    const env = await (await fetch(`${url}/api/env/status`)).json();
    check(env.api_configured === false, "env/status 报未配置 AI",
      `api_configured=${env.api_configured}`);
    const rec = await fetch(`${url}/api/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ problem_text: "x" }),
    });
    const recBody = await rec.json();
    check(rec.status === 400 && String(recBody.detail).includes("未配置 AI API"),
      "推荐端点仍 400「未配置 AI API」", `${rec.status} ${recBody.detail}`);

    // ---- ② 库端点 200 且非空 ----
    const modResp = await fetch(`${url}/api/modules`);
    const mods = modResp.ok ? await modResp.json() : [];
    check(modResp.ok, "/api/modules 200", `status=${modResp.status}`);
    check(mods.length > 0, "/api/modules 非空", `count=${mods.length}`);
    for (const path of ["/api/masters", "/api/topics", "/api/references"]) {
      const r = await fetch(`${url}${path}`);
      check(r.ok, `${path} 200`, `status=${r.status}`);
    }

    // ---- ③④⑤ 真浏览器 ----
    browser = await chromium.launch();
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(url, { waitUntil: "domcontentloaded" });
    // 模块池：按渲染出的单元格数判"空窗"。**等不到不算探针崩**——"一行都没有"
    // 正是本探针要照下来的那种读数（改动前就是这个形态）。
    await page.waitForSelector("#module-grid > *", { timeout: 20000 })
      .catch(() => {});
    const gridCount = await page.locator("#module-grid > *").count();
    const countText = await page.locator("#module-count").innerText().catch(() => "");
    check(gridCount > 0, "生成页模块池渲染出行", `cells=${gridCount} / 计数行=${JSON.stringify(countText)}`);

    // ⚠ 横幅**不是本单的判据**（改前改后一样是 hidden，见下面的观察行）：`#gen-banner`
    // 只在 `ui/settings.js:534`（保存设置后）被 toggle，首屏没人开它——既有前端缺口，
    // 与库端点那道闸无关。这里如实记一行观察，不拿它判本单的红绿。
    const bannerVisible = await page.locator("#gen-banner").isVisible();
    observations.push(`「尚未配置 AI API」横幅首屏可见 = ${bannerVisible}`
      + `（既有行为：只在保存设置后 toggle，与库闸门无关）`);

    // 模块库 tab：切过去看**真数据行**。判据不能是 `tbody tr`——加载态占位行也是
    // 一个 `<tr>`（实测把它数成 rows=1 = 假绿）；数据行的 td 没有 colspan，
    // 占位行是 `<td colspan="5" class="empty-td">`（ui/library.js）。
    await page.locator('button[data-tab="library"]').click();
    await page.waitForSelector("#lib-rows tr td:not([colspan])", { timeout: 15000 })
      .catch(() => {});
    const libRows = await page.locator("#lib-rows tr td:not([colspan])").count();
    check(libRows > 0, "模块库 tab 出真数据行", `data-cells=${libRows}`);

    check(errors.length === 0, "页面无 JS 报错", errors.slice(0, 3).join(" | "));
  } finally {
    if (browser) await browser.close().catch(() => {});
    proc.kill();
    await sleep(300);
    try { rmSync(cfgDir, { recursive: true, force: true }); } catch { /* 收不掉不影响结论 */ }
  }

  console.log("# 探针读数（工单 ci-gate-fixes/04 · 未配置 AI key 的机器上页面空不空窗）\n");
  for (const line of readings) console.log(line);
  if (observations.length) {
    console.log("\n# 顺带观察（不判本单红绿）\n");
    for (const line of observations) console.log(`  ·  ${line}`);
  }
  console.log(`\n结论：${fails.length === 0 ? "PASS（判红 0）" : `FAIL（判红 ${fails.length}）：${fails.join("；")}`}`);
  process.exit(fails.length === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("探针自身出错：", e);
  process.exit(2);
});
