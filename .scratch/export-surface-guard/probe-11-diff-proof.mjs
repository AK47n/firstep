// probe-11-diff-proof.mjs — 独立于清点脚本的**机械证据**：
//   改完之后，正文里丢掉的每一行都必须是"导出面"（`export` 关键字 / `export {…}` 名单成员 /
//   只服务那条再导出的 `import` 说明符 / 工单明令整条删的那一个函数）。
//
// 手法（不依赖 apply-sweep 的自述）：对每个被改的文件，把清点前（`git show`）与工作树的文本
// 规范化（行尾统一 LF、行尾空白去掉）后逐行比：
//   · 老行原样还在 → 没动；
//   · 老行去掉 `export ` 前缀后还在 → inline 摘前缀；
//   · 老行属一个 `export {…}` 语句（按"以 export { 开头 / 顶格 } 结尾 / 纯名字行"识别），
//     且它带的名字要么仍在本文件、要么正是本轮丢掉的导出名 → 清单摘名字或整条删；
//   · 老行属一个 `import {…}` 语句，且它的说明符名字都只出现在被摘的那条边里 → 孤儿 import 摘除；
//   · 老行属 `ui/generate-recommend.js::groupChoiceGap()` 的函数体 → 工单明令整条删（唯一正文删除）。
// 另外查两件容易藏事的地方：**导出名集合的差**（丢掉的每个导出名必须仍在本文件里有声明，
// 或被明令整条删）、**尾部换行数**（逐文件必须与清点前一致）。
//
// 用法：node .scratch/export-surface-guard/probe-11-diff-proof.mjs [base]
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const die = (msg) => { console.error(`✗ 内部错误：${msg}`); process.exit(2); };
const BASE = process.argv[2] || "d0f3e843";
const git = (...a) => execFileSync("git", a, { cwd: ROOT, encoding: "utf8", maxBuffer: 256 * 1024 * 1024 });
const lf = (s) => s.split("\r\n").join("\n");
const norm = (l) => l.replace(/[ \t]+$/, "");
const IDENT = /[A-Za-z_$][\w$]*/g;
const idents = (s) => s.match(IDENT) || [];
/** 去掉行尾 `//` 注释（粗略，够用：名单行里不会出现字符串里的 `//`）。 */
const stripComment = (l) => l.replace(/\/\/.*$/, "");

const changed = git("-c", "core.safecrlf=false", "diff", "--name-only", "--", "src/contest_generator/static/js")
  .split("\n").map((s) => s.trim()).filter(Boolean);

/** 导出名集合（`export function/const/… NAME` 与 `export { a, b }` 的成员）。 */
function exportNames(text) {
  const out = new Set();
  const t = lf(text);
  for (const m of t.matchAll(/^[ \t]*export\s+(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)/gm)) out.add(m[1]);
  for (const m of t.matchAll(/^[ \t]*export\s*\{([\s\S]*?)\}/gm)) {
    for (const part of m[1].split(",")) {
      const n = part.trim().split(/\s+as\s+/).pop().trim();
      if (/^[A-Za-z_$][\w$]*$/.test(n)) out.add(n);
    }
  }
  return out;
}
/** 说明符名集合（`import { a, b } from` 的成员）。 */
function importNames(text) {
  const out = new Set();
  for (const m of lf(text).matchAll(/^[ \t]*import\s*\{([\s\S]*?)\}\s*from/gm)) {
    for (const part of m[1].split(",")) {
      const n = part.trim().split(/\s+as\s+/)[0].trim();
      if (/^[A-Za-z_$][\w$]*$/.test(n)) out.add(n);
    }
  }
  return out;
}
/** 本地名是否还在正文里（不在 import/export 语句的名单里）。 */
const declaredIn = (text, name) => new RegExp(`(?<![\\w$.])${name}(?![\\w$])`).test(text);

const DELETED_FN_FILE = "src/contest_generator/static/js/ui/generate-recommend.js";
const DELETED_FN_NAMES = ["groupChoiceGap"];

const problems = [];
const tally = { kept: 0, prefix: 0, listRewrite: 0, deletedFn: 0, orphanImport: 0, blank: 0 };

