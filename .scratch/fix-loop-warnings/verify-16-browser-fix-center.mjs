// 修复中心真机验收（第十六轮）：A11 前端（首编超时即停）+ A2/A3（横幅四态 +
// 错误列表）+ B26（注入未用变量 → 自动续跑修复轮 → 复编 0 错 0 警）。
//
// 前置：webapp 起在 8000；建议先跑过一次本目录的 A 组链路，否则本脚本会自己
// 通过页面内的真实「生成」流程造一个 stm32 工程（topic 2026C，不烧推荐额度：
// slugs/main_c 从 .scratch/real-run/out_2026C_stm32/.contest_context.json 读）。
//
// 姿势（第十四/十五轮坑位）：
// - Chrome 用 playwright 自起 headless（不需 CDP 端口），每场景重新 goto；
// - 点按钮用 playwright 的真实点击（可信事件）；不用 element.click()；
// - 改类后读样式前等落定；
// - Mock 走 page.route（A11 场景只 mock /api/compile，不动真编译）。
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8000";
const OUT_DIR = "C:/Users/luoji/Desktop/firstep/.scratch/real-run/out_2026C_stm32";
const CTX = "C:/Users/luoji/Desktop/firstep/.scratch/real-run/out_2026C_stm32/.contest_context.json";
const EVID = "C:/Users/luoji/Desktop/firstep/.scratch/fix-loop-warnings";
mkdirSync(EVID, { recursive: true });

const log = [];
const check = (cond, msg) => log.push((cond ? "ok   " : "FAIL ") + msg);

const ctx = JSON.parse(readFileSync(CTX, "utf-8"));

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
});
const page = await browser.newPage({ viewport: { width: 1418, height: 802 } });

// 页面内统一入口：设置平台 + 输出目录（res-dir 优先于 output-dir）
async function prime() {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForFunction(() => !!document.querySelector("#platforms .platform-card"), { timeout: 20000 });
  await page.evaluate(async (dir) => {
    const mod = await import("/js/ui/generate-recommend.js");
    mod.setChosenPlatform("stm32");
    mod.setSelectedSlugs([]);
    // 输出目录：desktop-topic-output 勾选时 #output-dir 是 disabled（手输模式
    // 才可填）——本脚本走手动目录模式，直接写值 + 清 res-dir（fixInput 优先读
    // res-dir）。用 DOM 赋值而不是 fill：disabled 输入无法 fill。
    const box = document.getElementById("desktop-topic-output");
    if (box) { box.checked = false; box.dispatchEvent(new Event("change", { bubbles: true })); }
    document.getElementById("res-dir").textContent = "";
    document.getElementById("output-dir").value = dir;
  }, OUT_DIR);
  await page.evaluate(() => {
    const card = document.getElementById("card-fix-center");
    if (card) card.scrollIntoView({ block: "center" });
  });
}

const readFixState = () => page.evaluate(() => ({
  bannerClass: document.getElementById("compile-banner").className,
  bannerText: document.getElementById("compile-banner").textContent,
  status: document.getElementById("fix-status").textContent,
  round: document.getElementById("fix-center-round").textContent,
  errMsg: document.getElementById("fix-errors-msg").textContent,
  rows: [...document.querySelectorAll("#fix-results .fix-row, #fix-results > *")]
    .map((el) => el.textContent.trim().slice(0, 120)),
  rollbackHidden: document.getElementById("btn-fix-rollback").classList.contains("hidden"),
  continueHidden: document.getElementById("btn-fix-continue").classList.contains("hidden"),
  logLen: (document.getElementById("fix-center-log").value || "").length,
  busy: document.getElementById("btn-fix-center").disabled,
}));

// ---------------------------------------------------------------------------
// 场景 ①（A11 前端 / compile-verdict-align + cli-init-compile-timeout 前端对偶）：
// 首编超时 → 横幅 fail + 「编译超时…已停止循环」+ **零** fix-errors 调用
// ---------------------------------------------------------------------------
{
  let fixErrorCalls = 0;
  await page.route("**/api/fix-errors", async (route) => {
    fixErrorCalls += 1;
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: error\ndata: {\"message\":\"不该被调用\"}\n\n" });
  });
  await page.route("**/api/compile", async (route) => {
    const body = [
      'event: compile_start\ndata: {}\n\n',
      'event: done\ndata: ' + JSON.stringify({
        platform: "stm32", output_dir: OUT_DIR, exit_code: null,
        error_text: "（超时前的半截输出）", passed: false, timed_out: true,
        project_file: "", command: [], duration: 180.0, parsed_errors: [],
        summary: { errors: 0, warnings: 0 },
      }) + "\n\n",
    ].join("");
    await route.fulfill({ status: 200, contentType: "text/event-stream", body });
  });

  await prime();
  await page.click("#btn-fix-center");
  await page.waitForFunction(
    () => document.getElementById("fix-status").textContent.includes("编译超时"),
    { timeout: 20000 },
  );
  const st = await readFixState();
  check(st.bannerClass === "fail", `A11 前端：横幅态 = fail（实际 ${st.bannerClass}）`);
  check(/超时/.test(st.bannerText), `A11 前端：横幅文案含「超时」（${JSON.stringify(st.bannerText)}）`);
  check(st.status.includes("已停止循环"), "A11 前端：状态行「已停止循环」");
  check(fixErrorCalls === 0, `A11 前端：零 /api/fix-errors 调用（实际 ${fixErrorCalls}）`);
  check(st.rollbackHidden === true, "A11 前端：无备份 → 回滚按钮保持隐藏");
  check(st.busy === false, "A11 前端：结束后按钮恢复可用");
  writeFileSync(`${EVID}/verify-16-browser-a11-timeout.json`, JSON.stringify({ fixErrorCalls, st }, null, 2), "utf-8");
  await page.unroute("**/api/compile");
  await page.unroute("**/api/fix-errors");
}

