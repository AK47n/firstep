// probe-01-consume-and-form.mjs — 两件事的严格读数（只为读数，不产生判据）
//   ① 零消费者导出：消费者 = 页面模块图 ∪ tests/js ∪ tests/browser（按**import 边**算，不看提及）
//   ② 调用位 ⇒ 函数形态：把 `export { a }` / `export { a } from "…"` 的再导出链解开，再判形态
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, parseModuleExports, parseModuleImports,
  resolveModuleKey, maskCommentsAndStrings,
} from "../../tests/js/boot-contract.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${ROOT}src/contest_generator/static/`;
const JS = `${STATIC}js`;
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const word = (n) => new RegExp(`(?<![\\w$.])${esc(n)}\\b`);

const boot = readLoadRoot(STATIC);
const modules = readJsModules(STATIC);
const page = new Map([["boot.js", boot], ...modules.map((m) => [m.key, m.text])]);

// —— 测试侧：tests/js/*.mjs（含共享件）与 tests/browser/*.mjs
const testFiles = [];
for (const dir of ["tests/js", "tests/browser"]) {
  const abs = `${ROOT}${dir}`;
  if (!existsSync(abs)) continue;
  for (const name of readdirSync(abs)) {
    if (!/\.mjs$/.test(name)) continue;
    testFiles.push({ key: `${dir}/${name}`, text: readFileSync(`${abs}/${name}`, "utf8") });
  }
}

/** 测试文件的说明符 → 页面模块键（仓内 static/js 下）；仓外/无关返回 null。 */
function testSpecToKey(spec, testKey) {
  const norm = spec.split("\\").join("/");
  const marker = "/static/js/";
  const at = norm.indexOf(marker);
  if (at >= 0) return norm.slice(at + marker.length);
  if (!norm.startsWith(".")) return null;
  const base = testKey.split("/").slice(0, -1);            // tests/js
  const parts = norm.split("/");
  const stack = [...base];
  for (const p of parts) {
    if (p === "." || p === "") continue;
    if (p === "..") stack.pop(); else stack.push(p);
  }
  const joined = stack.join("/");                          // 形如 src/contest_generator/static/js/fx/x.js
  const idx = joined.indexOf("static/js/");
  return idx >= 0 ? joined.slice(idx + "static/js/".length) : null;
}

// —— 消费者集合：谁 import 了哪个名字
const consumers = new Map();   // name → Set<消费者描述>
const note = (name, who) => {
  if (!consumers.has(name)) consumers.set(name, new Set());
  consumers.get(name).add(who);
};
for (const [key, text] of page) {
  for (const e of parseModuleImports(text)) {
    if (resolveModuleKey(e.spec, key) === null) continue;
    for (const n of e.names) note(n, `page:${key}`);
  }
}
for (const t of testFiles) {
  for (const e of parseModuleImports(t.text)) {
    if (testSpecToKey(e.spec, t.key) === null) continue;
    for (const n of e.names) note(n, `test:${t.key}`);
  }
}

const exportsOf = new Map([...page].map(([k, t]) => [k, [...parseModuleExports(t)]]));
const dead = [];
for (const [key, names] of exportsOf) {
  for (const n of names) if (!consumers.has(n)) dead.push({ key, name: n });
}
const totalExports = [...exportsOf.values()].reduce((a, b) => a + b.length, 0);
console.log(`=== ① 零消费者导出（消费者 = 页面图 ∪ tests/js ∪ tests/browser 的 import 边）===`);
console.log(`页面导出名 ${totalExports}；零消费者 ${dead.length} 个`);
for (const d of dead) console.log(`  ${d.key} :: ${d.name}`);

// 只看页面图（不含测试）的对照读数
const pageOnly = [];
for (const [key, names] of exportsOf) {
  for (const n of names) {
    const cs = consumers.get(n) || new Set();
    if (![...cs].some((c) => c.startsWith("page:"))) pageOnly.push(n);
  }
}
console.log(`对照：零**页面**消费者的导出 ${pageOnly.length} 个（其中仅被测试消费 = 测试缝）`);

