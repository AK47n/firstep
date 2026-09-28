// .scratch/ui-density-sitewide/probe-05c-shot-settings-content.mjs —— 设置页「**有内容**」态整页图。
//
// 为什么还要一支：`probe-02-shot.mjs` 只点页签，拍到的设置页里 **体检结果 / 更新结果 / 下载进度
// 全是空的**（它们要点了按钮、并且要联网才出内容）。而 05 单改的正是这几块的观感
// （更新结果块的"数值优先于标签"、体检行的三档重量、失败提示的告警块、去框后的 wf 数据块）。
//
// 怎么造出这些态而**不打网络**：调**产品自己的纯渲染函数**（`fx/env.js` 的 `envCheckStatusHTML`、
// `fx/update.js` 的 `updateCheckCardHTML`、`fx/materials-update.js` 的 `materialsCheckCardHTML` /
// `materialsProgressHTML`、`fx/full-update.js` 的 `fullCheckCardHTML`），喂与 `tests/js/*.test.mjs`
// 同形的夹具数据——渲染路径是产品那一条，数据是夹具（与浏览器门禁的路由桩同一种思路）。
//
// 两处**不是**产品渲染路径，如实说明：
//   · 「最近 LLM 工作流」那段 HTML 由 `ui/settings.js` 内联产出（没有导出纯函数），这里照它的
//     形状复刻标记，只为看**去框之后**那块数据的观感；
//   · `#settings-msg` 直接写 `textContent`（产品就是 `textContent` + `classList` 写的），
//     这里做两态：**失败**（`error`）与**保存成功**（`error ok` 并存——`ui/settings.js` 成功时
//     只 add("ok")、不摘 error；CSS 侧靠 `:not(.ok)` 认这一态，这两个态都要拍下来给它作证）。
//
// 用的是同一套真后端夹具（`tests/browser/server.mjs`）：真库真母版、端口内核分配、跑完自收。
// ⚠ 纪律同其它探针：不要与全量 pytest 同时跑。
//
//     node .scratch/ui-density-sitewide/probe-05c-shot-settings-content.mjs 05-after dark
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const HERE = fileURLToPath(new URL("./", import.meta.url));
const OUT = join(HERE, "shots");
const TAG = process.argv[2] || "shot";
const THEME = process.argv[3] || "dark";
const VIEWPORT = { width: Number(process.env.SHOT_WIDTH || 1600), height: 1000 };

