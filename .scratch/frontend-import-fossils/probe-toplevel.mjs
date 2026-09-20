import { readFileSync } from "node:fs";

const ROOT = new URL("../../src/contest_generator/static/js/", import.meta.url);
const MODULES = [
  "ui/progress.js", "ui/files.js", "ui/generate-revise.js", "ui/generate-tasks.js",
  "ui/params.js", "ui/params-chat.js", "ui/delivery.js",
];

for (const rel of MODULES) {
  const src = readFileSync(new URL(rel, ROOT), "utf8");
  const lines = src.splitlines;
  const top = [];
  let inBlockComment = false;
  for (const line of src.split("\n")) {
    const t = line.trim();
    if (inBlockComment) { if (t.includes("*/")) inBlockComment = false; continue; }
    if (t.startsWith("/*")) { if (!t.includes("*/")) inBlockComment = true; continue; }
    if (!t || t.startsWith("//")) continue;
    if (t.startsWith("import ")) continue;
    if (/^(export\s+)?(async\s+)?function\b/.test(t)) continue;
    if (/^(export\s+)?(const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(async\s*)?\(/.test(t)) continue; // 箭头函数定义
    if (/^\}/.test(t)) continue;
    // 列 0 的语句 = 顶层可执行语句（缩进内的属于函数体）
    if (/^[A-Za-z_$]/.test(line)) top.push(line.trim());
  }
  console.log(`=== ${rel}`);
  console.log(top.length ? top.map((l) => "    " + l.slice(0, 110)).join("\n") : "    （无顶层可执行语句：纯声明模块）");
}
