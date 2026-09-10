// B24（revise-deepen/05）剩余三处真机验收：分析 → 影响/diff 卡、确认执行 → SSE 进度、
// 结果 diff / 验证状态 / 回滚。真 LLM + 真工具链，舞台 = A9 产出的真实工程。
//
// 前置：webapp 起在 8000；`.scratch/real-run/out_2026C_stm32` 是第十五/十六轮 A9 的
// 真实生成工程（含 .contest_context.json）。本脚本会**真改这个工程**（修订 = 覆盖式
// 重生成 + 整树备份），收尾用产品「回滚本次修订」把它恢复原状（sha 比对兜底）。
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";

const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8000";
const DIR = "C:/Users/luoji/Desktop/firstep/.scratch/real-run/out_2026C_stm32";
const EVID = "C:/Users/luoji/Desktop/firstep/.scratch/revise-deepen";
mkdirSync(EVID, { recursive: true });

const log = [];
const check = (c, m) => log.push((c ? "ok   " : "FAIL ") + m);
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
await page.goto(BASE, { waitUntil: "networkidle" });
// 修订卡默认折叠（`.collapsed` → 内容 display:none）：先等元素**挂载**再展开卡，
// 最后才等可见（playwright 的 waitForSelector 默认等 visible，折叠态会一直等）
await page.waitForSelector("#btn-revise-load-dir", { state: "attached", timeout: 20000 });
await page.evaluate(() => {
  document.getElementById("card-revise")?.classList.remove("collapsed");
  // 第 11 步卡内是页签式（step11-tabs-ui/01）：修订分区默认隐藏，
  // 必须点 `.revise-tab[data-tab="revise"]` 才 display:block
  const tab = document.querySelector('#revise-tabs .revise-tab[data-tab="revise"]');
  if (tab) tab.click();
});
await page.waitForFunction(
  () => !document.getElementById("revise-panel-revise").classList.contains("hidden"),
  null,
  { timeout: 15000 },
);
await page.waitForSelector("#btn-revise-load-dir", { state: "visible", timeout: 10000 });
await page.fill("#revise-dir-input", DIR);
await page.click("#btn-revise-load-dir");
await page.waitForFunction(
  () => document.getElementById("revise-load-status").textContent.includes("加载"),
  null,
  { timeout: 30000 },
);
await page.waitForFunction(
  () => !document.getElementById("revise-analyze-box").classList.contains("hidden"),
  null,
  { timeout: 30000 },
);

// 历史目录的 .contest_context.json 里 problem_text 为空（A9 那次生成走 topic_id 路径，
// 题面没随载荷落进清单）→ 加载后出现「补题面」输入框；不补分析必然 400
// 「缺少赛题原文」。这正是 B24 原验收项「历史目录补题面全流程」的场景。
// **必须等补题面区真的可见**（加载完成的渲染是异步的，上一版只等 status 文案就检查，
// 结果 needProblem=false 漏掉了补题面 → 分析 400 → 后续全红）。
await page.waitForSelector("#revise-problem-fill", { state: "visible", timeout: 15000 })
  .catch(() => {});
const needProblem = await page.evaluate(
  () => !document.getElementById("revise-problem-fill").classList.contains("hidden"),
);
if (needProblem) {
  const topicMd = readFileSync(
    "C:/Users/luoji/Desktop/firstep/library/topics/2026C/topic.md", "utf-8");
  await page.fill("#revise-problem-text", topicMd);
  log.push("note 历史目录缺题面 → 已用补题面输入框填入 library/topics/2026C/topic.md（原验收项场景）");
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll("#revise-problem-fill button")];
    const b = btns.find((x) => /保存|确认|填入|应用/.test(x.textContent)) || btns[0];
    if (b) b.click();
  });
  await page.waitForTimeout(1500);
} else {
  log.push("note 补题面区不可见（题面已在上下文里）——直接进分析");
}
// 分析前核对「加载到的题面长度」，避免带着空题面去打端点（400 会污染后续断言）
const problemLen = await page.evaluate(
  () => document.getElementById("revise-problem").textContent.trim().length,
);
log.push(`note 上下文题面长度 = ${problemLen} 字符`);

const mainShaBefore = sha(`${DIR}/main.c`);
const ctxBefore = JSON.parse(readFileSync(`${DIR}/.contest_context.json`, "utf-8"));