// 夹具（形状与 tests/js/env-check-center.test.mjs 的 status 一致）：三种重量都要出现——
// 绿（API 已配 / 库目录在）/ 黄（两条 LLM 通道待检查）/ 红（mspm0 工具链没找到、参考库目录不在）
const ENV_STATUS = {
  api_configured: true,
  llm: { base_url: "https://api.deepseek.com", model: "deepseek-chat", local_llm_base_url: "" },
  toolchains: {
    stm32: { found: true, path: "C:\\Keil5\\Core\\UV4\\UV4.exe", override: true },
    mspm0: { found: false, path: null, override: false },
  },
  ccs_tools: {
    sdk: { found: true, path: "C:\\ti\\ccs2051\\mspm0_sdk_2_10_00_04", root: "C:\\ti\\ccs2051", override: false },
    compiler: { found: false, path: null, root: null, override: false },
    sysconfig: { found: true, path: "C:\\ti\\ccs2051\\sysconfig_1.26.2\\sysconfig_cli.bat", root: "C:\\ti\\ccs2051", override: true },
  },
  library_dirs: {
    topic: { dir: "C:\\libs\\topics", exists: true, writable: true },
    reference: { dir: "C:\\libs\\references", exists: false, writable: false },
    pdf: { dir: "C:\\sources\\materials", exists: true, writable: true },
  },
  platforms: [
    { id: "stm32", name: "STM32F103C8T6", status: "ready" },
    { id: "mspm0", name: "MSPM0G3507", status: "no-master" },
  ],
  module_library: { dir: "C:\\libs\\modules", exists: true, count: 26, error: null },
  masters_dir: { dir: "C:\\libs\\masters", exists: true },
  output_dir: { dir: "C:\\Users\\me\\Desktop", exists: true, writable: true },
};
const TEXT_CH = { ok: true, data: { model: "deepseek-chat", elapsed_ms: 812, reply: "PONG" } };
const VISION_CH = { ok: false, data: { error: "连接超时（自检用当前填写参数真实调用一次）" } };
const UPDATE_CHECK = {
  update_available: true, latest_version: "1.3.2", current_version: "1.3.1",
  size_bytes: 12_345_678, release_notes: "更新面板体量数字与实测对齐\n修复骨架自检的一处误报",
};
const MATERIALS_CHECK = {
  latest_version: "2026-09-27", current_version: "2026-09-20", update_available: true,
  total_bytes: 734_003_200, changed_bytes: 51_380_224, batches: 3, files: 1284,
  message: "有 3 个批次变化，共约 49 MB",
};
const MATERIALS_STATUS = {
  state: "downloading", total_bytes: 51_380_224, total_downloaded_bytes: 20_971_520,
  speed_bps: 5_452_595, parts: [
    { name: "materials-batch-01.7z", total_bytes: 20_971_520, downloaded_bytes: 20_971_520, ok: true },
    { name: "materials-batch-02.7z", total_bytes: 30_408_704, downloaded_bytes: 0, ok: false },
  ],
};
const FULL_CHECK = {
  latest_version: "1.3.2", current_version: "1.3.1", update_available: true,
  total_bytes: 838_860_800, parts: 3, message: "完整包 800 MB，分 3 卷",
};
// 「最近 LLM 工作流」那块数据块（标记照 ui/settings.js 的 renderRecentWorkflows 复刻）
const WF_MARKUP = `
  <div class="recent-wf-summary">
    <div><span class="wf-name">recommend</span> <span class="wf-status-ok">成功</span>
      <span class="muted">wf_20260928_2118</span></div>
    <div class="muted">4 次调用（本地 1 / DeepSeek 3）· 耗时 12.4s · 请求 18.2 KB · 估算 ¥0.0132</div>
    <div class="recent-wf-calls">
      <div class="call-row">preread · deepseek-chat · 2.1s · 5.4 KB · ¥0.0031</div>
      <div class="call-row">module_intro · local:qwen2.5-coder:7b · 1.8s · 0 B · ¥0.0000</div>
    </div>
  </div>`;

