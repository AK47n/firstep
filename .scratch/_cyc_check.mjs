// Temp: detect static ESM import cycles across static/js, and dump the
// code-fix-panel import dependency chain. Ignores dynamic import().
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join, dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../src/contest_generator/static/js/", import.meta.url));

function walk(d, acc = []) {
  for (const f of readdirSync(d)) {
    const p = join(d, f);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (f.endsWith(".js")) acc.push(p);
  }
  return acc;
}

const files = walk(root);
const fileSet = new Set(files.map((f) => resolve(f)));

function normalize(spec, importerAbs, importerDir) {
  let base = null;
  if (spec.startsWith("/js/")) {
    base = join(root, spec.replace(/^\/js\//, ""));
  } else if (spec.startsWith(".")) {
    base = resolve(importerDir, spec);
  } else {
    // bare specifier — treat as external (skip)
    return null;
  }
  if (!base.endsWith(".js")) base += ".js";
  return base;
}

// Static import extraction: import ... from "..." and side-effect import "..." / export ... from "..."
const importsStatic = new Map(); // absPath -> Set(absDeps)
const dynamic = [];              // record dynamic import() specifiers

for (const imp of files) {
  const text = readFileSync(imp, "utf8");
  const dir = dirname(imp);
  const deps = new Set();
  // static named/default/namespace imports
  for (const m of text.matchAll(/^\s*import\s+(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']/gm)) {
    const t = normalize(m[1], imp, dir);
    if (t && existsSync(t)) deps.add(resolve(t));
    else if (t) deps.add(t + " (MISSING)");
  }
  // export ... from "..."
  for (const m of text.matchAll(/^\s*export\s+[\s\S]*?\s+from\s+["']([^"']+)["']/gm)) {
    const t = normalize(m[1], imp, dir);
    if (t && existsSync(t)) deps.add(resolve(t));
    else if (t) deps.add(t + " (MISSING)");
  }
  // dynamic import()
  for (const m of text.matchAll(/import\(\s*["']([^"']+)["']\s*\)/g)) {
    const t = normalize(m[1], imp, dir);
    dynamic.push({ imp: resolve(imp), spec: m[1], resolved: t || "(external)" });
  }
  importsStatic.set(resolve(imp), deps);
}

// DFS cycle detection
const color = new Map(); // 0 white 1 gray 2 black
const stack = [];
const cycles = [];
function dfs(n) {
  color.set(n, 1); stack.push(n);
  for (const d of importsStatic.get(n) || []) {
    if (!fileSet.has(d) || d.includes("MISSING")) continue;
    if (!color.has(d)) { dfs(d); continue; }
    if (color.get(d) === 1) {
      const i = stack.indexOf(d);
      cycles.push(stack.slice(i).concat(d).map((x) => x.replace(root, "/js/")).join(" -> "));
    }
  }
  stack.pop(); color.set(n, 2);
}
for (const f of files) if (!color.has(f)) dfs(f);

console.log("=== STATIC IMPORT CYCLES ===");
console.log(cycles.length ? cycles.join("\n") : "(none)");

console.log("\n=== code-fix-panel import chain ===");
const start = join(root, "ui", "code-fix-panel.js");
const seen = new Set();
function chain(n, depth) {
  if (depth > 40) return;
  seen.add(n);
  const rel = n.replace(root, "/js/");
  console.log("  ".repeat(depth) + rel);
  for (const d of importsStatic.get(n) || []) {
    const target = d.includes("MISSING") ? d : resolve(d);
    if (!fileSet.has(target)) continue;
    if (seen.has(target)) { console.log("  ".repeat(depth + 1) + "CYCLE-BACK -> " + target.replace(root, "/js/")); continue; }
    chain(target, depth + 1);
  }
}
chain(start, 0);

console.log("\n=== dynamic import() sites ===");
for (const d of dynamic) console.log("  " + d.imp.replace(root, "/js/") + "  import(" + d.spec + ") -> " + (d.resolved ? d.resolved.replace(root, "/js/") : d.resolved));
