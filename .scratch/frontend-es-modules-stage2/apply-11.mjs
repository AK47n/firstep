// 阶段 2 工单 11：最近生成列表迁 ui/recent.js（renderRecentList / refreshRecent /
// reportRecentStatus / initRecent；readiness 面板 5268-5328 留 host——工单 19 迁）。
// 删除段（物理升序）：最近生成区段头 → initRecent 末。顶部 import 追加。
// 全程 CRLF 感知。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/recent.js"'))) throw new Error("recent import already present");

// ---- 1) host import：settings import 之后追加
{
  const si = must(lines.findIndex((l) => l.includes('from "/js/ui/settings.js"')), "settings import");
  lines.splice(si + 1, 0,
    'import { renderRecentList, refreshRecent, reportRecentStatus, initRecent } from "/js/ui/recent.js";');
}

// ---- 2) 最近生成区段 → 注记（readiness 区段留 host）
{
  const a = must(lines.findIndex((l) => l.startsWith("// 最近生成（工单 recent-jobs/01）")), "recent header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before recent header not found");
  const b = must(lines.findIndex((l) => l.startsWith("// 检查能否生成（工单 a3-readiness-check/01-02）")), "readiness header");
  const dashB = b - 1;
  if (!lines[dashB].startsWith("// ------")) throw new Error("dash before readiness header not found");
  const removed = lines.slice(dashA, dashB).join(eol);
  for (const n of ["renderRecentList", "refreshRecent", "reportRecentStatus", "initRecent"]) {
    if (!new RegExp("(async )?function\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n);
  }
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 最近生成（工单 recent-jobs/01）：renderRecentList / refreshRecent /",
    "// reportRecentStatus / initRecent 已迁至 static/js/ui/recent.js（阶段 2",
    "// 工单 11）；纯件在 fx/recent.js（工单 08 迁：recentStatusMeta /",
    "// recentTimeLabel / recentPlatformLabel / recentChipHTML / recentListHTML /",
    "// recentStatusNow）。host 侧调用点：renderGenerateSuccess@3394 refreshRecent、",
    "// fixHandleEvent@4159 reportRecentStatus、启动区 initRecent——均经顶部 import。",
    "",
  ];
  lines.splice(dashA, dashB - dashA, ...note);
}

// ---- 校验
const out = lines.join(eol);
for (const n of ["renderRecentList", "refreshRecent", "reportRecentStatus", "initRecent"]) {
  if (new RegExp("(async )?function\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
for (const frag of ['refreshRecent();  // 生成成功 → 最近生成列表补一条（工单 recent-jobs/01）', 'reportRecentStatus(outputDir, done);  // 编译结果上报最近生成列表（工单 recent-jobs/01）', 'initRecent();  // 最近生成列表：拉取历史 + 事件委托（复制路径/删除/刷新）', 'from "/js/ui/recent.js"']) {
  if (!out.includes(frag)) throw new Error("host call site / import vanished: " + frag);
}
if (!out.includes("function renderReadinessPanel(") || !out.includes("function initReadinessCheck(")) throw new Error("readiness panel lost (should stay host until 19)");

writeFileSync(p, out, "utf8");
console.log("OK: recent cluster moved; host rewired; lines now", lines.length);
