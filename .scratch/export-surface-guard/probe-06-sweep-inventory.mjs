// probe-06-sweep-inventory.mjs — 清点前的逐条盘点（只为读数，不做任何写盘）
//   把判据 D 的 111 处按「清扫形态」逐条列出来，并给出每条要动的**原文行**、
//   所在 `export {…}` 清单的完整项数与摘完后剩几项（决定"摘名字"还是"整行删"）。
//
// 判据本体来自 `tests/js/boot-contract.mjs`（工单 01 立的单源）；**形态定位**自带一份扫描器：
// `parseModuleImports` 只把 `export {…} from "…"`（带 from 的再导出）当边，
// `export { a, b };`（纯本文件导出面）它按设计不收（那不是 import 边）——所以清单形态必须
// 自己扫。扫描一律在**掩码文本**上定位、在**原文**上取行（照 boot-contract 的两条先例：
// 定位用掩码免得注释里的 `export {` 被当真，取行用原文免得注释被吞掉）。
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, readConsumerModules, unconsumedExports, maskCommentsAndStrings,
  parseModuleExports,
} from "../../tests/js/boot-contract.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${ROOT}src/contest_generator/static`;
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const pageEntries = [{ key: "boot.js", text: readLoadRoot(STATIC) }, ...readJsModules(STATIC)];
const page = new Map(pageEntries.map((m) => [m.key, m.text]));
const consumers = readConsumerModules(ROOT);
const zero = unconsumedExports(pageEntries, consumers);

/** 模块里所有 `export {…}` 清单 → [{ start, end, names, locals, spec, from }]（行列 1 基）。 */
export function exportLists(text) {
  const masked = maskCommentsAndStrings(text);
  const out = [];
  for (const m of masked.matchAll(/(?:^|\n)([ \t]*)export\s*\{/g)) {
    const begin = m.index + m[1].length;               // `export` 的起点
    const open = masked.indexOf("{", begin);           // `{` 的位置
    const close = masked.indexOf("}", open);
    if (open < 0 || close < 0) continue;               // 应当不会发生
    const names = [];
    const locals = [];
    for (const part of masked.slice(open + 1, close).split(",")) {
      const clean = part.trim();
      if (!clean) continue;
      const alias = clean.split(/\s+as\s+/);
      names.push(alias[0].trim());
      locals.push((alias[1] || alias[0]).trim());
    }
    const start = masked.slice(0, begin).split("\n").length;      // 1 基行号
    const end = masked.slice(0, close).split("\n").length;
    // `from "…"`：本文件声明 vs 再导出
    const tail = /^\s*from\s*("([^"]*)"|'([^']*)')/.exec(text.slice(close + 1, close + 200));
    out.push({ start, end, names, locals, spec: tail ? (tail[2] ?? tail[3]) : null, text: text.slice(begin, close + 1) });
  }
  return out;
}

/** 这条导出是 inline 声明、`export {…}` 清单项，还是两者都不是 → { shape, line, end, names, … }。 */
function shapeOf(text, name) {
  const masked = maskCommentsAndStrings(text);
  const maskedLines = masked.split("\n");
  const rawLines = text.split("\n");
  const inlineRe = new RegExp(
    `^[ \\t]*export\\s+(?:async\\s+)?(?:function|class|const|let|var)\\s+${esc(name)}(?![\\w$])`);
  for (let i = 0; i < maskedLines.length; i++) {
    if (inlineRe.test(maskedLines[i])) return { shape: "inline", line: i + 1, end: i + 1, text: rawLines[i] };
  }
  for (const list of exportLists(text)) {
    if (!list.names.includes(name)) continue;
    return { shape: "list", line: list.start, end: list.end, text: list.text, list: list.names,
      listLocals: list.locals, spec: list.spec };
  }
  return { shape: "?", line: 0, end: 0, text: "" };
}

