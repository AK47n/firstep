// 阶段 2 工单 03：index.html 进度面板工厂迁 ui/progress.js；fmtClock/fmtDuration 迁 fx/core.js
// 删除范围 = 注释块（7 行）+ makeProgressPanel + fmtClock + fmtDuration（含中间空行），
// setStep 及之后的 distPanel 专属胶水原地保留（属工单 04 M 簇）。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);

if (lines.some((l) => l.includes('from "/js/ui/progress.js"'))) throw new Error("progress import already present");

// ---- 1) core.js import 行补充 fmtDuration（host 主体 finishProgress @7559 仍引用它）
{
  const i = lines.findIndex((l) => l.includes('from "/js/fx/core.js"'));
  if (i < 0) throw new Error("core import not found");
  if (!/^import \{ esc, formatSize \} from "\/js\/fx\/core\.js";$/.test(lines[i])) {
    throw new Error("core import shape unexpected: " + lines[i]);
  }
  lines[i] = lines[i].replace("{ esc, formatSize }", "{ esc, formatSize, fmtDuration }");
}

// ---- 2) host import 行：app.js import 之后插入 makeProgressPanel
{
  const i = lines.findIndex((l) => l.includes('from "/js/app.js"'));
  if (i < 0) throw new Error("app import not found");
  lines.splice(i + 1, 0, 'import { makeProgressPanel } from "/js/ui/progress.js";');
}

// ---- 3) 删除共享件块（注释 7 行 + makeProgressPanel + fmtClock + fmtDuration）
{
  const a = lines.findIndex((l) => l.includes("进度面板模块（工单 A 深化）"));
  if (a < 0) throw new Error("progress comment not found");
  if (!lines[a].startsWith("// =====")) throw new Error("progress comment must start with dashes: " + lines[a]);
  const dfn = lines.findIndex((l) => l.startsWith("function fmtDuration(sec)"));
  if (dfn < 0) throw new Error("fmtDuration not found");
  let b = dfn;
  while (b < lines.length && lines[b] !== "}") b++;
  if (b >= lines.length) throw new Error("fmtDuration end not found");
  const removed = lines.slice(a, b + 1).join(eol);
  for (const n of ["makeProgressPanel", "fmtClock", "fmtDuration"]) {
    if (!new RegExp("function\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n + " in removed span");
  }
  if (/function setStep\b/.test(removed)) throw new Error("overreach: setStep in removed span");
  const note = [
    "// ===== 进度面板工厂（阶段 2 工单 03）：makeProgressPanel 已迁至",
    "// static/js/ui/progress.js；fmtClock / fmtDuration 已迁至 static/js/fx/core.js。=====",
  ];
  lines.splice(a, b - a + 1, ...note);
}

// ---- 校验
const out = lines.join(eol);
for (const n of ["makeProgressPanel", "fmtClock", "fmtDuration"]) {
  if (new RegExp("(function|const)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
{
  const inst = out.match(/makeProgressPanel\(\{/g) || [];
  if (inst.length !== 2) throw new Error("expected 2 makeProgressPanel instance sites, got " + inst.length);
}
for (const n of ["setStep", "addLogLine", "addBatchLine", "updateBatch", "startProgress", "finishProgress", "failProgress", "MAX_LOG_LINES", "PHASE_LABEL", "currentReport", "renderReport"]) {
  if (!new RegExp("(function|const|let)\\s+" + n + "\\b").test(out)) throw new Error("M-cluster symbol vanished: " + n);
}

writeFileSync(p, out, "utf8");
console.log("OK: progress factory removed; imports updated; lines now", lines.length);
