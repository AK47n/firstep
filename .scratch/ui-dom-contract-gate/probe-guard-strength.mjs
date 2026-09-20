// 红证（工单 ui-dom-contract-gate/02）：两条判据**真的会红**吗。
//
// 口径：不动仓库里任何文件——判据函数是纯的（源码文本进、问题清单出），
// 所以按 tests/js/ui-dom-contract.test.mjs 的同一条取数路径读真源码，
// 把**注入变异**加在内存里的副本上，再断言"该红"。绿的反证也一起跑（原样必须干净）。
//
// 用法：node .scratch/ui-dom-contract-gate/probe-guard-strength.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  listJs, declaredIds, danglingIds, unreachableModules,
} from "../../tests/js/ui-dom-contract.mjs";
import { hostScript } from "../../tests/js/import-usage.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const read = (p) => readFileSync(STATIC + p, "utf8");

const NATIVE = listJs(STATIC + "js")
  .map((path) => ({ key: path.slice(STATIC.length), text: readFileSync(path, "utf8") }));
const HTML = read("index.html");

const results = [];
const check = (label, ok, note = "") => {
  results.push({ label, ok, note });
  console.log(`${ok ? "✔" : "✖"} ${label}${note ? "  —— " + note : ""}`);
};

const build = (mutate) => {
  const modules = NATIVE.map((m) => ({ ...m, text: mutate(m.key, m.text) ?? m.text }));
  const hostRaw = mutate("index.html", HTML) ?? HTML;
  const ui = modules.filter((m) => m.key.startsWith("js/ui/"))
    .map((m) => ({ path: m.key.slice(3), text: m.text }));
  const declared = declaredIds([{ path: "index.html", text: hostRaw }, ...modules]);
  return { ui, declared, modules, hostRaw };
};

// ---- 判据①：id 存在性 ----
{
  const clean = build(() => null);
  const problems = danglingIds(clean.ui, clean.declared);
  check("① 原样：无游离 id（绿）", problems.length === 0, `${problems.length} 条`);
}
{
  const injected = build((key, text) =>
    key === "js/ui/library.js" ? text + "\n$(\"outpt-dir-typo\");\n" : null);
  const problems = danglingIds(injected.ui, injected.declared);
  const hit = problems.find((p) => p.id === "outpt-dir-typo");
  check("① 注入：ui 引用一个不存在的 id → 红且点名", !!hit,
    hit ? `#${hit.id} ← ${hit.refs.map((r) => r.path + ":" + r.line).join(",")}` : "没抓到");
}
{
  // 反向：把声明**删掉**（把 index.html 里某个被引用的 id 改名）→ 也必须红
  const target = danglingIds(build(() => null).ui, build(() => null).declared).length === 0
    ? "output-dir" : null;
  const injected = build((key, text) =>
    key === "index.html" ? text.replace('id="output-dir"', 'id="output-dir-renamed"') : null);
  const problems = danglingIds(injected.ui, injected.declared);
  const hit = problems.find((p) => p.id === "output-dir");
  check("① 反证：把 index.html 里被引用的 id 改名 → 红且点名", !!hit && !!target,
    hit ? `#${hit.id} ← ${hit.refs.length} 处引用` : "没抓到");
}

/** 删掉含某子串的整行（按 \n 切，对 CRLF 也安全——末尾的 \r 随行一起去掉）。 */
const dropLineContaining = (text, needle) =>
  text.split("\n").filter((line) => !line.includes(needle)).join("\n");

// ---- 判据②：装载可达性 ----
const hostScriptOf = (html) => hostScript(html);
{
  const clean = build(() => null);
  const problems = unreachableModules(clean.ui, hostScriptOf(clean.hostRaw), clean.modules);
  check("② 原样：无孤立模块、无忘调的 init（绿）", problems.length === 0,
    problems.map((p) => p.path).join(", ") || "");
}
{
  // 孤立模块：把 glossary 从 index.html 的装载清单里摘掉
  const injected = build((key, text) => key === "index.html"
    ? dropLineContaining(text, "/js/ui/glossary.js") : null);
  const problems = unreachableModules(injected.ui, hostScriptOf(injected.hostRaw), injected.modules);
  const hit = problems.find((p) => p.path === "ui/glossary.js");
  check("② 注入：从装载清单摘掉一个模块 → 红且点名「孤立模块」", !!hit, hit ? hit.why : "没抓到");
}
{
  // init 被 import 了却忘调：把 index.html 正文里的 initGlossary() 调用点删掉
  const injected = build((key, text) => key === "index.html"
    ? dropLineContaining(text, "initGlossary();") : null);
  const problems = unreachableModules(injected.ui, hostScriptOf(injected.hostRaw), injected.modules);
  const hit = problems.find((p) => p.path === "ui/glossary.js"
    && /initGlossary 被 import 了却没人调用/.test(p.why));
  check("② 注入：删掉 init 的调用点（import 还在）→ 红且点名", !!hit, hit ? hit.why : "没抓到");
}
{
  // 反向：模块顶部自调的那种写法**不该**被误判（ui/topic.js 的 initTopicToolbar）
  const clean = build(() => null);
  const problems = unreachableModules(clean.ui, hostScriptOf(clean.hostRaw), clean.modules)
    .filter((p) => p.path === "ui/topic.js");
  check("② 反证：模块内自调的 init 不误报（绿）", problems.length === 0,
    problems.map((p) => p.why).join("; ") || "");
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${failed.length ? "FAIL" : "PASS"}：${results.length - failed.length}/${results.length} 条成立`);
process.exitCode = failed.length ? 1 : 0;