const rows = zero.map((z) => ({ ...z, ...shapeOf(page.get(z.key), z.name) }));
rows.sort((a, b) => (a.key === b.key ? a.line - b.line : a.key < b.key ? -1 : 1));

const counts = { inline: 0, list: 0, "?": 0 };
for (const r of rows) counts[r.shape]++;
console.log(`零消费者导出 ${rows.length} 处：inline ${counts.inline} / 清单 ${counts.list} / 认不出 ${counts["?"]}`);

console.log("\n== inline 形态（删 `export ` 前缀）==");
for (const r of rows.filter((x) => x.shape === "inline")) {
  console.log(`  ${r.key}:${r.line}  ${r.text.trim()}`);
}

const listRows = rows.filter((x) => x.shape === "list");
const sites = new Map();
for (const r of listRows) {
  const tag = `${r.key}:${r.line}-${r.end}`;
  if (!sites.has(tag)) sites.set(tag, { tag, ...r, doomed: [] });
  sites.get(tag).doomed.push(r.name);
}
const wholeLine = [...sites.values()].filter((s) => s.doomed.length === s.list.length);

console.log(`\n== 清单形态（${listRows.length} 项名字，落在 ${sites.size} 条清单上）==`);
for (const s of sites.values()) {
  console.log(`  ${s.tag}  ${s.doomed.length}/${s.list.length} 项要摘`
    + ` → ${s.doomed.length === s.list.length ? "【整行删】" : "【摘名字】"}`
    + `${s.spec ? `（再导出 from "${s.spec}"）` : "（本文件声明）"}`);
  for (const [i, line] of s.text.split("\n").entries()) console.log(`      ${s.line + i}: ${line}`);
  console.log(`      摘：${s.doomed.join(", ")}`);
  console.log(`      留：${s.list.filter((n) => !s.doomed.includes(n)).join(", ") || "（空 → 整行删）"}`);
  for (const n of s.doomed) {                          // 摘完本地名还有没有别的用处（防"未使用具名 import"）
    const local = s.listLocals[s.list.indexOf(n)];
    const uses = (maskCommentsAndStrings(page.get(s.key)).match(
      new RegExp(`(?<![\\w$.])${esc(local)}(?![\\w$])`, "g")) || []).length;
    console.log(`      本地名 ${local}：掩码正文里出现 ${uses} 次`
      + `（${uses === 1 ? "只剩声明处 → 摘 export 后可删 import" : "还有别的用处"}）`);
  }
}
console.log(`\n整行删 ${wholeLine.length} 条（${wholeLine.reduce((n, s) => n + s.doomed.length, 0)} 名）：`
  + wholeLine.map((s) => `${s.tag} ${s.doomed.join("/")}`).join("；"));
console.log(`摘名字 ${sites.size - wholeLine.length} 条（${listRows.length - wholeLine.reduce((n, s) => n + s.doomed.length, 0)} 名）`);

console.log("\n== 逐条（模块::名字，按模块分组）==");
const byKey = new Map();
for (const r of rows) byKey.set(r.key, [...(byKey.get(r.key) || []), r]);
for (const [key, list] of byKey) {
  console.log(`  ${key}：${list.map((r) => `${r.name}[${r.shape}@${r.line}]`).join(", ")}`);
}

console.log(`\n合计：${rows.length} 处 = inline ${counts.inline}（其中整条删 1 个 groupChoiceGap）`
  + ` + 清单项 ${counts.list}`);
console.log(`形态细分：摘 export 前缀 ${counts.inline - 1} 处 / 清单摘名字 `
  + `${listRows.length - wholeLine.reduce((n, s) => n + s.doomed.length, 0)} 处 / 清单整行删 `
  + `${wholeLine.reduce((n, s) => n + s.doomed.length, 0)} 处 / 整条删 1 处`);
console.log(`导出条目总数：${pageEntries.reduce((n, e) => n + parseModuleExports(e.text).size, 0)}`);
