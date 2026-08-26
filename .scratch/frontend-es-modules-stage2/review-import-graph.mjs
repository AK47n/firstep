// 一次性评审脚本：static/js 全模块 import 环检测 + index.html host import 与导出面对账
// 用法：node review-import-graph.mjs   （从仓库根运行）
import { readFileSync, readdirSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const JS_DIR = join(ROOT, "src/contest_generator/static/js");

const files = [];
const walk = (d) => {
  for (const e of readdirSync(d, { withFileTypes: true })) {
    const p = join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (e.name.endsWith(".js")) files.push(p);
  }
};
walk(JS_DIR);
const rel = (p) => p.slice(JS_DIR.length + 1).replaceAll("\\", "/");

// ---- 解析 import 边 ----
// 边：file -> importedFile（按 /js/ 前缀与相对路径解析）
const edges = new Map(files.map((f) => [rel(f), new Set()]));
for (const f of files) {
  const src = readFileSync(f, "utf8");
  const re = /import\s+(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']/g;
  let m;
  while ((m = re.exec(src))) {
    const spec = m[1];
    let target = null;
    if (spec.startsWith("/js/")) target = spec.slice("/js/".length);
    else if (spec.startsWith("./")) target = join(dirname(rel(f)), spec.slice(2)).replaceAll("\\", "/");
    else continue; // 第三方 / node 内建（无）
    if (target.endsWith(".js")) target = target.slice(0, -3);
    edges.get(rel(f))?.add(target + ".js");
  }
}

// ---- 环检测（DFS 找环路径）----
const nodeIdx = new Map(files.map((f, i) => [rel(f), i]));
const adj = files.map(() => []);
for (const [from, set] of edges) for (const to of set) {
  const ti = nodeIdx.get(to);
  if (ti !== undefined) adj[nodeIdx.get(from)].push(ti);
}
const state = new Array(files.length).fill(0); // 0 未访 1 在栈 2 完成
const stack = [];
const cycles = [];
const dfs = (u) => {
  state[u] = 1; stack.push(u);
  for (const v of adj[u]) {
    if (state[v] === 0) { if (dfs(v)) return true; }
    else if (state[v] === 1) {
      const i = stack.indexOf(v);
      cycles.push(stack.slice(i).concat(v).map((x) => rel(files[x])).join(" → "));
    }
  }
  stack.pop(); state[u] = 2; return false;
};
for (let i = 0; i < files.length; i++) if (state[i] === 0) dfs(i);
console.log("== 模块 import 环 ==");
if (cycles.length === 0) console.log("（无环）");
else cycles.forEach((c) => console.log("  " + c));

// ---- 关键约束：app.js 不 import 任何 ui ----
const appEdges = [...(edges.get("app.js") || [])];
console.log("\n== app.js 的 import 目标 ==");
appEdges.forEach((e) => console.log("  " + e));
console.log(appEdges.some((e) => e.startsWith("ui/")) ? "  ⚠ app.js 引用了 ui 模块（禁止）" : "  ✓ app.js 无 ui 依赖");

// ---- host import 对账 ----
const html = readFileSync(join(ROOT, "src/contest_generator/static/index.html"), "utf8");
const importLines = html.split("\n").filter((l) => l.includes('from "/js/'));
console.log(`\n== host import 行数: ${importLines.length} ==`);
const missing = [];
let total = 0;
for (const line of importLines) {
  const m = line.match(/import\s*\{([^}]*)\}\s*from\s*"\/js\/([^"]+)"/);
  if (!m) { console.log("  无法解析: " + line.trim().slice(0, 80)); continue; }
  const names = m[1].split(",").map((s) => s.trim()).filter(Boolean);
  const modPath = join(JS_DIR, m[2]);
  let src;
  try { src = readFileSync(modPath, "utf8"); } catch { missing.push(`${m[2]}（文件不存在）`); continue; }
  for (const n of names) {
    total++;
    const escN = n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const rx = new RegExp(`(?:export\\s+(?:async\\s+)?(?:function|const|let|class)\\s+${escN}(?![\\w$]))|(?:export\\s*\\{[^}]*\\b${escN}\\b[^}]*\\})|(?:export\\s*\\{[^}]*\\b${escN}\\s+as\\b)`, "m");
    if (!rx.test(src)) missing.push(`${m[2]} 缺导出 ${n}`);
  }
}
console.log(`host import 名字总数: ${total}`);
if (missing.length === 0) console.log("✓ 全部名字在目标模块有对应导出");
else missing.forEach((x) => console.log("  ⚠ " + x));

// ---- ui 模块导出清单（一眼核对）----
console.log("\n== ui/*.js 导出面 ==");
for (const f of files.filter((p) => rel(p).startsWith("ui/")).sort()) {
  const src = readFileSync(f, "utf8");
  const ex = [];
  for (const [re] of [[/export\s+(?:async\s+)?(?:function|const|let|class)\s+([A-Za-z_$][\w$]*)/g]]) {
    let m; while ((m = re.exec(src))) ex.push(m[1]);
  }
  for (const m of src.matchAll(/export\s*\{([^}]+)\}/g))
    m[1].split(",").forEach((s) => { const n = s.trim().split(/\s+as\s+/)[0]; if (n) ex.push(n); });
  console.log("  " + rel(f) + ": " + [...new Set(ex)].join(", "));
}
