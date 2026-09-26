// probe-dead-exports.mjs — 只读量具：把 `tests/js` 从判据 D 的消费者集合里摘出去之后，
// 页面模块图里会露出多少「产品侧零消费者」的导出（评审 P2-12 的射程测量）。
//
// 口径与守卫一致：消费者 = 页面模块图（含装载根 boot.js）∪ tests/browser ∪（本次刻意排除的 tests/js）。
// 判据本体不另抄——直接调 tests/js/boot-contract.mjs 的 exportFaceProblems。
import { fileURLToPath } from "node:url";
import { readJsModules, readLoadRoot, readConsumerModules, unconsumedExports, exportFaceProblems } from "../../tests/js/boot-contract.mjs";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${REPO}src/contest_generator/static`;
const PAGE = [{ key: "boot.js", text: readLoadRoot(STATIC) }, ...readJsModules(STATIC)];
const ALL = readConsumerModules(REPO);
const NO_JS_TESTS = ALL.filter((m) => m.key.startsWith("tests/browser/"));

const before = unconsumedExports(PAGE, ALL);
const after = unconsumedExports(PAGE, NO_JS_TESTS);
const key = (v) => `${v.key}::${v.name}`;
const beforeSet = new Set(before.map(key));
const newly = after.filter((v) => !beforeSet.has(key(v)));

console.log(`消费者集合：全部 ${ALL.length} 个（tests/js + tests/browser）→ 排除 tests/js 后 ${NO_JS_TESTS.length} 个`);
console.log(`零消费者导出：现状 ${before.length} 条 → 排除后 ${after.length} 条（新露出 ${newly.length} 条）`);
console.log(`取数面体检（现状）违规 ${exportFaceProblems(PAGE, ALL).length} 条 /（排除 tests/js）违规 ${exportFaceProblems(PAGE, NO_JS_TESTS).length} 条`);
console.log("--- 新露出的（按模块归组）---");
const byModule = new Map();
for (const v of newly) byModule.set(v.key, [...(byModule.get(v.key) || []), v.name]);
for (const [mod, names] of [...byModule.entries()].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`${String(names.length).padStart(3)}  ${mod}: ${names.join(", ")}`);
}
