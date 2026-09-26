// probe-bridge-callsites.mjs — 只读量具：哪些模块**在调用位上**用了别的模块的导出，
// 却既没 import、也没在本模块声明——靠 `Object.assign(window, {...})` 那个老式全局桥解析。
//
// 口径（粗筛，供人复核；已排除：本模块 import 的本地名、本模块 function/const/let/var/class 声明）。
import { fileURLToPath } from "node:url";
import { readJsModules, parseModuleImports, parseModuleExports, maskNonCode } from "../../tests/js/boot-contract.mjs";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${REPO}src/contest_generator/static`;
const MODULES = readJsModules(STATIC);

/** 抽 `Object.assign(window, { ... })` 的对象字面量文本（括号配对，够用）。 */
function windowBridgeNames(text) {
  const names = [];
  const re = /Object\.assign\(\s*window\s*,\s*\{/g;
  let m;
  while ((m = re.exec(text))) {
    let i = m.index + m[0].length, depth = 1;
    while (i < text.length && depth > 0) {
      const c = text[i];
      if (c === "{") depth++;
      else if (c === "}") depth--;
      if (depth === 0) break;
      i++;
    }
    const body = text.slice(m.index + m[0].length, i);
    for (const part of body.split(",")) {
      const t = part.trim();
      const kv = t.match(/^([A-Za-z_$][\w$]*)\s*:/);          // key: value → window 上是 key
      const shorthand = t.match(/^([A-Za-z_$][\w$]*)$/);      // 简写 → 名字本身
      if (kv) names.push(kv[1]);
      else if (shorthand) names.push(shorthand[1]);
    }
  }
  return names;
}

const bridged = new Map();     // 名字 → 首个发布它的模块
for (const mod of MODULES) for (const n of windowBridgeNames(mod.text)) if (!bridged.has(n)) bridged.set(n, mod.key);

const rows = [];
for (const mod of MODULES) {
  const imports = parseModuleImports(mod.text);
  const locals = new Set(imports.flatMap((e) => e.locals || []));
  const code = maskNonCode(mod.text);
  const declared = new Set();
  for (const d of code.matchAll(/\b(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)/g)) declared.add(d[1]);
  // 本模块自己导出的名字也不算"外部依赖"
  const ownExports = new Set(parseModuleExports(mod.text));
  const hits = [];
  for (const [name, from] of bridged) {
    if (from === mod.key || locals.has(name) || declared.has(name) || ownExports.has(name)) continue;
    if (new RegExp(`(?:^|[^\\w$.])${name.replace(/\$/g, "\\$")}\\s*\\(`).test(code)) hits.push(name);
  }
  if (hits.length) rows.push({ key: mod.key, hits });
}

let total = 0;
for (const r of rows.sort((a, b) => b.hits.length - a.hits.length)) {
  total += r.hits.length;
  console.log(`${String(r.hits.length).padStart(3)}  ${r.key}: ${r.hits.join(", ")}`);
}
console.log(`\n合计：${rows.length} 个模块 / ${total} 处「调用位自由标识符」（粗筛，需逐条复核）`);
console.log(`全局桥上共发布 ${bridged.size} 个名字，来自 ${new Set(bridged.values()).size} 个模块`);
