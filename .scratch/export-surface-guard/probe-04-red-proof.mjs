// probe-04-red-proof.mjs — 真红证（工单 export-surface-guard/01）：
// 把**导出面两条判据**（判据单源 = tests/js/boot-contract.mjs）喂给**清点前那个提交**的源码，
// 证明它们真的会红；再在当前工作树上复算一遍（清点工单 02 之后这里要求绿）。
//
// 手法（照 .scratch/frontend-boot-module/probe-01-red-proof.mjs 先例）：
//   · 只读：`git ls-tree` / `git show`，不碰工作区、不改仓库文件
//   · **base 必须显式钉住，不能写 HEAD**：本轮提交之后 HEAD 就是清点后的代码，
//     拿 HEAD 当"清点前"会让红证静默变绿
//   · **base 自校验**：base 上零消费者导出必须是 111 处、形态面 0 处、且 base 那一代
//     `boot-contract.mjs` 里还没有这两条判据 —— 任一条不成立就大声失败，绝不产出假绿
//
// 用法：
//     node .scratch/export-surface-guard/probe-04-red-proof.mjs
//     node .scratch/export-surface-guard/probe-04-red-proof.mjs --base <rev> --out <path>
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, readConsumerModules, parseModuleImports, parseModuleExports,
  resolveModuleKey, consumerSpecToKey, maskCommentsAndStrings,
  unconsumedExports, nonFunctionCallees, starImports, exportFaceProblems,
} from "../../tests/js/boot-contract.mjs";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const JS_DIR = "src/contest_generator/static/js";
const CONTRACT = "tests/js/boot-contract.mjs";

// 清点前那个提交（spec 现场基线；**不写 HEAD**）
const BASE = "27a7b46e";

const argv = process.argv.slice(2);
const argOf = (flag) => (argv.includes(flag) ? argv[argv.indexOf(flag) + 1] : null);
const base = argOf("--base") || BASE;
const outPath = argOf("--out") || fileURLToPath(new URL("./red-proof.txt", import.meta.url));

// 证据落 UTF-8 文件：脚本自己写（PowerShell 的 `>` 会写 UTF-16LE，`tee` 又得依赖别的 feature 目录）
const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };
const flush = () => writeFileSync(outPath, lines.join("\n") + "\n", "utf8");
const fail = (msg) => { say(msg); flush(); process.exit(2); };

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const word = (n) => new RegExp(`(?<![\\w$.])${esc(n)}\\b`);
const git = (...a) => execFileSync("git", a, {
  cwd: REPO, encoding: "utf8", maxBuffer: 256 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"],
});
const gitOrNull = (...a) => { try { return git(...a); } catch { return null; } };

/** 从某个提交读页面模块表（键空间相对 `static/js`；装载根单独取）→ { page, root }。 */
function pageAt(rev) {
  const paths = git("ls-tree", "-r", "--name-only", rev, "--", JS_DIR)
    .split("\n").map((s) => s.trim()).filter((p) => p.endsWith(".js"));
  const modules = paths.map((p) => ({ key: p.slice(JS_DIR.length + 1), text: git("show", `${rev}:${p}`) }));
  const root = modules.find((m) => m.key === "boot.js");
  return { page: [root, ...modules.filter((m) => m.key !== "boot.js")], root };
}

/** 从某个提交读消费侧模块表（`tests/js` 与 `tests/browser` 的 .mjs）→ [{ key, text }]。 */
function consumersAt(rev) {
  const out = [];
  for (const dir of ["tests/js", "tests/browser"]) {
    const paths = gitOrNull("ls-tree", "-r", "--name-only", rev, "--", dir);
    if (paths === null) continue;
    for (const p of paths.split("\n").map((s) => s.trim()).filter((x) => x.endsWith(".mjs"))) {
      out.push({ key: p, text: git("show", `${rev}:${p}`) });
    }
  }
  return out;
}

const patch = (entries, key, fn) => entries.map((e) => (e.key === key ? { ...e, text: fn(e.text) } : e));
const dropName = (text, edge, name) => {
  const rest = edge.names.filter((n) => n !== name);
  return text.replace(edge.raw, rest.length ? `import { ${rest.join(", ")} } from "${edge.spec}";` : "");
};

// ---------------------------------------------------------------------------
// ① base 自校验（选错 base = 红证静默变绿，就死在这一步）
// ---------------------------------------------------------------------------

