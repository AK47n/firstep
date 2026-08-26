// 阶段 2 工单 06：共用文件件迁 ui/files.js（函数 + MAX_PICK_BYTES；4 个
// bindFilePicker 调用 / btn-add-file-row 监听 / 初始行 留 host 待 07/08 迁簇）
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/files.js"'))) throw new Error("files import already present");

// ---- 1) host import：pdf.js import 之后
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/pdf.js"')), "pdf import");
  lines.splice(i + 1, 0,
    'import { addFileRow, collectFiles, readPickedText, pickFilesInto, bindFilePicker } from "/js/ui/files.js";');
}

// ---- 2) 段 A：注释 + addFileRow 定义（6005-6018）→ 注记
{
  const a = must(lines.findIndex((l) => l.includes("// 动态文件行（模块库 / 参考文件库共用")), "addFileRow comment");
  const b = must(lines.findIndex((l) => l.startsWith("function addFileRow(container, name, content) {")), "addFileRow");
  let e = b;
  while (e < lines.length && lines[e] !== "}") e++;
  if (e >= lines.length) throw new Error("addFileRow end not found");
  const removed = lines.slice(a, e + 1).join(eol);
  if (!/dynamic/.test(removed) && !/addFileRow\(container, name, content\)/.test(removed)) throw new Error("span A unexpected");
  const note = [
    "// 动态文件行（模块库 / 参考文件库共用）已迁至 static/js/ui/files.js（阶段 2 工单 06）；",
    "// 下方 btn-add-file-row 监听与初始行绑定经 host import 引用同名函数。",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 3) 段 B：collectFiles + 选择器注释 + MAX_PICK_BYTES + 3 函数（→ bindFilePicker 末）→ 注记
{
  const a = must(lines.findIndex((l) => l.startsWith("function collectFiles(container) {")), "collectFiles");
  const b = must(lines.findIndex((l) => l.startsWith("function bindFilePicker(btnId, inputId, containerId, msgId) {")), "bindFilePicker");
  let e = b;
  while (e < lines.length && lines[e] !== "}") e++;
  if (e >= lines.length) throw new Error("bindFilePicker end not found");
  // bindFilePicker 尾随后应紧跟 4 个绑定调用（留 host）——确认它们不在 span 内
  const removed = lines.slice(a, e + 1).join(eol);
  for (const n of ["collectFiles", "MAX_PICK_BYTES", "readPickedText", "pickFilesInto", "bindFilePicker"]) {
    if (!new RegExp("(function|const)\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n + " in span B");
  }
  if (!/bindFilePicker\("btn-pick-mod-files"/.test(lines[e + 1])) throw new Error("bind calls not right after bindFilePicker (span boundary shifted?): " + lines[e + 1]);
  const note = [
    "// ===== 选择文件 / 文件夹 → 读为文本填入文件行（模块库 / 参考库共用）=====",
    "// 已迁至 static/js/ui/files.js（阶段 2 工单 06）：collectFiles / readPickedText /",
    "// pickFilesInto / bindFilePicker / MAX_PICK_BYTES；下方 4 个绑定调用经 host import。",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 校验
const out = lines.join(eol);
for (const n of ["addFileRow", "collectFiles", "readPickedText", "pickFilesInto", "bindFilePicker", "MAX_PICK_BYTES"]) {
  if (new RegExp("(function|const)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
for (const frag of ['bindFilePicker("btn-pick-mod-files"', 'bindFilePicker("btn-ref-pick-files"', 'collectFiles($("ref-files"))', 'collectFiles()', 'addFileRow()', 'addFileRow(newfilesBox)', 'pickFilesInto(e.target, newfilesBox']) {
  if (!out.includes(frag)) throw new Error("host call site vanished: " + frag);
}

writeFileSync(p, out, "utf8");
console.log("OK: files shared moved; imports updated; lines now", lines.length);
