// B24（revise-deepen/05）真机段二：**浏览器面**——分析渲染 → 确认执行（SSE 进度）
// → 结果（diff 记录 / 验证状态 / 回滚按钮）→ 回滚后文件复原。
//
// 段一（`.scratch/revise-deepen/probe-16-revise-analyze.py`）已用服务端真链证过
// `/api/revise/analyze` 的事件流与载荷形状；本段测页面把真实载荷渲染出来 + 执行 + 回滚。
//
// 脚本姿势（工单 real-acceptance/07）：本轮的折叠+页签 / 长流程轮询两个坑**已固化成
// `.scratch/browser-harness.mjs` 的 `expandCard()` / `pollUntil()`**（本脚本就是它们的
// 回归样本）；四个坑的全文与正确姿势见
// `.scratch/real-acceptance/issues/07-browser-acceptance-pitfalls.md` 与挂账单 01 的
// 「B 组统一前置 · 姿势清单」。本脚本另有两条自己的坑：
//   1. 历史目录 `.contest_context.json` 的 `problem_text` 为空（A9 那次生成走 topic_id 路径）
//      → 必须先在「补题面」框贴题面，分析才不会 400；
//   2. `reviseApply` / `reviseRollback` 各有一层 confirmModal，**不点确认请求根本不发**
//      （服务端日志里只有 analyze 就是这个原因）→ 按按钮文字点。
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { expandCard, pollUntil } from "../browser-harness.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8000";
const REPO = "C:/Users/luoji/Desktop/firstep";
const DIR = `${REPO}/.scratch/real-run/out_2026C_stm32`;
const EVID = `${REPO}/.scratch/revise-deepen`;

const log = [];
const check = (c, m) => log.push((c ? "ok   " : "FAIL ") + m);
const note = (m) => log.push("note " + m);
const sha = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");

const QA = [
  "问：小车的无线通信是否限定为已有的 Zigbee 模块？",
  "答：就用现有 Zigbee DL-20 透传（115200），不额外加别的无线模块。",
  "",
  "问：开锁动作是继电器还是只用 LED 指示？",
  "答：以 LED 指示为准，继电器只做演示联动，不做硬性要求。",
].join("\n");

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
});
const page = await browser.newPage({ viewport: { width: 1418, height: 802 } });
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 240)));
page.on("console", (m) => {
  const t = m.text();
  // 噪音白名单：favicon 404（页面无图标，浏览器自动请求）与探测用的 400/404 资源
  if (m.type() === "error" && /favicon|Failed to load resource/.test(t)) return;
  if (m.type() === "error") pageErrors.push("console: " + t.slice(0, 240));
});

/** 轮询 DOM 直到终态（助手在 .scratch/browser-harness.mjs；超时如实记 note 不静默）。 */
const poll = async (fn, opts) => {
  const out = await pollUntil(page, fn, opts);
  if (out.timeout) note(`轮询超时（${opts.label}）：最后一次观测 ${JSON.stringify(out)}`);
  return out;
};

await page.goto(BASE, { waitUntil: "networkidle" });
// 第 11 步卡默认折叠 + 卡内页签式（坑 1 的姿势）：展开 #card-revise 并切到「修订」页签
const expanded = await expandCard(page, "card-revise", '#revise-tabs .revise-tab[data-tab="revise"]');
note(`展开 card-revise（原折叠=${expanded.wasCollapsed}，页签命中=${expanded.tabFound}）`);
await page.waitForSelector("#btn-revise-load-dir", { state: "visible", timeout: 15000 });
await page.fill("#revise-dir-input", DIR);
await page.click("#btn-revise-load-dir");
await poll(() => ({
  done: !document.getElementById("revise-context").classList.contains("hidden"),
}), { timeoutMs: 40000, every: 800, label: "上下文加载" });

const needProblem = await page.evaluate(
  () => !document.getElementById("revise-problem-fill").classList.contains("hidden"));
if (needProblem) {
  await page.fill("#revise-problem-text", readFileSync(`${REPO}/library/topics/2026C/topic.md`, "utf-8"));
  note("历史目录缺题面 → 补题面框填入 library/topics/2026C/topic.md（原验收场景）");
  await page.evaluate(() => {
    const bs = [...document.querySelectorAll("#revise-problem-fill button")];
    (bs.find((x) => /保存|确认|填入|应用/.test(x.textContent)) || bs[0])?.click();
  });
  await page.waitForTimeout(1200);
}

const mainShaBefore = sha(`${DIR}/main.c`);
const ctxBefore = JSON.parse(readFileSync(`${DIR}/.contest_context.json`, "utf-8"));