// ---------------------------------------------------------------------------
// 场景 ②（A2/A3）：真实工程 + 真实 UV4 全量编译，干净产物 → 横幅 success
// 「0 错 0 警」+ 状态行「编译通过 ✅ 0 错 0 警」+ 编译日志有内容
// ---------------------------------------------------------------------------
{
  await prime();
  await page.click("#btn-fix-center");
  await page.waitForFunction(
    () => /编译通过|编译有错|编译有警|超时|未检测到/.test(document.getElementById("fix-status").textContent),
    { timeout: 240000 },
  );
  const st = await readFixState();
  check(st.bannerClass === "success", `A2/A3：干净工程横幅 = success（实际 ${st.bannerClass} / ${JSON.stringify(st.bannerText)}）`);
  check(/0 错 0 警/.test(st.status), `A2/A3：状态行含「0 错 0 警」（${JSON.stringify(st.status)}）`);
  check(st.logLen > 0, `A2/A3：编译日志非空（${st.logLen} 字符）`);
  check(st.errMsg === "", "A2/A3：无错误提示行");
  writeFileSync(`${EVID}/verify-16-browser-a2a3-clean.json`, JSON.stringify(st, null, 2), "utf-8");
  await page.screenshot({ path: `${EVID}/shot-16-fix-banner-success.png`, fullPage: false });
}

// ---------------------------------------------------------------------------
// 场景 ③（B26）：注入 main() 内局部未用变量 → 首编 0 错 1 警（横幅仍 success
// 但状态行进告警轮）→ 真实 AI 修复 → 复编 0 错 0 警
// ---------------------------------------------------------------------------
{
  const files = {
    main: `${OUT_DIR}/main.c`,
  };
  const before = readFileSync(files.main, "utf-8");
  const lines = before.split("\n");
  // 注入点：main() 第一行之后（与 fix-loop-warnings/01 真机红证同款形态）
  const idx = lines.findIndex((l) => /^int\s+main\s*\(/.test(l));
  lines.splice(idx + 2, 0, "    int unused_probe_16 = 1;   /* B26 注警探针 */");
  writeFileSync(files.main, lines.join("\n"), "utf-8");

  await prime();
  await page.click("#btn-fix-center");
  // 终态判据：状态行出现「0 错 0 警」或「已达 3 轮上限」或超时
  await page.waitForFunction(
    () => /0 错 0 警|已达 3 轮上限|超时|未应用任何修复/.test(document.getElementById("fix-status").textContent),
    { timeout: 600000 },
  );
  const st = await readFixState();
  const after = readFileSync(files.main, "utf-8");
  check(!after.includes("unused_probe_16"), "B26：注入行已被 AI 删除（main.c 里不再有 unused_probe_16）");
  check(/0 错 0 警/.test(st.status), `B26：状态行终态「0 错 0 警」（${JSON.stringify(st.status)}）`);
  check(st.rollbackHidden === false, "B26：有备份 → 回滚按钮可见");
  check(/第 1\/3 轮|第 1\/3/.test(st.round) || st.round.length > 0, `B26：轮次条有内容（${JSON.stringify(st.round)}）`);
  writeFileSync(
    `${EVID}/verify-16-browser-b26-warning.json`,
    JSON.stringify({ st, injectedLine: "int unused_probe_16 = 1;", removed: !after.includes("unused_probe_16") }, null, 2),
    "utf-8",
  );
  await page.screenshot({ path: `${EVID}/shot-16-fix-warning-cleared.png`, fullPage: false });
}

writeFileSync(`${EVID}/verify-16-browser-summary.txt`, log.join("\n") + "\n", "utf-8");
console.log(log.join("\n"));
const fails = log.filter((l) => l.startsWith("FAIL")).length;
console.log(fails ? `FAILURES: ${fails}` : "ALL PASS");
await browser.close();
process.exit(fails ? 1 : 0);
