// probe-01-red-proof.mjs — 真红证（工单 launcher-exit-race/01）：
// 把**判据⑥「早注册」**（判据单源 = `tests/js/boot-contract.mjs`）作用在**修复前那个提交**
// 的源码上，证明它真的会红；再在当前工作树上复算一遍（要求绿）。
//
// 手法（照 `.scratch/frontend-boot-module/probe-01-red-proof.mjs` 先例）：
//   · 只读：`git show <base>:<path>`，不碰工作区、不改仓库文件；
//   · **base 必须显式钉住，不能写 HEAD**：本工单提交之后 HEAD 就是修好的代码，拿 HEAD
//     当"修复前"会让红证静默变绿（2026-09-20 刚踩过这个坑）；
//   · **base 自校验**：base 的 `index.html` 内联脚本里**没有** register、而 base 的 `app.js`
//     **有** register —— 两条任一不成立就大声失败，绝不产出假绿。
//
// 判据强度（每条子判据的合成反例）住在闸门内的 `tests/js/tab-register-guard.test.mjs` ——
// 那里是唯一一份合成用例表，本探针不抄第二份（先例：module-import-usage 的双轴评审
// 抓到过"闸门与红证各抄一张表、已经分叉"）。
//
// 用法：
//     node .scratch/launcher-exit-race/probe-01-red-proof.mjs
//     node .scratch/launcher-exit-race/probe-01-red-proof.mjs --base <rev>
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import { TAB_REGISTER_ENDPOINT, earlyRegisterProblems, scriptBlocks } from "../../tests/js/boot-contract.mjs";

tee(process.argv[1], process.argv.slice(2));

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const INDEX = "src/contest_generator/static/index.html";
const APP = "src/contest_generator/static/js/app.js";

// 修复前那个提交（本单开工时的 HEAD：工单 module-import-usage/03 的收尾提交）
const BASE = "eae57b43";

const args = process.argv.slice(2);
const base = args.includes("--base") ? args[args.indexOf("--base") + 1] : BASE;

const git = (...a) => execFileSync("git", a, {
  cwd: REPO, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"],
});
const gitOrNull = (...a) => {
  try { return git(...a); } catch { return null; }
};

/**
 * 内联脚本里在装载标签**之前**有没有 register 调用 —— 给**人读**的读数（偏移量），
 * **不是第二条判据**：结论一律来自 `earlyRegisterProblems`。这里重算块偏移只是为了把
 * "登记在装载标签之前"这件事打印成可核对的两个数字。
 */