// ---------- ① 分析：kick off 不 await + 轮询 DOM（坑 3 的姿势） ----------
await page.fill("#revise-qa-new", QA);
await page.evaluate(() => {
  import("/js/ui/generate-revise.js").then((m) => m.reviseAnalyze());
});
const analysisPoll = await poll(() => ({
  done: !document.getElementById("revise-analysis").classList.contains("hidden")
    || document.getElementById("revise-analyze-msg").textContent.trim() !== "",
  st: document.getElementById("revise-analyze-status").textContent,
  msg: document.getElementById("revise-analyze-msg").textContent,
}), { timeoutMs: 300000, every: 3000, label: "分析" });
const analysis = await page.evaluate(() => ({
  hidden: document.getElementById("revise-analysis").classList.contains("hidden"),
  text: document.getElementById("revise-analysis").textContent,
  msg: document.getElementById("revise-analyze-msg").textContent,
  execVisible: !document.getElementById("revise-exec-box").classList.contains("hidden"),
  discardVisible: !document.getElementById("btn-revise-discard").classList.contains("hidden"),
  confirmed: document.getElementById("revise-confirmed-slugs").value,
  rows: document.querySelectorAll("#revise-analysis .item").length,
  chips: document.querySelectorAll("#revise-analysis .chip").length,
}));
check(analysis.msg === "", `分析无错误提示（msg=${JSON.stringify(analysis.msg)}）`);
check(!analysis.hidden, `分析区渲染出来（轮询终态 st=${JSON.stringify(analysisPoll.st)}）`);
check(/逐条影响结论/.test(analysis.text), "渲染含「逐条影响结论」标题");
check(/模块集 diff/.test(analysis.text), "渲染含「模块集 diff」卡");
check(/新增/.test(analysis.text) && /移除/.test(analysis.text) && /不变/.test(analysis.text),
  "diff 卡三栏（新增 / 移除 / 不变）都在");
check(/平台警告/.test(analysis.text), "渲染含「平台警告」段");
check(/建议模块集/.test(analysis.text), "渲染含「建议模块集」段");
check(analysis.rows >= 3, `渲染出 ${analysis.rows} 个条目块（逐条影响 + diff 卡 + …）`);
check(analysis.chips >= 3, `渲染出 ${analysis.chips} 个 chip（模块名 / 标记）`);
check(analysis.discardVisible, "「放弃」按钮出现");
check(analysis.confirmed.trim().length > 0, `建议模块集已预填确认框（${analysis.confirmed.slice(0, 50)}…）`);
writeFileSync(`${EVID}/verify-16-revise-render-analysis.txt`, analysis.text, "utf-8");
await page.evaluate(() => document.getElementById("revise-analysis").scrollIntoView({ block: "center" }));
await page.waitForTimeout(400);
await page.screenshot({ path: `${EVID}/shot-16-revise-analysis.png`, fullPage: false });

// ---------- ② 确认执行（真 SSE：备份 → 重生成 → 编译验证） ----------
const progress = [];
const timer = setInterval(async () => {
  const t = await page.evaluate(() => ({
    st: document.getElementById("revise-exec-status").textContent,
    res: document.getElementById("revise-result").textContent.length,
  })).catch(() => null);
  if (t) {
    const line = `${t.st} | resultLen=${t.res}`;
    if (progress[progress.length - 1] !== line) progress.push(line);
  }
}, 1000);
await page.evaluate((slugs) => {
  const input = document.getElementById("revise-confirmed-slugs");
  if (!input.value.trim()) input.value = slugs.join(", ");
  import("/js/ui/generate-revise.js").then((m) => m.reviseApply());
}, ctxBefore.slugs);
// reviseApply 内部先弹「确认执行修订？」模态（覆盖式重生成明示）——不点确认就
// 根本不会发 POST（上一版没点，于是服务端日志里只有 analyze，执行阶段空转）。
const confirmSeen = await page.waitForSelector(
  '[data-confirm-value="1"], .confirm-modal, .modal', { timeout: 20000 },
).then(() => true).catch(() => false);
note(`确认弹窗出现=${confirmSeen}`);
if (confirmSeen) {
  await page.locator('[data-confirm-value="1"]').first().click({ timeout: 8000 })
    .catch(async () => {
      await page.locator(".confirm-modal button, .modal button")
        .filter({ hasText: /执行修订|确认|确定/ }).first().click({ timeout: 8000 })
        .catch(() => {});
    });
}
const applyPoll = await poll(() => ({
  done: !document.getElementById("revise-result").classList.contains("hidden")
    || document.getElementById("revise-exec-msg").textContent.trim() !== ""
    || !document.getElementById("btn-revise-rollback").classList.contains("hidden"),
  st: document.getElementById("revise-exec-status").textContent,
  msg: document.getElementById("revise-exec-msg").textContent,
}), { timeoutMs: 900000, every: 4000, label: "执行" });
clearInterval(timer);
const applyResult = await page.evaluate(() => ({
  st: document.getElementById("revise-exec-status").textContent,
  msg: document.getElementById("revise-exec-msg").textContent,
  resultHidden: document.getElementById("revise-result").classList.contains("hidden"),
  resultText: document.getElementById("revise-result").textContent,
  rollbackVisible: !document.getElementById("btn-revise-rollback").classList.contains("hidden"),
}));
writeFileSync(`${EVID}/verify-16-revise-progress.txt`,
  "执行阶段状态轨迹（去重相邻相同）：\n" + progress.join("\n") + "\n", "utf-8");

