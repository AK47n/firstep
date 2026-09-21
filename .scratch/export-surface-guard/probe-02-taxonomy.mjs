// probe-02-taxonomy.mjs — 零消费者导出的三分类 + 修好再导出链的形态判定
// 只为读数，不产生判据。
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, readConsumerModules, unconsumedExports, parseModuleExports,
  parseModuleImports, resolveModuleKey, maskCommentsAndStrings,
} from "../../tests/js/boot-contract.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${ROOT}src/contest_generator/static/`;
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const word = (n) => new RegExp(`(?<![\\w$.])${esc(n)}\\b`);

const boot = readLoadRoot(STATIC);
const page = new Map([["boot.js", boot], ...readJsModules(STATIC).map((m) => [m.key, m.text])]);

// —— 全仓文件清单（分类用）
const files = [];
const walk = (d) => {
  if (!existsSync(d)) return;
  for (const entry of readdirSync(d, { withFileTypes: true })) {
    const full = `${d}/${entry.name}`;
    if (entry.isDirectory()) { if (!/node_modules|\.git|\.trash/.test(entry.name)) walk(full); }
    else if (/\.(mjs|js|py|html|json)$/.test(entry.name)) files.push(full);
  }
};
for (const d of ["tests", "tools", "src"]) walk(`${ROOT}${d}`);
const rel = (p) => p.slice(ROOT.length).split("\\").join("/");
const jsFiles = files.filter((f) => /\.(mjs|js)$/.test(f));
const pyFiles = files.filter((f) => f.endsWith(".py"));
const testJs = jsFiles.filter((f) => /^tests\//.test(rel(f)));

// —— 零消费者导出：**用判据本体**（工单 01 之后判据单源在 tests/js/boot-contract.mjs；
//    探针自抄一份会分叉——双轴评审实测过一次：名字级 vs 按导出算，差 3 处）
const pageEntries = [...page].map(([key, text]) => ({ key, text }));
const consumerEntries = readConsumerModules(ROOT);
const zero = unconsumedExports(pageEntries, consumerEntries);

const bridged = (masked, name) => {
  for (const m of masked.matchAll(/Object\.assign\(\s*window\s*,\s*\{([\s\S]*?)\}\s*\)/g)) {
    if (word(name).test(m[1])) return true;
  }
  return false;
};

// —— python 侧字面量引用（跨语言镜像对拍按源码文本读；只用于分类标注，不算消费者）
const pyLiterals = new Set();
for (const f of pyFiles) {
  for (const m of readFileSync(f, "utf8").matchAll(/["']([A-Za-z_$][\w$]*)["']/g)) pyLiterals.add(m[1]);
}

const rows = [];
for (const { key, name } of zero) {
  const ownPath = `src/contest_generator/static/js/${key}`;
  const text = page.get(key);
  const masked = maskCommentsAndStrings(text);
  // 用**原文**数（注释也算）：掩码件会把模板串 `${…}` 里插值一并掩掉（boot-contract 已知限制），
  // 拿它数"还有没有别处用"会把 `\`${PANEL_LABELS[k]}\`` 这类误判成"只有定义行"。
  // 数多了只会让"真死"这一档更保守（更不容易误删），方向安全。
  const code = (text.match(new RegExp(word(name).source, "g")) || []).length;
  const isBridged = bridged(masked, name);
  const elsewhere = [];
  for (const f of files) {
    if (rel(f) === ownPath) continue;
    if (word(name).test(readFileSync(f, "utf8"))) elsewhere.push(rel(f));
  }
  const pyLit = pyLiterals.has(name);
  let verdict;
  if (code <= 1 && !isBridged) verdict = "真死（只有定义行）→ 整条删";
  else if (isBridged) verdict = "摘 export 关键字（window 桥保留）";
  else verdict = "摘 export 关键字（仅内部用）";
  rows.push({ key, name, code, isBridged, pyLit, elsewhere, verdict });
}

console.log(`=== 零 import 消费者的导出（页面图 ∪ tests/js ∪ tests/browser 的 import 边）===`);
console.log(`合计 ${zero.length}`);
const byVerdict = {};
for (const r of rows) byVerdict[r.verdict] = (byVerdict[r.verdict] || 0) + 1;
console.log("分类计数：", JSON.stringify(byVerdict, null, 0));
console.log("");
console.log("模块".padEnd(28) + "导出名".padEnd(30) + "码位".padEnd(6) + "桥".padEnd(4) + "py字面量".padEnd(10) + "别处提及");
for (const r of rows) {
  console.log(
    `${r.key.padEnd(28)}${r.name.padEnd(30)}${String(r.code).padEnd(6)}${(r.isBridged ? "是" : "—").padEnd(4)}`
    + `${(r.pyLit ? "是" : "—").padEnd(10)}${r.elsewhere.join(" ") || "（无）"}`);
}
console.log("");
console.log("=== 真死清单（只有定义行、无桥、无别处提及）===");
for (const r of rows.filter((r) => r.code <= 1 && !r.isBridged)) {
  console.log(`  ${r.key} :: ${r.name}`);
}
console.log("");
console.log("=== backlog 点名的 7 个在上述集合里的落点 ===");
const SEVEN = ["CCS_PIECE_NAMES", "maincScrollToRange", "codeEditorHighlight", "HWCHECK_VERDICT_FALLBACK",
  "BUY_DECISIONS_KEY", "SETTINGS_DEFAULT_COLLAPSED", "wfNum"];
for (const n of SEVEN) {
  const r = rows.find((x) => x.name === n);
  console.log(`  ${n.padEnd(28)} ${r ? `${r.verdict}；别处提及：${r.elsewhere.join(" ") || "（无）"}` : "不在集合内（有 import 消费者？）"}`);
}

// ---------------------------------------------------------------------------
// 形态判定（修好再导出链：用 parseModuleImports 拿 from 说明符）
// ---------------------------------------------------------------------------
const LOCAL_FN = (name) => new RegExp(
  `(?:^|\\n)[ \\t]*(?:export\\s+)?(?:async\\s+)?function\\s+${esc(name)}\\b`
  + `|(?:^|\\n)[ \\t]*(?:export\\s+)?class\\s+${esc(name)}\\b`
  + `|(?:^|\\n)[ \\t]*(?:export\\s+)?(?:const|let|var)\\s+${esc(name)}\\s*=\\s*(?:async\\s*)?(?:\\(|function\\b|[A-Za-z_$][\\w$]*\\s*=>)`);
const LOCAL_ANY = (name) => new RegExp(
  `(?:^|\\n)[ \\t]*(?:export\\s+)?(?:async\\s+)?(?:function|class|const|let|var)\\s+${esc(name)}\\b`);
const ALIAS = (name) => new RegExp(
  `(?:^|\\n)[ \\t]*(?:export\\s+)?(?:const|let|var)\\s+${esc(name)}\\s*=\\s*([A-Za-z_$][\\w$]*)\\s*;`);

/** 模块里 `import { x } from "…"` → x 的来源模块。 */
function importSourceOf(key, local) {
  for (const e of parseModuleImports(page.get(key))) {
    const at = e.locals.indexOf(local);
    if (at < 0) continue;
    const t = resolveModuleKey(e.spec, key);
    return t ? { key: t, name: e.names[at] } : null;
  }
  return null;
}

/** 导出名 → "fn" | "value" | null（解不开），跟随再导出与函数别名。 */
function form(key, name, depth = 0, seen = new Set()) {
  const tag = `${key}::${name}`;
  if (depth > 8 || seen.has(tag)) return null;
  seen.add(tag);
  const text = page.get(key);
  if (!text) return null;
  const masked = maskCommentsAndStrings(text);
  // 再导出（带 from）
  for (const e of parseModuleImports(text)) {
    if (!e.names.includes(name)) continue;
    const t = resolveModuleKey(e.spec, key);
    if (t === null) return null;
    if (t === key) continue;                       // `export { a };` 本地形态
    return form(t, name, depth + 1, seen);
  }
  if (LOCAL_FN(name).test(masked)) return "fn";
  const alias = ALIAS(name).exec(masked);
  if (alias) {                                     // `export const x = 某标识符;`
    const target = alias[1];
    const local = LOCAL_FN(target).test(masked);
    if (local) return "fn";
    const src = importSourceOf(key, target);
    if (src) return form(src.key, src.name, depth + 1, seen);
    if (LOCAL_ANY(target).test(masked)) return "value";
    return null;                                   // 可能是全局/内建函数名
  }
  if (LOCAL_ANY(name).test(masked)) return "value";
  return null;
}

let callSites = 0;
const bad = [];
const unresolved = [];
for (const [key, text] of page) {
  const masked = maskCommentsAndStrings(text);
  for (const e of parseModuleImports(text)) {
    const target = resolveModuleKey(e.spec, key);
    if (target === null || e.star || !page.has(target)) continue;
    e.locals.forEach((localName, i) => {
      if (!new RegExp(`(?<![\\w$.])${esc(localName)}\\s*\\(`).test(masked)) return;
      callSites++;
      const f = form(target, e.names[i]);
      if (f === null) unresolved.push({ from: key, to: target, name: e.names[i] });
      else if (f !== "fn") bad.push({ from: key, to: target, name: e.names[i], form: f });
    });
  }
}
console.log("");
console.log("=== 调用位 ⇒ 函数形态（再导出链与函数别名已解开）===");
console.log(`调用位导入名 ${callSites}；非函数形态 ${bad.length} 处；解不开 ${unresolved.length} 处`);
for (const b of bad) console.log(`  [违规] ${b.from} ← ${b.to} :: ${b.name}（${b.form}）`);
for (const u of unresolved) console.log(`  [解不开] ${u.from} ← ${u.to} :: ${u.name}`);