const { page: basePage } = pageAt(base);
const baseConsumers = consumersAt(base);
const baseContract = gitOrNull("show", `${base}:${CONTRACT}`);
if (baseContract === null) fail(`✗ base ${base} 里读不到 ${CONTRACT} —— 换 --base`);

const baseD = unconsumedExports(basePage, baseConsumers);
const baseT = nonFunctionCallees(basePage);
const baseStars = starImports(basePage, baseConsumers);
const baseFace = exportFaceProblems(basePage, baseConsumers);

const selfCheck = [];
if (baseD.length !== 111) selfCheck.push(`base 的零消费者导出是 ${baseD.length} 处（实测基线是 111 处）`);
if (baseT.length !== 0) selfCheck.push(`base 的形态违规是 ${baseT.length} 处（实测基线是 0 处）`);
if (baseStars.length !== 0) selfCheck.push(`base 有 ${baseStars.length} 处星号导入（实测基线是 0 处）`);
if (baseFace.length) selfCheck.push(`base 的取数面体检就不干净：${baseFace.join("；")}`);
if (baseContract.includes("unconsumedExports")) {
  selfCheck.push("base 那一代 boot-contract.mjs 里已经有判据 D —— 这不是清点前的提交");
}
for (const [key, needle] of [
  ["fx/code.js", "export function maincScrollToRange"],
  ["fx/workflow.js", "export function wfNum"],
  ["ui/generate-recommend.js", "export function groupChoiceGap"],
]) {
  if (!(basePage.find((m) => m.key === key).text.includes(needle))) {
    selfCheck.push(`base 的 ${key} 里找不到 \`${needle}\` —— 这不是清点前的提交`);
  }
}

say(`== ① base 自校验（base=${base}）==`);
say(`  页面模块 ${basePage.length} 个（git ls-tree ${base} -- ${JS_DIR}）；消费侧 ${baseConsumers.length} 个 .mjs`);
say(`  判据 D 零消费者导出：${baseD.length} 处（基线 111）；判据 T 形态违规：${baseT.length} 处（基线 0）`);
say(`  星号导入：${baseStars.length} 处；取数面体检：${baseFace.length ? baseFace.join("；") : "无问题"}`);
if (selfCheck.length) {
  flush();
  console.error("✗ base 选错，红证会静默变绿 —— 拒绝继续：");
  for (const line of selfCheck) console.error("  · " + line);
  process.exit(2);
}
say("  ✓ 通过（base 是清点前那一代）");

// ---------------------------------------------------------------------------
// ② 判据作用在 base 上：判据 D 必红
// ---------------------------------------------------------------------------

say(`\n== ② 同一套判据作用在 base 上（判据 D 应红、判据 T 应绿）==`);
say(`  判据 D「每个导出必须有消费者」：红 —— ${baseD.length} 处`);
const byKeyOf = (list) => {
  const m = new Map();
  for (const v of list) m.set(v.key, [...(m.get(v.key) || []), v.name]);
  return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
};
const grouped = byKeyOf(baseD);
for (const [key, names] of grouped.slice(0, 6)) {
  say(`      ${key}：${names.length} 个 —— ${names.slice(0, 6).join(", ")}${names.length > 6 ? " …" : ""}`);
}
say(`      …（其余 ${Math.max(0, grouped.length - 6)} 个模块略；完整清单见 --out 文件末尾）`);
const SEVEN = ["CCS_PIECE_NAMES", "maincScrollToRange", "codeEditorHighlight", "HWCHECK_VERDICT_FALLBACK",
  "BUY_DECISIONS_KEY", "SETTINGS_DEFAULT_COLLAPSED", "wfNum"];
const sevenHit = SEVEN.filter((n) => baseD.some((v) => v.name === n));
say(`      backlog 点名的 7 个：${sevenHit.length}/7 在清单里（${sevenHit.length === 7 ? "对" : "错"}）`);
say(`  判据 T「调用位 ⇒ 函数形态」：绿 —— ${baseT.length} 处违规（0 不是"判据没用"：见 ④ 的自检 6/7/8）`);
const redOk = baseD.length > 0 && sevenHit.length === 7;

// ---------------------------------------------------------------------------
// ③ 判据作用在当前工作树上（工单 02 之前 = 仍红；02 之后 = 绿）
// ---------------------------------------------------------------------------

