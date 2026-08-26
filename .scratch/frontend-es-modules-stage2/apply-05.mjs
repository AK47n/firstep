// 阶段 2 工单 05：PDF 资料库 tab 迁 ui/pdf.js；truncate 迁 fx/core.js
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/pdf.js"'))) throw new Error("pdf import already present");

// ---- 1) host import：ui/master.js import 之后插入
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/master.js"')), "master import");
  lines.splice(i + 1, 0, 'import { loadPdfs, initPdfToolbar } from "/js/ui/pdf.js";');
}

// ---- 2) PDF 区段（dashes header ~ initPdfToolbar 末）→ 注记
{
  const a0 = must(lines.findIndex((l) => l.includes("PDF 资料库页：素材库全量 PDF 浏览")), "pdf header comment");
  const a = a0 - 1;
  if (!lines[a].startsWith("// ---")) throw new Error("pdf header dash expected: " + lines[a]);
  const b = must(lines.findIndex((l) => l.startsWith("function initPdfToolbar()")), "initPdfToolbar");
  let e = b;
  while (e < lines.length && lines[e] !== "}") e++;
  if (e >= lines.length) throw new Error("initPdfToolbar end not found");
  const removed = lines.slice(a, e + 1).join(eol);
  for (const n of ["pdfFileUrl", "showPdfDetail", "loadPdfs", "initPdfToolbar", "pdfUI", "pdfPageCache", "confirmTrashGroup", "renderPdfChips"]) {
    if (!new RegExp("(function|const|let)\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n + " in removed span");
  }
  if (/赛题库页/.test(removed)) throw new Error("overreach into topic: 赛题库页 in removed span");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// PDF 资料库页：全部胶水已迁至 static/js/ui/pdf.js（阶段 2 工单 05）；",
    "// 纯件（过滤/排序/统计/健康/行渲染/详情/回收 URL）在 static/js/fx/pdf.js。",
    "// host 只经 tab 分发器调 loadPdfs、经启动 init 调 initPdfToolbar（顶部 import）。",
    "// ---------------------------------------------------------------------------",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 3) truncate（题库簇物理区内的死件）→ 注记（迁 fx/core.js）
{
  const a = must(lines.findIndex((l) => l.startsWith("function truncate(text, n) {")), "truncate");
  let e = a;
  while (e < lines.length && lines[e] !== "}") e++;
  if (e >= lines.length) throw new Error("truncate end not found");
  const removed = lines.slice(a, e + 1).join(eol);
  if (!/…/.test(removed) || !/text\.length <= n/.test(removed)) throw new Error("truncate body unexpected: " + removed);
  const note = ["// truncate（文本截断纯函数，当前无调用方）已迁至 static/js/fx/core.js（阶段 2 工单 05）。"];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 校验
const out = lines.join(eol);
const moved = [
  "pdfFileUrl", "pdfHealthPredicates", "loadPdfPages", "copyPdfPath", "showPdfDetail",
  "openPdfTrashConfirm", "pdfTrashDate", "confirmTrashPdf", "confirmTrashGroup",
  "renderPdfChips", "renderPdfStats", "renderPdfs", "clearPdfFilter", "loadPdfs",
  "initPdfToolbar", "pdfUI", "pdfFilterContext", "pdfCache", "pdfSearchTimer",
  "pdfPageCache", "truncate",
];
for (const n of moved) {
  if (new RegExp("(function|const|let)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
for (const frag of ["loadPdfs();", "initPdfToolbar();"]) {
  if (!out.includes(frag)) throw new Error("host call site vanished: " + frag);
}
if (!out.includes("赛题库页")) throw new Error("topic header vanished (over-deleted)");

writeFileSync(p, out, "utf8");
console.log("OK: pdf tab moved; truncate moved; imports updated; lines now", lines.length);
