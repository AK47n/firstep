// 探针：跑一遍 ui-dom-contract 的两条判据，看当前实现下有多少「问题」。
// 只为校准判据，不进闸门。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  listJs, declaredIds, danglingIds, referencedIds, unreachableModules,
} from "../../tests/js/ui-dom-contract.mjs";
import { hostScript } from "../../tests/js/import-usage.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const read = (p) => readFileSync(p, "utf8");

const allJs = listJs(STATIC + "js").map((p) => ({ key: p.slice(STATIC.length), text: read(p) }));
const html = read(STATIC + "index.html");
const declared = declaredIds([{ path: "index.html", text: html }, ...allJs]);
const uiSources = allJs.filter((m) => m.key.startsWith("js/ui/"))
  .map((m) => ({ path: m.key.slice(3), text: m.text }));

const script = hostScript(html);
const hostText = script;

const dangling = danglingIds(uiSources, declared);
const unreachable = unreachableModules(uiSources, hostText, allJs);
const refIds = new Set(uiSources.flatMap((s) => referencedIds(s.path, s.text).map((r) => r.id)));

console.log(`声明 id = ${declared.size}；ui 模块 = ${uiSources.length}；ui 引用 id = ${refIds.size}`);
console.log(`\n判据① 游离 id = ${dangling.length}`);
for (const d of dangling) console.log(`  ✗ ${d.id}  ← ${d.refs.map((r) => r.path + ":" + r.line).join(", ")}`);
console.log(`\n判据② 装载不可达 = ${unreachable.length}`);
for (const u of unreachable) console.log(`  ✗ ${u.path} — ${u.why}`);