const STATIC = `${REPO}src/contest_generator/static`;
const nowPage = [{ key: "boot.js", text: readLoadRoot(STATIC) }, ...readJsModules(STATIC)];
const nowConsumers = readConsumerModules(REPO);
const nowD = unconsumedExports(nowPage, nowConsumers);
const nowT = nonFunctionCallees(nowPage);
const nowStars = starImports(nowPage, nowConsumers);
const nowFace = exportFaceProblems(nowPage, nowConsumers);

let worktreeState;
if (nowD.length === 0) worktreeState = "绿（清点已完成）";
else if (nowD.length === baseD.length) worktreeState = `红（清点尚未做：${nowD.length} 处，与 base 同数）`;
else worktreeState = `异常（${nowD.length} 处，既不是 base 的 ${baseD.length} 也不是 0）`;

say(`\n== ③ 当前工作树读数 ==`);
say(`  页面模块 ${nowPage.length} 个；消费侧 ${nowConsumers.length} 个 .mjs`);
say(`  判据 D 零消费者导出：${nowD.length} 处 —— ${worktreeState}`);
say(`  判据 T 形态违规：${nowT.length} 处${nowT.length ? "（红：" + nowT.slice(0, 3).map((v) => v.name).join(", ") + "）" : "（绿）"}`);
say(`  星号导入体检：${nowStars.length} 处${nowStars.length ? "（红）" : "（绿）"}`);
say(`  取数面体检：${nowFace.length ? "红 —— " + nowFace.join("；") : "绿"}`);
// 工单 ③ 要求"判据 T 在 base 与当前工作树上都是 0 违规"——工作树这一半必须**硬判**，
// 不能只打印（工单 01 spec 轴评审实测：打印不判的话，工作树上 T 崩了脚本照样 PASS）。
const worktreeClean = nowT.length === 0 && nowStars.length === 0 && nowFace.length === 0;
const worktreeOk = worktreeClean && (nowD.length === 0 || nowD.length === baseD.length);

// ---------------------------------------------------------------------------
// ④ 判据强度自检（内存注入，不写盘）—— "判据能红"的证据不止来自 base
// ---------------------------------------------------------------------------

const pageKeys = new Set(nowPage.map((e) => e.key));
const byKey = new Map(nowPage.map((e) => [e.key, e]));

// 全图消费边清单（供自检挑锚点：挑"只被一条边消费"的名字，摘掉它才必然报出）
const edges = [];
for (const entry of nowPage) {
  for (const edge of parseModuleImports(entry.text)) {
    const target = resolveModuleKey(edge.spec, entry.key);
    if (target === null || edge.star || !pageKeys.has(target)) continue;
    for (const name of edge.names) edges.push({ kind: "page", entry, edge, target, name });
  }
}
for (const entry of nowConsumers) {
  for (const edge of parseModuleImports(entry.text)) {
    const target = consumerSpecToKey(edge.spec);
    if (target === null) continue;
    for (const name of edge.names) edges.push({ kind: "consumer", entry, edge, target, name });
  }
}
const edgeCount = new Map();
for (const e of edges) edgeCount.set(e.name, (edgeCount.get(e.name) || 0) + 1);

const callEdge = (entry, edge, local) =>
  new RegExp(`(?<![\\w$.])${esc(local)}\\s*\\(`).test(maskCommentsAndStrings(entry.text));

/** 找一条"调用位"的页面 import 边（可选条件缺省不过滤）→ { entry, edge, target, name, local }。 */
function findCallEdge(where = () => true) {
  for (const entry of nowPage) {
    for (const edge of parseModuleImports(entry.text)) {
      const target = resolveModuleKey(edge.spec, entry.key);
      if (target === null || edge.star || !pageKeys.has(target)) continue;
      for (let i = 0; i < edge.locals.length; i++) {
        const local = edge.locals[i];
        if (!callEdge(entry, edge, local)) continue;
        const found = { entry, edge, target, name: edge.names[i], local };
        if (where(found)) return found;
      }
    }
  }
  return null;
}
const locallyDeclared = (key, name) =>
  new RegExp(`(?:^|\\n)[ \\t]*(?:export\\s+)?(?:async\\s+)?(?:function|class|const|let|var)\\s+`
    + `${esc(name)}(?![\\w$])`)                                  // `$` 那类名字不能用 `\b`（见 boot-contract 注释）
    .test(maskCommentsAndStrings(byKey.get(key).text));

