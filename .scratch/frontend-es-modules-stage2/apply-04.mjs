// 阶段 2 工单 04：母版页 + 更新记录迁 ui/master.js；LLM 用量记录服务迁 ui/usage.js
// 删除范围 = ①母版页 header ~ loadChangelog 末（7268-7807 一带）②用量区段
// （dashes header ~ btn-usage-reset 监听末）③llmPricesDefaults 声明行；
// 另 2 处小改：loadSettings 写入点改 setter、host 顶部 import 两条。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/master.js"'))) throw new Error("master import already present");

// ---- 1) host import：ui/progress.js import 之后插入 usage + master 两行
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/progress.js"')), "progress import");
  lines.splice(i + 1, 0,
    'import { recordLLMUsage, llmPricesDefaults, setLlmPricesDefaults, renderUsageStats } from "/js/ui/usage.js";',
    'import { loadMasters, loadChangelog } from "/js/ui/master.js";');
}

// ---- 2) llmPricesDefaults 声明行 → 注记（所有权迁 ui/usage.js）
{
  const i = must(lines.findIndex((l) => l.startsWith("let llmPricesDefaults = {};")), "llmPricesDefaults let");
  lines[i] = "// llmPricesDefaults（当前生效 LLM 单价表）已迁至 static/js/ui/usage.js（阶段 2 工单 04）：";
  lines.splice(i + 1, 0, "// 写入走 setLlmPricesDefaults（loadSettings），collectLlmPrices 经 import 只读（ESM 活绑定）。");
}

// ---- 3) loadSettings 写入点 → setter
{
  const i = must(lines.findIndex((l) => l.includes("llmPricesDefaults = s.llm_prices || {};")), "llmPricesDefaults write");
  lines[i] = lines[i].replace("llmPricesDefaults = s.llm_prices || {};", "setLlmPricesDefaults(s.llm_prices || {});");
  if (!/setLlmPricesDefaults\(s\.llm_prices \|\| \{\}\);/.test(lines[i])) throw new Error("setter rewrite failed: " + lines[i]);
}

// ---- 4) 母版页区段 → 注记
{
  const a = must(lines.findIndex((l) => l.trim() === "// 母版页"), "母版页 header");
  const b = must(lines.findIndex((l) => l.startsWith("async function loadChangelog()")), "loadChangelog");
  let e = b;
  while (e < lines.length && lines[e] !== "}") e++;
  if (e >= lines.length) throw new Error("loadChangelog end not found");
  const removed = lines.slice(a, e + 1).join(eol);
  for (const n of ["scannedProjects", "stagedDirs", "distPanel", "setStep", "renderReport", "loadMasters", "loadChangelog", "masterCache"]) {
    if (!new RegExp("(function|const|let|async function)\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n + " in removed span");
  }
  if (/collectLlmPrices/.test(removed)) throw new Error("overreach into settings: collectLlmPrices in removed span");
  if (!/btn-confirm/.test(removed)) throw new Error("overreach check: btn-confirm listener missing from removed span");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 母版页（扫描 / 整夹暂存 / 提炼 / 报告 / 母版库 / 更新记录）：全部胶水已迁至",
    "// static/js/ui/master.js（阶段 2 工单 04）；纯件（表格行 / 判定行 / 归档行 /",
    "// 详情 / 文件 URL）在 static/js/fx/master.js。host 只经 tab 分发器调",
    "// loadMasters / loadChangelog（顶部 import）。",
    "// ---------------------------------------------------------------------------",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 5) 用量区段 → 注记
{
  const a = must(lines.findIndex((l) => l.includes("LLM 用量统计（工单 ui-polish-5/02）")), "usage header comment");
  let a0 = a - 1;
  if (!lines[a0].startsWith("// ---")) throw new Error("usage header dash expected: " + lines[a0]);
  const b = must(lines.findIndex((l) => l.includes('$("btn-usage-reset").addEventListener')), "btn-usage-reset");
  let e = b;
  while (e < lines.length && lines[e] !== "});") e++;
  if (e >= lines.length) throw new Error("usage listener end not found");
  const removed = lines.slice(a0, e + 1).join(eol);
  for (const n of ["USAGE_STORE_KEY", "usageSessionAcc", "loadUsageAcc", "currentLlmPrices", "recordLLMUsage", "renderUsageStats"]) {
    if (!new RegExp("(function|const|let)\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n + " in removed span");
  }
  const note = [
    "// ---------------------------------------------------------------------------",
    "// LLM 用量统计（工单 ui-polish-5/02）：记录服务（recordLLMUsage / 单价表 /",
    "// 会话累计与持久化 / reset）已迁至 static/js/ui/usage.js（阶段 2 工单 04）；",
    "// 纯计算在 fx/llm.js。host 经顶部 import 调 recordLLMUsage（推荐 / 修复 / 修订流）",
    "// 与 renderUsageStats（设置 tab 分发器）。",
    "// ---------------------------------------------------------------------------",
  ];
  lines.splice(a0, e - a0 + 1, ...note);
}

// ---- 校验
const out = lines.join(eol);
const moved = [
  "scannedProjects", "currentReport", "stagedDirs", "projectDirs", "renderStagedDirs",
  "PHASE_LABEL", "MAX_LOG_LINES", "distPanel", "setStep", "updateBatch",
  "addLogLine", "addBatchLine", "startProgress", "finishProgress", "failProgress",
  "decisionItem", "archiveItem", "renderReport", "openMasterDeleteConfirm",
  "loadMasterFileState", "renderMasterFileContent", "openMasterFile", "openMasterDetail",
  "loadMasters", "loadChangelog", "masterCache", "masterFileCache",
  "USAGE_STORE_KEY", "usageBase", "usageSessionAcc", "loadUsageAcc",
  "currentLlmPrices", "recordLLMUsage", "renderUsageStats", "llmPricesDefaults",
];
for (const n of moved) {
  if (new RegExp("(function|const|let)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
{
  const inst = out.match(/makeProgressPanel\(\{/g) || [];
  if (inst.length !== 1) throw new Error("expected 1 makeProgressPanel instance in host (recPanel), got " + inst.length);
}
// host 仍需引用的调用点都在
for (const frag of ['recordLLMUsage(ev)', 'recordLLMUsage(data)', 'renderUsageStats();', 'loadMasters();', 'loadChangelog();']) {
  if (!out.includes(frag)) throw new Error("host call site vanished: " + frag);
}

writeFileSync(p, out, "utf8");
console.log("OK: master page + usage service moved; imports updated; lines now", lines.length);