function earlyRegisterSummary(html) {
  const blocks = scriptBlocks(html);
  const inline = blocks.filter((b) => b.src === null);
  const tag = blocks.find((b) => /type\s*=\s*["']module["']/i.test(b.attrs));
  const hit = inline.find((b) => b.text.includes(TAB_REGISTER_ENDPOINT));
  return {
    files: blocks.length,
    inline: inline.length,
    tagAt: tag ? tag.index : null,
    registerAt: hit ? hit.index + hit.raw.indexOf(">") + 1 : null,
  };
}

// ---------------------------------------------------------------------------
// ① base 自校验：选错就大声失败
// ---------------------------------------------------------------------------
const baseHtml = gitOrNull("show", `${base}:${INDEX}`);
const baseApp = gitOrNull("show", `${base}:${APP}`);
if (baseHtml === null || baseApp === null) {
  console.error(`✗ base ${base} 里读不到 ${INDEX} / ${APP} —— 换 --base`);
  process.exit(2);
}
const selfCheck = [];
if (baseHtml.includes(TAB_REGISTER_ENDPOINT)) {
  selfCheck.push("base 的 index.html 里已经有 register —— 这不是修复前那一代");
}
if (!baseApp.includes(TAB_REGISTER_ENDPOINT)) {
  selfCheck.push("base 的 app.js 里没有 register —— 判据⑥ 在 base 上不可能因为「登记住错地方」红");
}
console.log(`== ① base 自校验（base=${base}）==`);
console.log(`  base index.html：内联脚本里 register 字样 ${baseHtml.includes(TAB_REGISTER_ENDPOINT) ? "有（错）" : "没有（对）"}`);
console.log(`  base app.js：register 调用 ${baseApp.includes(TAB_REGISTER_ENDPOINT) ? "有（对：登记住在模块里）" : "没有（错）"}`);
if (selfCheck.length) {
  console.error("✗ base 选错，红证会静默变绿 —— 拒绝继续：");
  for (const line of selfCheck) console.error("  · " + line);
  process.exit(2);
}
console.log("  ✓ 通过（base 是修复前那一代）");

// ---------------------------------------------------------------------------
// ② 同一套判据作用在 base 上：必红
// ---------------------------------------------------------------------------
const baseProblems = earlyRegisterProblems(baseHtml, baseApp);
console.log(`\n== ② 判据⑥ 作用在 base 上（应红）==`);
for (const p of baseProblems) console.log(`  · ${p.why}`);
const baseSummary = earlyRegisterSummary(baseHtml);
console.log(`  读数：脚本块 ${baseSummary.files} 个 / 内联 ${baseSummary.inline} 个；`
  + `装载标签偏移 ${baseSummary.tagAt}；内联脚本里的 register 偏移 ${baseSummary.registerAt ?? "（没有）"}`);
const redOk = baseProblems.some((p) => p.why.includes("内联"));

// ---------------------------------------------------------------------------
// ③ 判据作用在当前工作树上：要求绿
// ---------------------------------------------------------------------------
const nowHtml = readFileSync(REPO + INDEX, "utf8");
const nowApp = readFileSync(REPO + APP, "utf8");
const nowProblems = earlyRegisterProblems(nowHtml, nowApp);
const nowSummary = earlyRegisterSummary(nowHtml);
console.log(`\n== ③ 当前工作树读数（本工单要求绿）==`);
console.log(`  判据⑥ 违规：${nowProblems.length} 条${nowProblems.length ? "（红：" + nowProblems.map((p) => p.why).join("；") + "）" : "（绿）"}`);
console.log(`  读数（给人看，不是判据）：脚本块 ${nowSummary.files} 个 / 内联 ${nowSummary.inline} 个；`
  + `装载标签偏移 ${nowSummary.tagAt}；内联脚本里的 register 偏移 ${nowSummary.registerAt}`);
console.log(`  登记点单源：app.js 里 ${nowApp.includes(TAB_REGISTER_ENDPOINT) ? "**仍有** register（红）" : "已无 register（对）"}`);

// ---------------------------------------------------------------------------
// ④ 判据不是真空绿：喂一份"没有任何登记"的最小 HTML，必须报出
// ---------------------------------------------------------------------------
const bare = '<html><head><script>\n  var x = 1;\n</script></head>'
  + '<body><script type="module" src="/js/boot.js"></script></body></html>';
const bareProblems = earlyRegisterProblems(bare, baseApp);
console.log(`\n== ④ 判据非真空自检（最小 HTML，应报出）==`);
console.log(`  ${bareProblems.length ? "✔ 报出 " + bareProblems.length + " 条：" + bareProblems[0].why : "✗ 没报出（判据真空绿）"}`);

// ---------------------------------------------------------------------------
// 结论
// ---------------------------------------------------------------------------
const greenNow = nowProblems.length === 0
  && !nowApp.includes(TAB_REGISTER_ENDPOINT)
  && nowSummary.files === 2
  && nowSummary.registerAt !== null && nowSummary.tagAt !== null
  && nowSummary.registerAt < nowSummary.tagAt;
const ok = redOk && greenNow && bareProblems.length > 0;
console.log(`\n== 结论 ==`);
console.log(`  红证（base 上必红）：${redOk ? "成立" : "不成立"}`);
console.log(`  当前工作树：${greenNow ? "绿" : "红"}`);
console.log(ok ? "\nPASS（判据在修复前那一代上真会红，且当前树满足早注册契约）" : "\nFAIL");
process.exitCode = ok ? 0 : 1;