mkdirSync(OUT, { recursive: true });
const server = await startServer();
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.on("dialog", (d) => d.dismiss());
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  if (THEME === "light") {
    await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });
  }
  await page.click('nav button[data-tab="settings"]');
  await page.waitForTimeout(800);

  // **默认态先量一次**（评审 Standards 抓到的洞：本探针原先只造"失败态"与"成功态"，
  // 而 `#settings-msg` 的初始类就是 `error`、内容为空 —— 05d 那条告警块会让页面**一打开**
  // 就挂着一条空红框）。这里把它钉成断言：空态**不许有框**。
  const emptyState = await page.evaluate(() => {
    const msg = document.getElementById("settings-msg");
    const cs = getComputedStyle(msg);
    return { cls: msg.className, textLen: (msg.textContent || "").trim().length,
             border: cs.borderTopWidth, box: Math.round(msg.getBoundingClientRect().width) };
  });
  console.log("默认（空）态：", JSON.stringify(emptyState));
  if (emptyState.textLen === 0 && emptyState.border !== "0px") {
    throw new Error(`空态挂着告警框（border=${emptyState.border}，宽 ${emptyState.box}）—— ` +
      `页面一打开就有；规则缺 \`:not(:empty)\``);
  }

  const filled = await page.evaluate(async ([envStatus, textCh, visionCh, upd, mat, matStatus, full, wf]) => {
    const env = await import("/js/fx/env.js");
    const update = await import("/js/fx/update.js");
    const matMod = await import("/js/fx/materials-update.js");
    const fullMod = await import("/js/fx/full-update.js");
    document.getElementById("env-check-results").innerHTML = env.envCheckStatusHTML(envStatus, textCh, visionCh);
    document.getElementById("update-results").innerHTML = update.updateCheckCardHTML(upd);
    document.getElementById("materials-update-results").innerHTML =
      matMod.materialsCheckCardHTML(mat) + matMod.materialsProgressHTML(matStatus);
    document.getElementById("full-update-results").innerHTML = fullMod.fullCheckCardHTML(full);
    document.getElementById("recent-workflows").innerHTML = wf;
    // 失败态（产品就是 textContent + classList 写的）：红框告警块那一态
    const msg = document.getElementById("settings-msg");
    msg.textContent = "保存失败：配置文件被占用（另一个 firstep 正在运行），请关掉它再试。";
    return {
      errRows: document.querySelectorAll(".env-row .env-badge.env-err").length,
      warnRows: document.querySelectorAll(".env-row .env-badge.env-warn").length,
      okRows: document.querySelectorAll(".env-row .env-badge.env-ok").length,
      updateBlock: !!document.querySelector(".update-result b"),
      wfBlock: !!document.querySelector(".recent-wf-summary"),
      msgBox: getComputedStyle(msg).borderTopWidth + " " + getComputedStyle(msg).borderTopColor,
    };
  }, [ENV_STATUS, TEXT_CH, VISION_CH, UPDATE_CHECK, MATERIALS_CHECK, MATERIALS_STATUS, FULL_CHECK, WF_MARKUP]);
  console.log("注入读数：", JSON.stringify(filled));
  if (!filled.errRows || !filled.warnRows || !filled.okRows) {
    throw new Error("三档体检行没造齐（err/warn/ok 都要有）——截图会缺证据，停手");
  }
  if (!filled.updateBlock) throw new Error("更新结果块没渲染出来（.update-result b 找不到）");

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-settings-content-top.png`) });
  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-settings-content-full.png`), fullPage: true });
  console.log("shot:", join(OUT, `${TAG}-${THEME}-settings-content-full.png`));

  // ① 体检结果那一段（三档重量 + 失败行的左条）
  for (const [i, sel] of ["#env-check-results", "#update-results", "#recent-workflows"].entries()) {
    const el = page.locator(sel).first();
    if (!(await el.count())) { console.log(`  ⚠ 找不到 ${sel}`); continue; }
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(250);
    const p = join(OUT, `${TAG}-${THEME}-settings-content-seg${i + 1}.png`);
    await page.screenshot({ path: p });
    console.log("seg:", p, `(${sel})`);
  }

  // ② **保存成功**那一态：`ui/settings.js` 成功时只 add("ok")、不摘 error ——
  //    CSS 靠 `:not(.ok)` 认这一态；这里把它拍下来，免得"成功提示被装进红框"这种回归没人看见
  const okState = await page.evaluate(() => {
    const msg = document.getElementById("settings-msg");
    msg.classList.add("ok");
    msg.textContent = "已保存，立即生效。";
    const cs = getComputedStyle(msg);
    return { classes: msg.className, border: cs.borderTopWidth, bg: cs.backgroundColor, color: cs.color };
  });
  console.log("保存成功态：", JSON.stringify(okState));
  if (okState.border !== "0px") {
    throw new Error(`保存成功态仍然带着告警块的框（border=${okState.border}）——:not(.ok) 那条没生效`);
  }
  await page.locator("#settings-msg").scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  await page.screenshot({ path: join(OUT, `${TAG}-${THEME}-settings-content-saved.png`) });
  console.log("shot:", join(OUT, `${TAG}-${THEME}-settings-content-saved.png`));

  await page.close();
} finally {
  await browser.close();
  await server.stop();
}