// ---------- ① 分析 → 影响结论 + diff 卡 + 警告变化 ----------
await page.fill("#revise-qa-new", QA);
// 诊断：点分析后每 5s 记一行状态（本轮前几次都卡在「没等到分析终态」，
// 现场看不到状态行/错误行 → 无法定性；先加观测面再谈结论）
const trace = [];
const traceTimer = setInterval(async () => {
  const t = await page.evaluate(() => ({
    st: document.getElementById("revise-analyze-status").textContent,
    msg: document.getElementById("revise-analyze-msg").textContent,
    hidden: document.getElementById("revise-analysis").classList.contains("hidden"),
    len: document.getElementById("revise-analysis").textContent.length,
    busy: document.getElementById("btn-revise-analyze").disabled,
  })).catch(() => null);
  if (t) trace.push(`t+${trace.length * 5}s st=${JSON.stringify(t.st)} msg=${JSON.stringify(t.msg)} analysisHidden=${t.hidden} analysisLen=${t.len} busy=${t.busy}`);
}, 5000);
await page.click("#btn-revise-analyze");
await page.waitForFunction(
  () => !document.getElementById("revise-analysis").classList.contains("hidden")
    || document.getElementById("revise-analyze-msg").textContent.trim() !== "",
  null,
  { timeout: 600000 },
).catch(async (e) => {
  clearInterval(traceTimer);
  writeFileSync(`${EVID}/verify-16-revise-analyze-trace.txt`,
    "分析阶段超时（观测轨迹）：\n" + trace.join("\n") + "\n", "utf-8");
  await page.screenshot({ path: `${EVID}/shot-16-revise-analyze-timeout.png`, fullPage: false });
  throw e;
});
clearInterval(traceTimer);
writeFileSync(`${EVID}/verify-16-revise-analyze-trace.txt`,
  "分析阶段观测轨迹：\n" + trace.join("\n") + "\n", "utf-8");
const analysis = await page.evaluate(() => ({
  html: document.getElementById("revise-analysis").innerHTML,
  text: document.getElementById("revise-analysis").textContent,
  msg: document.getElementById("revise-analyze-msg").textContent,
  execVisible: !document.getElementById("revise-exec-box").classList.contains("hidden"),
  discardVisible: !document.getElementById("btn-revise-discard").classList.contains("hidden"),
}));
check(analysis.msg === "", `分析无错误提示（msg=${JSON.stringify(analysis.msg)}）`);
check(/影响|结论|无需|模块/.test(analysis.text), "分析区有影响结论文本");
check(analysis.execVisible, "确认执行区出现（分析成功 → 可确认）");
check(analysis.discardVisible, "「放弃」按钮出现（可放弃）");
const hasDiffCard = /diff|增|删|不变|模块集/.test(analysis.text);
check(hasDiffCard, "diff 卡文本可见（增/删/不变/模块集）");
writeFileSync(`${EVID}/verify-16-revise-analysis.txt`, analysis.text, "utf-8");
await page.screenshot({ path: `${EVID}/shot-16-revise-analysis.png`, fullPage: false });