/** 沿再导出链找到"真正声明这个名字"的模块键。 */
function declaringKey(key, name) {
  const seen = new Set();
  let k = key;
  while (!seen.has(k)) {
    seen.add(k);
    if (locallyDeclared(k, name)) return k;
    let next = null;
    for (const edge of parseModuleImports(byKey.get(k).text)) {
      if (!/^export/.test(edge.raw.trimStart()) || !edge.names.includes(name)) continue;
      next = resolveModuleKey(edge.spec, k);
      break;
    }
    if (next === null) return null;
    k = next;
  }
  return null;
}

const strength = [];
const check = (name, ok, note) => strength.push({ name, ok, note });

// 1) 摘掉一条真 import 边 → 判据 D 报出（锚点挑"只被一条边消费"的名字，摘掉必然报出）
{
  const anchor = edges.find((e) => e.kind === "page" && edgeCount.get(e.name) === 1);
  if (!anchor) check("摘掉一条真 import 边 → 判据 D 报出", false, "找不到只被一条页面边消费的锚点");
  else {
    const patched = patch(nowPage, anchor.entry.key, (t) => dropName(t, anchor.edge, anchor.name));
    const hit = unconsumedExports(patched, nowConsumers).some((v) => v.name === anchor.name);
    check("摘掉一条真 import 边 → 判据 D 报出该导出没人用", hit,
      hit ? `${anchor.entry.key} 不再 import ${anchor.name}（来自 ${anchor.target}）→ 报出`
        : `没报出（${anchor.name}）`);
  }
}

// 2) 正向对照：注入一个没人 import 的导出 → 必须报出（防"断言为空"的真空绿）
{
  const target = "fx/code.js";
  const patched = patch(nowPage, target, (t) => t + "\nexport function probeInjectedDead() {}\n");
  const hit = unconsumedExports(patched, nowConsumers).some((v) => v.key === target && v.name === "probeInjectedDead");
  check("正向对照：注入一个没人 import 的导出 → 判据 D 报出", hit,
    hit ? `报出 ${target}::probeInjectedDead` : "没报出（抽取器失效？）");
}

// 3) 注释喂绿自检：名字只出现在别处的注释（含 boot.js 墓碑注释、消费侧注释）→ 仍须报出
{
  const target = "fx/code.js";
  let patched = patch(nowPage, target, (t) => t + "\nexport function probeTombstone() {}\n");
  patched = patch(patched, "boot.js", (t) => t + "\n// probeTombstone 已迁至 fx/code.js（墓碑注释，不是消费者）\n");
  patched = patch(patched, "ui/topic.js", (t) => t + "\n// probeTombstone 同上\n");
  patched = patch(patched, "tests/js/fx-guard.test.mjs", (t) => t + "\n// probeTombstone\n");
  const hit = unconsumedExports(patched, nowConsumers).some((v) => v.name === "probeTombstone");
  check("注释喂绿自检：名字只出现在注释里 → 判据 D 仍报出", hit,
    hit ? "报出（注释不算消费者）" : "没报出 —— 被注释喂绿了");
}

// 4) 测试侧消费者真的算数：摘掉"只被测试 import"的那条边 → 报出
{
  const anchor = edges.find((e) => e.kind === "consumer" && edgeCount.get(e.name) === 1);
  if (!anchor) check("摘掉测试侧 import → 判据 D 报出", false, "找不到只被测试侧消费的锚点");
  else {
    const patched = nowConsumers.map((e) =>
      (e.key === anchor.entry.key ? { ...e, text: dropName(e.text, anchor.edge, anchor.name) } : e));
    const hit = unconsumedExports(nowPage, patched).some((v) => v.name === anchor.name);
    check("测试侧消费者算数：摘掉测试侧 import → 判据 D 报出", hit,
      hit ? `${anchor.entry.key} 不再 import ${anchor.name} → 报出` : `没报出（${anchor.name}）`);
  }
}