// —— ② 导出形态：把再导出链解开
const LOCAL_DECL = (name) => [
  { re: new RegExp(`(?:^|\\n)\\s*(?:export\\s+)?(?:async\\s+)?function\\s+${esc(name)}\\b`), form: "fn" },
  { re: new RegExp(`(?:^|\\n)\\s*(?:export\\s+)?class\\s+${esc(name)}\\b`), form: "fn" },
  { re: new RegExp(`(?:^|\\n)\\s*(?:export\\s+)?(?:const|let|var)\\s+${esc(name)}\\s*=\\s*(?:async\\s*)?(?:\\(|function\\b|[A-Za-z_$][\\w$]*\\s*=>)`), form: "fn" },
  { re: new RegExp(`(?:^|\\n)\\s*(?:export\\s+)?(?:const|let|var)\\s+${esc(name)}\\s*=`), form: "value" },
];
const REEXPORT_FROM = /^[ \t]*export\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']/gm;
const REEXPORT_LOCAL = /^[ \t]*export\s*\{([^}]*)\}(?!\s*from)/gm;

/** 模块 + 导出名 → { form, via }（解开再导出链；解不开返回 form=null）。 */
function resolveForm(key, name, depth = 0) {
  if (depth > 6) return { form: null, via: "链路过深" };
  const text = page.get(key);
  if (!text) return { form: null, via: "模块不存在" };
  const masked = maskCommentsAndStrings(text);
  // 再导出（带 from）
  for (const m of masked.matchAll(REEXPORT_FROM)) {
    const names = m[1].split(",").map((s) => s.trim().split(/\s+as\s+/).pop().trim()).filter(Boolean);
    if (!names.includes(name)) continue;
    const next = resolveModuleKey(m[2], key);
    if (next === null) return { form: null, via: "仓外再导出" };
    return resolveForm(next, name, depth + 1);
  }
  // 本地再导出（`export { a, b };`）→ 形态由本文件的声明决定，落到下面的 LOCAL_DECL
  for (const d of LOCAL_DECL(name)) if (d.re.test(masked)) return { form: d.form, via: key };
  return { form: null, via: "解不开" };
}

const FUNC_FORMS = new Set(["fn"]);
let callSites = 0;
const bad = [];
const unresolved = [];
for (const [key, text] of page) {
  const masked = maskCommentsAndStrings(text);
  for (const e of parseModuleImports(text)) {
    const target = resolveModuleKey(e.spec, key);
    if (target === null || e.star || !page.has(target)) continue;
    e.locals.forEach((local, i) => {
      if (!new RegExp(`(?<![\\w$.])${esc(local)}\\s*\\(`).test(masked)) return;
      callSites++;
      const src = e.names[i];
      const { form, via } = resolveForm(target, src);
      if (form === null) { unresolved.push({ from: key, to: target, name: src, via }); return; }
      if (!FUNC_FORMS.has(form)) bad.push({ from: key, to: target, name: src, form });
    });
  }
}
console.log(`=== ② 调用位 ⇒ 函数形态 ===`);
console.log(`调用位导入名 ${callSites} 个；导出侧非函数形态 ${bad.length} 处；形态解不开 ${unresolved.length} 处`);
for (const b of bad) console.log(`  ${b.from} ← ${b.to} :: ${b.name}（${b.form}）`);
for (const u of unresolved) console.log(`  [解不开] ${u.from} ← ${u.to} :: ${u.name}（${u.via}）`);

// —— ③ 导出形态分布（常量形态断言的可恢复面有多大）
let fns = 0; const vals = [];
for (const [key, names] of exportsOf) {
  for (const n of names) {
    const { form } = resolveForm(key, n);
    if (form === "fn") fns++;
    else vals.push(`${key}::${n}(${form || "?"})`);
  }
}
console.log(`=== ③ 形态分布 ===`);
console.log(`函数形态 ${fns}；非函数/解不开 ${vals.length}`);
console.log(`  非函数形态清单：${vals.join(", ")}`);