for (const p of changed) {
  const oldRaw = git("-c", "core.safecrlf=false", "show", `${BASE}:${p}`);
  const newRaw = readFileSync(`${ROOT}${p}`, "utf8");
  const oldLines = lf(oldRaw).split("\n").map(norm);
  const newLines = lf(newRaw).split("\n").map(norm);
  const newSet = new Set(newLines);
  const newText = newLines.join("\n");
  const newIdents = new Set(idents(newText));

  const droppedExports = [...exportNames(oldRaw)].filter((n) => !exportNames(newRaw).has(n));
  const droppedImports = [...importNames(oldRaw)].filter((n) => !importNames(newRaw).has(n));
  const droppedExportSet = new Set(droppedExports);
  const droppedImportSet = new Set(droppedImports);

  // 状态机：当前行走在一个 `export {…}` / `import {…}` 语句里吗；以及是否走在被整条删的函数体里
  let inExportList = false;
  let inImportList = false;
  let fnDepth = 0;                                           // >0 = 在 groupChoiceGap 的函数体里
  for (let li = 0; li < oldLines.length; li++) {
    const line = oldLines[li];
    const bare = stripComment(line);
    const t = bare.trim();
    // 被整条删的函数：从它的**声明行**起，按花括号配平吃掉整个函数体
    // （名字要卡 `function <名>(` 形态——裸 `includes` 会撞上 `groupChoiceGapText` 这类同前缀名）
    const declRe = new RegExp(`(?:^|[^\\w$])(?:async\\s+)?function\\s+(${DELETED_FN_NAMES.join("|")})\\s*\\(`);
    if (fnDepth === 0 && p === DELETED_FN_FILE && declRe.test(bare) && !newSet.has(line)) {
      // 从**函数体的那个 `{`** 起算（别把别处的花括号算进来）
      const bodyFrom = bare.indexOf("{", bare.indexOf(")"));
      const bodyText = bodyFrom < 0 ? "" : bare.slice(bodyFrom);
      fnDepth = (bodyText.match(/\{/g) || []).length - (bodyText.match(/\}/g) || []).length;
      tally.deletedFn++;
      if (fnDepth <= 0) die("函数体没开起来（声明行里找不到 `{`）");
      continue;
    }
    if (fnDepth > 0) {
      fnDepth += (t.match(/\{/g) || []).length - (t.match(/\}/g) || []).length;
      tally.deletedFn++;
      if (fnDepth <= 0) fnDepth = 0;
      continue;
    }
    void li;
    void t;
    if (newSet.has(line)) {
      if (/^[ \t]*export\s*\{/.test(bare)) inExportList = !/\}/.test(bare);
      else if (/^[ \t]*import\s*\{/.test(bare)) inImportList = !/\}/.test(bare);
      tally.kept++;
      continue;
    }
    if (t === "") { tally.blank++; continue; }
    const stripped = line.replace(/^([ \t]*)export\s+/, "$1");
    if (stripped !== line && newSet.has(stripped)) { tally.prefix++; continue; }

    const startsExportList = /^[ \t]*export\s*\{/.test(bare);
    const startsImportList = /^[ \t]*import\s*\{/.test(bare);
    const inList = startsExportList || startsImportList || inExportList || inImportList;
    if (inList) {
      if (startsExportList) inExportList = !/\}/.test(bare);
      if (startsImportList) inImportList = !/\}/.test(bare);
      if (/\}/.test(bare)) { inExportList = false; inImportList = false; }
      const ids = idents(bare);
      const localNames = ids.filter((n) => !/^(export|import|from|as)$/.test(n));
      const ok = localNames.every((n) => newIdents.has(n)
        || droppedExportSet.has(n) || droppedImportSet.has(n));
      if (ok) { tally.listRewrite++; continue; }
      problems.push(`${p}: 属某个 export/import 名单但名字对不上 → ${JSON.stringify(line)}`);
      continue;
    }
    if (p === DELETED_FN_FILE && DELETED_FN_NAMES.some((n) => t.includes(n))) {
      tally.deletedFn++;
      continue;
    }
    problems.push(`${p}: 这一行在新文本里找不到出处 → ${JSON.stringify(line)}`);  }

  // 丢掉的导出名：必须仍在本文件里有声明（只是被摘了 export），
  // 或是"孤儿的转手再导出"（名字只为那条再导出而存在），或是工单明令整条删的那个函数
  for (const n of droppedExports) {
    if (declaredIn(newText, n) || DELETED_FN_NAMES.includes(n) || droppedImportSet.has(n)) continue;
    problems.push(`${p}: 导出名 ${n} 丢掉后在文件里再也找不到（不是"只摘 export"）`);
  }
  // 丢掉的说明符名：本地名应当也一起消失（说明它只为那条边存在）
  for (const n of droppedImports) {
    if (!declaredIn(newText, n)) { tally.orphanImport++; continue; }
    problems.push(`${p}: import 说明符里的 ${n} 摘了但本地名还在用（会变成死 import）`);
  }
  // 尾部换行数逐文件还原
  const trail = (s) => { const x = lf(s); return x.length - x.replace(/\n+$/, "").length; };
  if (trail(newRaw) !== trail(oldRaw)) problems.push(`${p}: 尾部换行数变了`);
}

console.log(`被改文件 ${changed.length} 个`);
console.log(`归因：未被改动的老行 ${tally.kept} 行 / 摘 export 前缀 ${tally.prefix} 行 /`
  + ` 名单重写 ${tally.listRewrite} 行 / 删函数体 ${tally.deletedFn} 行 /`
  + ` 孤儿 import ${tally.orphanImport} 行 / 空行 ${tally.blank} 行`);
console.log(`\n**归不了因的差异：${problems.length} 处**`);
for (const x of problems) console.log(`  ✗ ${x}`);
console.log(problems.length === 0
  ? "\nPASS：每一处改动都是「摘导出面 / 摘孤儿 import 说明符」，或工单明令整条删的那一个函数；尾部换行逐文件还原"
  : "\nFAIL");
process.exitCode = problems.length === 0 ? 0 : 1;
