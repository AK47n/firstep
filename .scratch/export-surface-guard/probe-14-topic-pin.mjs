// probe-14-topic-pin.mjs — 核验工单 02 点名的两件事（读数，不改任何文件）：
//   ① 摘掉 `ui/topic.js::initTopicToolbar` 的 `export` 后，登记体检仍由 `initTopicPanel` 的调用点满足；
//   ② "行数只减不增"的真正口径（`git diff` 的 "insertions" 是**改写行**，不是新增内容行）。
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, readConsumerModules, registryProblems, maskCommentsAndStrings,
  parseModuleExports,
} from "../../tests/js/boot-contract.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${ROOT}src/contest_generator/static`;
const modules = readJsModules(STATIC);
const root = readLoadRoot(STATIC);

// ① 登记体检
const problems = registryProblems(root, modules);
console.log(`① registryProblems：${problems.length} 处${problems.length ? " —— " + JSON.stringify(problems) : "（绿）"}`);

// ② initTopicToolbar 的调用点仍在（在 initTopicPanel 里）
const topic = modules.find((m) => m.key === "ui/topic.js").text;
const masked = maskCommentsAndStrings(topic);
const callSites = [...masked.matchAll(/(?<![\w$.])initTopicToolbar\s*\(/g)]
  .map((m) => masked.slice(0, m.index).split("\n").length);
console.log(`② ui/topic.js 里 initTopicToolbar 的**代码**调用点：第 ${callSites.join(" / ")} 行`);
console.log(`   还有 export 吗？${/export\s+(async\s+)?(function|const|let|var)\s+initTopicToolbar/.test(masked)}`);
const inits = parseModuleExports(topic);
console.log(`   ui/topic.js 现在的导出面：${[...inits].join(", ")}`);

// ③ 行数口径
const git = (...a) => execFileSync("git", a, { cwd: ROOT, encoding: "utf8", maxBuffer: 1 << 28 });
const short = git("-c", "core.safecrlf=false", "diff", "--shortstat", "--", "src/contest_generator/static/js").trim();
const numstat = git("-c", "core.safecrlf=false", "diff", "--numstat", "--", "src/contest_generator/static/js")
  .split("\n").filter(Boolean).map((l) => l.split("\t").map(Number));
const sum = numstat.reduce((a, [add, del]) => [a[0] + add, a[1] + del], [0, 0]);
console.log(`③ git --shortstat：${short}`);
console.log(`   numstat 汇总：+${sum[0]} / -${sum[1]}（净 ${sum[0] - sum[1]} 行）`);
console.log("   口径说明：被改写的行（摘掉 `export ` 前缀）在 git 里算「一删一增」，");
console.log(`   但那 ${sum[0]} 条「新增」行逐条都是某条删除行去掉 \`export \` 前缀（或清单重排）后的样子`);
console.log("   （见 probe-11 的归因）；所以**文件行数**只减不增——apply-sweep 逐文件核对（净 " + (sum[0] - sum[1]) + " 行）。");
