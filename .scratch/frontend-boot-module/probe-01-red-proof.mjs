// probe-01-red-proof.mjs — 真红证（工单 frontend-boot-module/01）：
// 把**四类不变量**（判据单源 = tests/js/boot-contract.mjs）喂给**收走前那个提交**的源码，
// 证明它们真的会红；再在当前工作树上复算一遍（收口工单 05 要求这里绿）。
//
// 手法（照 .scratch/release-channel-dedupe/probe-01-pin-red-proof.py 先例）：
//   · 只读：`git show <base>:<path>` / `git ls-tree`，不碰工作区、不改仓库文件
//   · **base 必须显式钉住，不能写 HEAD**：本工单提交之后 HEAD 就是收走后的代码，
//     拿 HEAD 当"收走前"会让红证静默变绿（2026-09-20 刚踩过这个坑）
//   · **base 自校验**：base 的 index.html 必须有 Import 清单、且**没有** boot.js、
//     且那 11 个模块各自有求值期接线 —— 任一条不成立就大声失败，绝不产出假绿
//
// 用法：
//     node .scratch/frontend-boot-module/probe-01-red-proof.mjs
//     node .scratch/frontend-boot-module/probe-01-red-proof.mjs --base <rev>
import { execFileSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import {
  indexHtmlImports, inlineDefinitions, wiringViolations, wiringEffects, registryProblems,
  graphBreaks, reachable, readJsModules, loadRootTag, parseModuleImports, bareLoads,
  importersOf, loadRootKeys, EXPLICIT_WIRING_MODULES,
} from "../../tests/js/boot-contract.mjs";
import { unreachableModules } from "../../tests/js/ui-dom-contract.mjs";
import { hostScript } from "../../tests/js/import-usage.mjs";

// 证据落 UTF-8 文件（PowerShell 的 `>` 会写 UTF-16LE；`--out <path>` 可覆盖）
tee(fileURLToPath(import.meta.url), process.argv.slice(2));

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const INDEX = "src/contest_generator/static/index.html";
const JS_DIR = "src/contest_generator/static/js";
const STATIC_DIR = REPO + "src/contest_generator/static";
const BOOT = `${JS_DIR}/boot.js`;

// 收走前那个提交（spec 现场快照：index.html 的 <script type="module"> 块还在）
const BASE = "b52022f1";

// 本次要显式 init 的 11 个模块（spec「实现决策」B 档）
const SCOPED = [
  "ui/generate-revise.js", "ui/generate-tasks.js", "ui/params.js", "ui/params-chat.js",
  "ui/delivery.js", "ui/generate-core.js", "ui/library.js", "ui/master.js",
  "ui/reference.js", "ui/topic.js", "ui/code-fix-panel.js",
];

const args = process.argv.slice(2);
const base = args.includes("--base") ? args[args.indexOf("--base") + 1] : BASE;

const git = (...a) => execFileSync("git", a, {
  cwd: REPO, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"],
});
const gitOrNull = (...a) => {
  try { return git(...a); } catch { return null; }      // 取不到就返回 null（stderr 不吵）
};

/** 宿主脚本块 = `tests/js/import-usage.mjs` 的单源（收走前那一代：装载清单写在 index.html 里）。 */
const hostOf = hostScript;

// ---------------------------------------------------------------------------
// ① base 自校验：选错就大声失败（红证的"静默变绿"就死在这一步）
// ---------------------------------------------------------------------------

const baseHtml = gitOrNull("show", `${base}:${INDEX}`);
if (baseHtml === null) {
  console.error(`✗ base ${base} 里读不到 ${INDEX} —— 换 --base`);
  process.exit(2);
}
const baseBoot = gitOrNull("show", `${base}:${BOOT}`);
const basePaths = git("ls-tree", "-r", "--name-only", base, "--", JS_DIR)
  .split("\n").map((s) => s.trim()).filter((p) => p.endsWith(".js"));
const baseModules = basePaths.map((p) => ({
  key: p.slice(JS_DIR.length + 1),
  text: git("show", `${base}:${p}`),
}));
const baseHost = hostOf(baseHtml);
const baseImports = parseModuleImports(baseHost);

const selfCheck = [];
if (baseImports.length !== 45) {
  selfCheck.push(`base 的宿主脚本有 ${baseImports.length} 条 import（收走前是 45 条）`);
}
if (baseBoot !== null) {
  selfCheck.push("base 里已经有 js/boot.js —— 这不是收走前的提交");
}
const missingScoped = SCOPED.filter((key) =>
  wiringEffects((baseModules.find((m) => m.key === key) || { text: "" }).text).length === 0);
if (missingScoped.length) {
  selfCheck.push(`base 里这些模块没有求值期接线（判据③在 base 上不可能红）：${missingScoped.join(", ")}`);
}
console.log(`== ① base 自校验（base=${base}）==`);
console.log(`  收走前宿主脚本：import ${baseImports.length} 条；boot.js：${baseBoot === null ? "不存在（对）" : "已存在（错）"}`);
console.log(`  模块表：${baseModules.length} 个 .js（git ls-tree ${base}）`);
if (selfCheck.length) {
  console.error("✗ base 选错，红证会静默变绿 —— 拒绝继续：");
  for (const line of selfCheck) console.error("  · " + line);
  process.exit(2);
}
console.log("  ✓ 通过（base 是收走前那一代）");

// ---------------------------------------------------------------------------
// ② 判据作用在 base 上：必红
// ---------------------------------------------------------------------------

const baseHtmlImports = indexHtmlImports(baseHtml);
const baseWiring = wiringViolations(baseHost, baseModules);
const baseWiringTotal = baseWiring.reduce((n, p) => n + p.effects.length, 0);

console.log(`\n== ② 同一套判据作用在 base 上（应红）==`);
console.log(`  判据①「index.html 零 import」：红 —— ${baseHtmlImports.length} 条`);
for (const line of baseHtmlImports.slice(0, 3)) console.log(`      ${line.line}: ${line.text.slice(0, 70)}`);
console.log(`      …（其余 ${Math.max(0, baseHtmlImports.length - 3)} 条略）`);
const baseBare = bareLoads(baseHost);
console.log(`  判据③-a「装载清单零裸装载」：红 —— ${baseBare.length} 条`);
for (const b of baseBare) console.log(`      ${b.line}: import "${b.spec}"`);
console.log(`  判据③-b「接线不住求值期」（适用面 = 登记表 11 个模块 ∪ boot 唯一装载来源的 ui 模块）：红 —— ${baseWiring.length} 个模块 / ${baseWiringTotal} 条列 0 副作用`);
for (const p of baseWiring) console.log(`      ${p.key}: ${p.effects.length} 条（首条 ${p.effects[0].line}: ${p.effects[0].text.slice(0, 56)}）`);
const baseRegistry = registryProblems(baseHost, baseModules);
console.log(`  登记表体检（11 项）：${baseRegistry.length ? "红 —— " + baseRegistry.map((p) => p.key + "：" + p.why).join("；") : "绿"}`);
const redOk = baseHtmlImports.length > 0 && baseWiring.length > 0 && baseBare.length > 0;

// ---------------------------------------------------------------------------
// ③ 判据作用在当前工作树上（收口工单 05 要求这里绿）
// ---------------------------------------------------------------------------

const nowHtml = readFileSync(REPO + INDEX, "utf8");
const nowModules = readJsModules(STATIC_DIR);
const nowRoot = existsSync(REPO + BOOT) ? readFileSync(REPO + BOOT, "utf8") : null;
const nowRootTag = loadRootTag(nowHtml);

console.log(`\n== ③ 当前工作树读数（收口时要求全绿）==`);
const nowImports = indexHtmlImports(nowHtml);
const nowDefs = inlineDefinitions(nowHtml);
// 装载根还不存在时（工单 02 之前）：判据 ③/④ 没有适用面 —— **如实地报"无装载根"**，
// 不拿哨兵值凑数（凑出来的"1 条红"是编造读数，比不报更坏）。
const rootLabel = nowRoot ? "boot.js" : "（无装载根：判据 ③/④ 无适用面）";
const nowWiring = nowRoot ? wiringViolations(nowRoot, nowModules) : null;
const nowRegistry = nowRoot ? registryProblems(nowRoot, nowModules) : null;
const nowBare = nowRoot ? bareLoads(nowRoot) : null;
const graphRoot = nowRoot || hostOf(nowHtml);       // 无 boot 时按现状（宿主块）算基线
const nowBreaks = graphBreaks([{ key: "boot.js", text: graphRoot }, ...nowModules]);
const nowReach = reachable(graphRoot, nowModules);
console.log(`  判据① index.html import：${nowImports.length} 条${nowImports.length ? "（红）" : "（绿）"}`);
console.log(`  判据② index.html JS 定义：${nowDefs.length} 条${nowDefs.length ? "（红）" : "（绿）"}`);
console.log(`  装载标签：type=module 共 ${nowRootTag.count} 个，src=${nowRootTag.src || "（内联）"}`);
console.log(`  判据③-a 装载清单裸装载：${nowBare ? `${nowBare.length} 条${nowBare.length ? "（红：" + nowBare.map((b) => b.spec).join(", ") + "）" : "（绿）"}` : rootLabel}`);
console.log(`  判据③-b 接线不住求值期：${nowWiring ? `${nowWiring.length} 个模块${nowWiring.length ? "（红：" + nowWiring.map((p) => p.key).join(", ") + "）" : "（绿）"}` : rootLabel}`);
console.log(`  登记表体检（11 项）：${nowRegistry ? (nowRegistry.length ? "（红：" + nowRegistry.map((p) => p.key).join(", ") + "）" : "（绿）") : rootLabel}`);
console.log(`  判据④-a 全图对账断裂（根=${rootLabel}）：${nowBreaks.length} 处${nowBreaks.length ? "（红：" + nowBreaks.slice(0, 3).map((b) => b.from + "→" + b.spec).join(", ") + "）" : "（绿）"}`);
console.log(`  判据④-b 从装载根可达：${nowModules.length - nowReach.orphans.length}/${nowModules.length}${nowReach.orphans.length ? "（掉队：" + nowReach.orphans.slice(0, 5).join(", ") + "）" : "（绿）"}`);
const greenNow = nowImports.length === 0 && nowDefs.length === 0 && nowWiring !== null
  && nowWiring.length === 0 && nowRegistry !== null && nowRegistry.length === 0
  && nowBare !== null && nowBare.length === 0
  && nowBreaks.length === 0 && nowReach.orphans.length === 0;

// ---------------------------------------------------------------------------
// ④ 判据强度自检（内存注入；不写盘）—— 判据"能红"的证据不止来自 base
// ---------------------------------------------------------------------------

const strength = [];
const check = (name, ok, note) => strength.push({ name, ok, note });

// a) 删一条装载 → 该模块掉出模块图（可达性判据要能看见）
{
  const lines = baseHost.split("\n");
  const idx = lines.findIndex((l) => /^\s*import .*"\/js\/ui\/topic\.js"/.test(l));
  const mutated = idx < 0 ? baseHost : lines.filter((_, n) => n !== idx).join("\n");
  const r = reachable(mutated, baseModules);
  check("删掉一条装载 → 可达性判据报出掉队模块",
    idx >= 0 && r.orphans.includes("ui/topic.js"),
    idx < 0 ? "找不到注入锚点（index.html 装载行变了？）" : `掉队：${r.orphans.join(", ") || "（无）"}`);
}

// b) 摘掉一个导出 → 全图对账报出"未导出"（2026-09-12 整页 SyntaxError 的那一类）
{
  const target = "ui/hwcheck.js";
  const patched = baseModules.map((m) => m.key === target
    ? { ...m, text: m.text.replace("export function renderHwcheckPanel(", "function renderHwcheckPanel(") }
    : m);
  const breaks = graphBreaks([{ key: "boot.js", text: baseHost }, ...patched]);
  const hit = breaks.some((b) => b.from === "boot.js" && b.spec.endsWith("hwcheck.js")
    && b.missing.includes("renderHwcheckPanel"));
  check("摘掉一个导出 → 全图对账报出未导出名", hit,
    hit ? "报出 renderHwcheckPanel" : `没报出（断裂 ${breaks.length} 处）`);
}

// c) 往 index.html 塞一个定义 → 零定义判据报出
{
  const injected = baseHtml.replace("<script>", "<script>\nfunction probeInjected() {}");
  const defs = inlineDefinitions(injected);
  check("index.html 塞一个 function → 零定义判据报出", defs.length > 0,
    defs.length ? `报出 ${defs.length} 条：${defs[0].text}` : "没报出");
}

// d) 遗留的 HTML import 若目标模块不存在 → 全图对账报"文件不存在"
{
  const mutated = baseHost + '\nimport { nothing } from "/js/ui/does-not-exist.js";\n';
  const breaks = graphBreaks([{ key: "boot.js", text: mutated }, ...baseModules]);
  const hit = breaks.some((b) => b.spec.includes("does-not-exist") && b.why === "文件不存在");
  check("装载指向不存在的模块 → 对账报出文件不存在", hit,
    hit ? "报出 does-not-exist.js" : "没报出");
}

// e) "import 了却忘调"判据（ui-dom-contract 的 init 调用点检查）——用合成宿主文本，
//    不掺 base 宿主里既有的 init 调用（否则"忘了调"永远看不见）
{
  const ui = [{ path: "ui/glossary.js", text: baseModules.find((m) => m.key === "ui/glossary.js").text }];
  const all = baseModules.map((m) => ({ key: `js/${m.key}`, text: m.text }));
  const without = 'import { initGlossary } from "/js/ui/glossary.js";\n';
  const withCall = without + "\ninitGlossary();\n";
  const bad = unreachableModules(ui, without, all);
  const good = unreachableModules(ui, withCall, all);
  check("import 了 init 却不调用 → 判据报出；补上调用 → 转绿",
    bad.some((p) => p.why.includes("initGlossary")) && good.length === 0,
    bad.length ? `报出：${bad[0].why}` : "没报出");
}

// f) 注释感知：现状里有"import 花括号里带注释"的真实形态，解析器不得把它当导入名
{
  const src = baseModules.find((m) => m.key === "ui/code-compile.js").text;
  const names = parseModuleImports(src).flatMap((e) => e.names);
  const polluted = names.filter((n) => n.startsWith("//") || n.includes(" "));
  const breaks = graphBreaks(baseModules);
  check("注释感知：花括号里的注释不被当成导入名，全图对账零断裂",
    polluted.length === 0 && breaks.length === 0,
    polluted.length ? `污染名：${polluted.join(" | ")}` : `全图断裂 ${breaks.length} 处`);
}

// g) 判据③ 的登记那一半真的在兜底：4 个"另有 importer"的模块，结构判据抓不到它们
//    （这正是 spec 轴评审实测出来的洞：把它们改成具名导入后，旧口径双报 0）
{
  const structural = new Set([...loadRootKeys(baseHost)]
    .filter((k) => k.startsWith("ui/") && importersOf(k, baseModules).size === 0));
  const registryOnly = EXPLICIT_WIRING_MODULES.filter((k) => !structural.has(k));
  const violated = new Set(wiringViolations(baseHost, baseModules).map((p) => p.key));
  const caught = registryOnly.filter((k) => violated.has(k));
  check("判据③ 登记那一半兜底：结构判据抓不到的模块也被判红",
    registryOnly.length === 4 && caught.length === 4,
    `结构判据漏掉 ${registryOnly.length} 个（${registryOnly.map((k) => k.split("/")[1]).join(", ")}），`
    + `其中判红 ${caught.length} 个`);
}

console.log(`\n== ④ 判据强度自检（内存注入，不写盘）==`);
for (const s of strength) console.log(`  ${s.ok ? "✔" : "✗"} ${s.name} —— ${s.note}`);

// ---------------------------------------------------------------------------
// 结论
// ---------------------------------------------------------------------------

const strengthOk = strength.every((s) => s.ok);
console.log(`\n== 结论 ==`);
console.log(`  红证（base 上必红）：${redOk ? "成立" : "不成立"}`);
console.log(`  强度自检：${strength.filter((s) => s.ok).length}/${strength.length} 成立`);
console.log(`  当前工作树：${greenNow ? "绿（收口状态）" : "红（实现期间正常；工单 05 要求转绿）"}`);
const ok = redOk && strengthOk;
console.log(ok ? "\nPASS（判据能红，且不是靠选错 base 红的）" : "\nFAIL");
process.exitCode = ok ? 0 : 1;