check(applyResult.msg === "", `执行无错误提示（msg=${JSON.stringify(applyResult.msg)}）`);
check(!applyResult.resultHidden, `结果区渲染出来（轮询终态 st=${JSON.stringify(applyPoll.st)}）`);
check(/diff|备份|验证|模块/.test(applyResult.resultText), "结果区含 diff 记录 / 验证状态文本");
check(applyResult.rollbackVisible, "回滚按钮可见（有备份）");
check(progress.some((l) => /备份|重生成|编译|深化|完成/.test(l)),
  `SSE 进度出现过备份/重生成/编译验证字样（${progress.length} 个状态行）`);
writeFileSync(`${EVID}/verify-16-revise-render-result.txt`, applyResult.resultText, "utf-8");
await page.evaluate(() => document.getElementById("revise-result").scrollIntoView({ block: "center" }));
await page.waitForTimeout(400);
await page.screenshot({ path: `${EVID}/shot-16-revise-result.png`, fullPage: false });

// ---------- ③ 回滚 ----------
if (applyResult.rollbackVisible) {
  await page.evaluate(() => {
    import("/js/ui/generate-revise.js").then((m) => m.reviseRollback());
  });
  // 回滚确认模态：confirmText = 「确认回滚」（danger），按**按钮文字**点最稳
  const rbConfirm = await page.waitForSelector(".confirm-modal, .modal", { timeout: 20000 })
    .then(() => true).catch(() => false);
  note(`回滚确认弹窗出现=${rbConfirm}`);
  await page.locator(".confirm-modal button, .modal button")
    .filter({ hasText: /确认回滚|确认|确定/ }).first().click({ timeout: 10000 })
    .catch(() => {});
  await poll(() => ({
    done: /已回滚到备份状态/.test(document.getElementById("revise-exec-status").textContent)
      || /已回滚/.test(document.getElementById("revise-rollback-status").textContent),
    st: document.getElementById("revise-exec-status").textContent,
    rb: document.getElementById("revise-rollback-status").textContent,
  }), { timeoutMs: 90000, every: 1500, label: "回滚" });
} else {
  note("回滚步骤跳过：回滚按钮不可见（执行未产出备份）");
}
const after = await page.evaluate(() => ({
  st: document.getElementById("revise-exec-status").textContent,
  rollbackStatus: document.getElementById("revise-rollback-status").textContent,
  rollbackVisible: !document.getElementById("btn-revise-rollback").classList.contains("hidden"),
}));
const mainShaAfter = sha(`${DIR}/main.c`);
check(mainShaAfter === mainShaBefore,
  `回滚后 main.c sha 复原（before=${mainShaBefore.slice(0, 12)} after=${mainShaAfter.slice(0, 12)}）`);
check(/回滚|恢复/.test(after.st + after.rollbackStatus) || !after.rollbackVisible,
  `回滚状态可见（st=${JSON.stringify(after.st)} / rollbackStatus=${JSON.stringify(after.rollbackStatus)}）`);
check(pageErrors.length === 0,
  `页面零 JS 异常（${pageErrors.length} 条${pageErrors.length ? "：" + pageErrors[0] : ""}）`);

writeFileSync(`${EVID}/verify-16-revise-render.json`, JSON.stringify({
  analysis: { text: analysis.text.slice(0, 6000), confirmed: analysis.confirmed, rows: analysis.rows },
  apply: { ...applyResult, resultText: applyResult.resultText.slice(0, 6000) },
  progress, rollback: { ...after, mainShaBefore, mainShaAfter },
  pageErrors,
}, null, 2), "utf-8");
writeFileSync(`${EVID}/verify-16-revise-render.txt`, log.join("\n") + "\n", "utf-8");

console.log(log.join("\n"));
const fails = log.filter((l) => l.startsWith("FAIL")).length;
console.log(fails ? `FAILURES: ${fails}` : "ALL PASS");
await browser.close();
process.exit(fails ? 1 : 0);
