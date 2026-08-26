// 阶段 2 工单 08：参考文件库 tab 迁 ui/reference.js（13+ 函数 + 4 状态 +
// ref-anchor-kind / 录入表单 / 文件选择 ref 绑定；host 仅留分发器与启动调用）。
// 删除段（物理升序，内容锚点寻址）：ref 绑定注记+绑定对（4910-4912）→
// 参考库整簇（4917-5374 一带：区段头 → btn-ref-add 监听末）。顶部 import 追加。
// 全程 CRLF 感知。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/reference.js"'))) throw new Error("reference import already present");

// ---- 1) host import：library import 之后追加
{
  const li = must(lines.findIndex((l) => l.includes('from "/js/ui/library.js"')), "library import");
  lines.splice(li + 1, 0,
    'import { loadReferences, loadKitVocabulary, initReferenceToolbar, deleteReference, editReference, openReferenceFile, viewReferenceDetail } from "/js/ui/reference.js";');
}

// ---- 2) 段 A：参考库整簇（ref 绑定注记 → btn-ref-add 监听末）→ 注记
{
  const a = must(lines.findIndex((l) => l === "// 参考库两个绑定留 host（工单 08 迁簇时带走）。"), "ref binding note");
  const b = must(lines.findIndex((l) => l.startsWith('$("btn-ref-add").addEventListener("click"')), "btn-ref-add listener");
  let e = b;
  while (e < lines.length && lines[e] !== "});") e++;
  if (e >= lines.length) throw new Error("btn-ref-add end not found");
  // 边界：下一行应为 PDF 区段头（dashes 注释）
  const next = lines[e + 1];
  if (!/^\/\/ -+$/.test(next) && !next.startsWith("//") && next !== "") {
    throw new Error("unexpected boundary after btn-ref-add: " + JSON.stringify(next));
  }
  const removed = lines.slice(a, e + 1).join(eol);
  for (const n of ["refUI", "refFilterContext", "renderReferenceChips", "renderReferenceStats", "renderReferences", "clearReferenceFilter", "initReferenceToolbar", "kitVocabulary", "loadKitVocabulary", "refEntryCache", "refTopicKeys", "loadReferences", "deleteReference", "editReference", "REF_TEXT_EXTENSIONS", "referenceFileUrl", "openReferenceFile", "viewReferenceDetail", "showReferenceDetail", "refCollectFiles"]) {
    if (!new RegExp("(function|const|let)\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n);
  }
  if (!removed.includes('bindFilePicker("btn-ref-pick-files"')) throw new Error("ref pick bindings not in span");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 参考文件库页：浏览 / 搜索 / AI 简介草稿 / 入库 / 删除（全部已迁 ui/reference.js）",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/reference.js（阶段 2 工单 08）：refUI / refFilterContext /",
    "// refSearchTimer / kitVocabulary / refEntryCache / refTopicKeys 状态 +",
    "// renderReferenceChips / renderReferenceStats / renderReferences /",
    "// clearReferenceFilter / initReferenceToolbar / loadKitVocabulary /",
    "// loadReferences / deleteReference / editReference / referenceFileUrl /",
    "// openReferenceFile / viewReferenceDetail / showReferenceDetail /",
    "// refCollectFiles + 录入表单监听（ref-anchor-kind / btn-ref-add-file-row /",
    "// btn-ref-draft-desc / btn-ref-add / 两个 ref 文件选择绑定）。纯件在",
    "// fx/reference.js（工单 03 迁）；文件行件在 ui/files.js（06 迁）。",
    "// host 页签分发器 / 启动区经顶部 import 调 loadReferences /",
    "// loadKitVocabulary / initReferenceToolbar（见 import 行与启动区）。",
    "",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 校验
const out = lines.join(eol);
for (const n of ["renderReferenceChips", "renderReferenceStats", "renderReferences", "clearReferenceFilter", "initReferenceToolbar", "loadKitVocabulary", "loadReferences", "deleteReference", "editReference", "referenceFileUrl", "openReferenceFile", "viewReferenceDetail", "showReferenceDetail", "refCollectFiles"]) {
  if (new RegExp("(function|const|let)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
if (/^(const|let)\s+(refUI|refFilterContext|kitVocabulary|refEntryCache|refTopicKeys|refSearchTimer|REF_TEXT_EXTENSIONS)$/m.test(out)) throw new Error("residual ref state");
for (const frag of ['loadReferences(); loadKitVocabulary();', 'initReferenceToolbar();', 'from "/js/ui/reference.js"']) {
  if (!out.includes(frag)) throw new Error("host call site / import vanished: " + frag);
}
if (out.includes('bindFilePicker("btn-ref-pick-files"')) throw new Error("ref pick binding still in host");

writeFileSync(p, out, "utf8");
console.log("OK: reference cluster moved; host rewired; lines now", lines.length);