// 5) 星号导入体检：注入 `import * as ns` 并真的用上 → 体检必须报出（判据 D 对它本来就是瞎的）
//    锚点**不能写死某个名字**：清点（工单 02）之后 `maincScrollToRange` 已经不是导出了，
//    写死会让这条自检在清点后变成假红。改成**内存注入一个专用锚点**（`probeStarAnchor`）——
//    注入的 `export` 是一条已知的零消费者导出，再给它一个星号消费；判据 D 仍须看不见它。
{
  const baseline = starImports(nowPage, nowConsumers).length;
  const target = "fx/code.js";
  const patched = patch(
    patch(nowPage, target, (t) => t + "\nexport function probeStarAnchor() {}\n"),
    "boot.js",
    (t) => t + `\nimport * as probeNs from "/js/${target}";\nprobeNs.probeStarAnchor();\n`);
  const hit = starImports(patched, nowConsumers).some((s) => s.spec === `/js/${target}`);
  // 如实记一句：星号导入用上了名字，判据 D 也**看不见**（逐名对账对命名空间是瞎的）——这就是体检的理由
  const blind = unconsumedExports(patched, nowConsumers)
    .some((v) => v.key === target && v.name === "probeStarAnchor");
  check("星号导入体检：注入 `import * as ns` → 体检报出（判据 D 对它本来就是瞎的）",
    baseline === 0 && hit && blind,
    `基线 ${baseline} 处；注入后体检${hit ? "报出" : "没报出"}；判据 D ${blind ? "仍把它当没人用" : "意外认了"}`
    + `（内存注入锚点 ${target}::probeStarAnchor）`);
}

// 6) 被调用的 `export function` 换成同名数据 → 判据 T 报出
{
  const anchor = findCallEdge((e) =>
    new RegExp(`export\\s+(?:async\\s+)?function\\s+${esc(e.name)}\\s*\\(`).test(byKey.get(e.target).text));
  if (!anchor) check("把被调用的 export function 换成同名数据 → 判据 T 报出", false, "找不到锚点");
  else {
    const patched = patch(nowPage, anchor.target, (t) => t.replace(
      new RegExp(`export\\s+(?:async\\s+)?function\\s+${esc(anchor.name)}\\s*\\(`),
      `export const ${anchor.name} = 1; const _probeInjected = (`));
    const hit = nonFunctionCallees(patched).some((v) =>
      v.from === anchor.entry.key && v.to === anchor.target && v.name === anchor.name);
    check("把被调用的 `export function` 换成同名数据 → 判据 T 报出", hit,
      hit ? `${anchor.entry.key} → ${anchor.target}::${anchor.name} 报出` : "没报出");
  }
}

// 7) 再导出链感知：链上那一环改成数据 → 报出；**基线不报**（证明链真的被跟到了声明处）
{
  // 锚点 = "经由再导出被调用"的那条边：直接目标不声明它，声明在链的更远处
  let anchor = null;
  for (const entry of nowPage) {
    for (const edge of parseModuleImports(entry.text)) {
      const target = resolveModuleKey(edge.spec, entry.key);
      if (target === null || edge.star || !pageKeys.has(target)) continue;
      for (let i = 0; i < edge.locals.length; i++) {
        if (!callEdge(entry, edge, edge.locals[i])) continue;
        const name = edge.names[i];
        if (locallyDeclared(target, name)) continue;             // 本文件就声明了 → 不是再导出
        const owner = declaringKey(target, name);
        if (owner === null || owner === target) continue;
        anchor = { entry, target, name, owner };
        break;
      }
      if (anchor) break;
    }
    if (anchor) break;
  }
  if (!anchor) check("再导出链感知：链上声明改成数据 → 判据 T 报出", false, "找不到「经由再导出被调用」的锚点");
  else {
    const baseline = nonFunctionCallees(nowPage).some((v) => v.name === anchor.name);
    const patched = patch(nowPage, anchor.owner, (t) => t.replace(
      new RegExp(`export\\s+(?:async\\s+)?function\\s+${esc(anchor.name)}(?![\\w$])`),
      `export const ${anchor.name} = 1; const _probeInjected = (`));
    const hit = nonFunctionCallees(patched).some((v) =>
      v.from === anchor.entry.key && v.to === anchor.target && v.name === anchor.name);
    check("再导出链感知：链上声明改成数据 → 判据 T 报出（基线不报＝链跟通了）", !baseline && hit,
      `基线${baseline ? "报了（链没跟通）" : "不报 ✓"}；改成数据后${hit ? "报出 ✓" : "没报出 ✗"}`
      + `（${anchor.entry.key} → ${anchor.target}（再导出）→ ${anchor.owner}::${anchor.name}）`);
  }
}