// ---------- ② 确认执行 → SSE 进度全程 ----------
// 记录 SSE 进度文案变化（轮询 status 元素，落盘轨迹）
const progress = [];
const stop = { v: false };
const poll = (async () => {
  while (!stop.v) {
    const t = await page.evaluate(() => ({
      exec: document.getElementById("revise-exec-status").textContent,
      rollback: document.getElementById("revise-rollback-status").textContent,
      result: !document.getElementById("revise-result").classList.contains("hidden"),
    })).catch(() => null);
    if (t) {
      const line = `${t.exec} | ${t.rollback} | result=${t.result}`;
      if (progress[progress.length - 1] !== line) progress.push(line);
      if (t.result) break;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
})();
// 先确认执行按钮真的可见（页签/折叠任一没生效都会静默点空）
await page.waitForSelector("#btn-revise-apply", { state: "visible", timeout: 15000 });
// 确认模块集：分析成功后该输入框未填（空 → apply 会 400「请填写确认模块集」）。
// 用**加载时读到的原始模块集**（= 不变更模块集的最小修订，正合 B24 的「无变化」分支语义）。
await page.evaluate((slugs) => {
  const input = document.getElementById("revise-confirmed-slugs");
  if (input && !input.value.trim()) input.value = slugs.join(", ");
}, ctxBefore.slugs);
await page.click("#btn-revise-apply");
// 终态判据放宽：结果区可见 / 错误行非空 / 状态行出现过「完成|验证|已修订|回滚」/
// 回滚按钮亮起——命中任一即视为执行结束（再看具体断言）
await page.waitForFunction(
  () => {
    const res = document.getElementById("revise-result");
    const msg = document.getElementById("revise-exec-msg").textContent.trim();
    const st = document.getElementById("revise-exec-status").textContent;
    const rb = !document.getElementById("btn-revise-rollback").classList.contains("hidden");
    return !res.classList.contains("hidden") || msg !== "" || rb
      || /完成|验证|已修订|已生成|回滚|失败/.test(st);
  },
  null,
  { timeout: 900000 },
);
stop.v = true;
await poll.catch(() => {});
const execState = await page.evaluate(() => ({
  exec: document.getElementById("revise-exec-status").textContent,
  resultText: document.getElementById("revise-result").textContent,
  msg: document.getElementById("revise-exec-msg").textContent,
  rollbackVisible: !document.getElementById("btn-revise-rollback").classList.contains("hidden"),
}));
writeFileSync(`${EVID}/verify-16-revise-progress.txt`,
  "SSE/状态文案轨迹（去重相邻相同）：\n" + progress.join("\n") + "\n", "utf-8");
check(progress.length >= 2, `SSE 进度轨迹有推进（${progress.length} 个不同状态行）`);
check(/backup|备份|重生成|深化|编译|验证|完成/.test(progress.join("\n")), "进度轨迹含备份/重生成/编译验证字样");
check(execState.msg === "", `执行无错误提示（msg=${JSON.stringify(execState.msg)}）`);
check(execState.resultText.length > 0, "结果区有内容（diff 记录 / 验证状态）");
check(execState.rollbackVisible, "回滚按钮可见（有备份）");

// ---------- ③ 回滚 → 文件恢复 + 状态刷新 ----------
if (execState.rollbackVisible) {
  await page.click("#btn-revise-rollback");
  await page.waitForSelector(".confirm-modal, .modal, [data-confirm-value]", { timeout: 10000 })
    .catch(() => {});
  await page.locator('[data-confirm-value="1"]').first().click({ timeout: 8000 }).catch(async () => {
    await page.locator(".confirm-modal button, .modal button")
      .filter({ hasText: /确认|回滚|确定/ }).first().click({ timeout: 8000 }).catch(() => {});
  });
  await page.waitForTimeout(2500);
} else {
  // 回滚按钮没亮 = 执行没产出备份（上面已记 FAIL），此处不硬点不可见元素
  log.push("note 回滚步骤跳过：回滚按钮不可见（执行未产出备份）");
}
const after = await page.evaluate(() => ({
  rollbackStatus: document.getElementById("revise-rollback-status").textContent,
  rollbackVisible: !document.getElementById("btn-revise-rollback").classList.contains("hidden"),
}));
const mainShaAfter = sha(`${DIR}/main.c`);
check(mainShaAfter === mainShaBefore, `回滚后 main.c sha 复原（before=${mainShaBefore.slice(0, 12)} after=${mainShaAfter.slice(0, 12)}）`);
check(/回滚|恢复/.test(after.rollbackStatus) || !after.rollbackVisible,
  `回滚状态可见（${JSON.stringify(after.rollbackStatus)}）`);
writeFileSync(`${EVID}/verify-16-revise-live.json`, JSON.stringify({
  analysis: { text: analysis.text.slice(0, 4000), execVisible: analysis.execVisible },
  progress, execState: { exec: execState.exec, resultText: execState.resultText.slice(0, 4000) },
  rollback: { ...after, mainShaBefore, mainShaAfter },
  ctxSlugsBefore: ctxBefore.slugs,
}, null, 2), "utf-8");

writeFileSync(`${EVID}/verify-16-revise-live.txt`, log.join("\n") + "\n", "utf-8");
console.log(log.join("\n"));
const fails = log.filter((l) => l.startsWith("FAIL")).length;
console.log(fails ? `FAILURES: ${fails}` : "ALL PASS");
await browser.close();
process.exit(fails ? 1 : 0);