// 8) 别名正向对照：`export const x = 别的函数名;` 必须**不报**；改成数据 → 报出
{
  const anchor = findCallEdge((e) => {
    const masked = maskCommentsAndStrings(byKey.get(e.target).text);
    return new RegExp(`(?:^|\\n)[ \\t]*(?:export\\s+)?(?:const|let|var)\\s+${esc(e.name)}\\s*=`
      + `\\s*[A-Za-z_$][\\w$]*\\s*;`).test(masked);
  });
  if (!anchor) check("别名正向对照：`= 别的函数名` 不报；改成数据 → 报出", false, "找不到函数别名锚点");
  else {
    const baseline = nonFunctionCallees(nowPage).some((v) => v.name === anchor.name);
    const patched = patch(nowPage, anchor.target, (t) => t.replace(
      new RegExp(`((?:^|\\n)[ \\t]*(?:export\\s+)?(?:const|let|var)\\s+${esc(anchor.name)}\\s*=)\\s*[A-Za-z_$][\\w$]*\\s*;`),
      `$1 1;`));
    const hit = nonFunctionCallees(patched).some((v) => v.name === anchor.name);
    check("别名正向对照：`= 别的函数名` 不报（防假红）；改成数据 → 报出", !baseline && hit,
      `基线${baseline ? "报了（假红）" : "不报 ✓"}；改成数据后${hit ? "报出 ✓" : "仍不报 ✗"}`
      + `（锚点 ${anchor.target}::${anchor.name}）`);
  }
}

// 9) 注释感知：同一个名字，写成**代码**的调用要报出、写成**注释**的不算调用位
//    锚点**用判据自己当裁判**挑（注入一次调用、看判据报不报）——不去重写一份形态解析，
//    否则"自检"判的是复制品而不是判据本身。
{
  let anchor = null;
  let tried = 0;
  for (const e of edges) {
    if (e.kind !== "page") continue;
    if (++tried > 40) break;                                     // 每次试都跑一遍全图判据：设上限免得太慢
    const asCode = patch(nowPage, e.entry.key, (t) => t + `\n${e.name}(1);\n`);
    if (nonFunctionCallees(asCode).some((v) => v.name === e.name)) { anchor = e; break; }
  }
  if (!anchor) check("注释感知：注释里的 `x(` 不算调用位", false, "找不到「被调用就会报」的值形态导出锚点");
  else {
    const asComment = patch(nowPage, anchor.entry.key, (t) => t + `\n// ${anchor.name}(1); ← 注释里的调用位\n`);
    const commentHit = nonFunctionCallees(asComment).some((v) => v.name === anchor.name);
    check("注释感知：值形态导出被当代码调用 → 报出；写在注释里 → 不报", !commentHit,
      `代码形态报出 ✓；注释形态${commentHit ? "报了 ✗" : "不报 ✓"}`
      + `（锚点 ${anchor.entry.key} 里的 ${anchor.name}）`);
  }
}

say(`\n== ④ 判据强度自检（内存注入，不写盘）==`);
for (const s of strength) say(`  ${s.ok ? "✔" : "✗"} ${s.name} —— ${s.note}`);

// ---------------------------------------------------------------------------
// 结论
// ---------------------------------------------------------------------------

const strengthOk = strength.every((s) => s.ok);
say(`\n== 结论 ==`);
say(`  红证（判据 D 在 base 上必红、且 backlog 点名的 7 个都在清单里）：${redOk ? "成立" : "不成立"}`);
say(`  强度自检：${strength.filter((s) => s.ok).length}/${strength.length} 成立`);
say(`  当前工作树：${worktreeState}；判据 T／星号体检／取数面体检：${worktreeClean ? "全绿" : "有红（见上）"}`);
const ok = redOk && strengthOk && worktreeOk;
say(ok ? "\nPASS（判据能红，且不是靠选错 base 红的）" : "\nFAIL");

// 完整清单落档（base 的 108 处逐条，便于工单 02 照着清点）
say(`\n== 附：base（${base}）的零消费者导出完整清单（${baseD.length} 处）==`);
for (const [key, names] of grouped) say(`  ${key}：${names.join(", ")}`);
say(`\n== 附：当前工作树的零消费者导出完整清单（${nowD.length} 处）==`);
for (const [key, names] of byKeyOf(nowD)) say(`  ${key}：${names.join(", ")}`);

flush();
console.log(`\n证据落档：${outPath}`);
process.exitCode = ok ? 0 : 1;
