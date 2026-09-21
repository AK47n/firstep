// survey2.mjs — 逐模块的**接线清单**（工单 frontend-boot-module 的 spec 依据，非判据）。
//
// 读的是**收走前那个提交**（`git show <base>:…`，缺省 b52022f1）——那是工单 03/04 的作业单：
// 11 个模块各自"要求值期执行多少条接线、分别是哪几行"。搬家之后工作树里这些语句已经不在
// 顶层了，所以缺省取 git；想量当前工作树加 `--worktree`。
//
// 判据/解析全部 import 自 tests/js/boot-contract.mjs（单源）。
//
// 用法：node .scratch/frontend-boot-module/survey2.mjs [--base <rev>] [--worktree]
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import { readJsModules, readLoadRoot, parseModuleImports, wiringEffects } from "../../tests/js/boot-contract.mjs";

tee(fileURLToPath(import.meta.url), process.argv.slice(2));   // 证据落 UTF-8

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const JS_DIR = "src/contest_generator/static/js";
const STATIC = REPO + "src/contest_generator/static";
const args = process.argv.slice(2);
const worktree = args.includes("--worktree");
const base = args.includes("--base") ? args[args.indexOf("--base") + 1] : "b52022f1";

let modules;
let root;
let where;
if (worktree) {
  modules = readJsModules(STATIC);
  root = readLoadRoot(STATIC) || "";
  where = "当前工作树";
} else {
  const git = (...a) => execFileSync("git", a, {
    cwd: REPO, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"],
  });
  const paths = git("ls-tree", "-r", "--name-only", base, "--", JS_DIR)
    .split("\n").map((s) => s.trim()).filter((p) => p.endsWith(".js"));
  modules = paths.map((p) => ({ key: p.slice(JS_DIR.length + 1), text: git("show", `${base}:${p}`) }));
  const html = git("show", `${base}:src/contest_generator/static/index.html`);
  const s = html.indexOf('<script type="module">');
  root = html.slice(s + '<script type="module">'.length, html.indexOf("</script>", s));
  where = `收走前那个提交 ${base}`;
}

// 本次 spec「实现决策」B 档的 11 个模块（裸装载 5 ＋ boot 唯一来源 6）
const SCOPED = [
  "ui/generate-revise.js", "ui/generate-tasks.js", "ui/params.js", "ui/params-chat.js",
  "ui/delivery.js", "ui/generate-core.js", "ui/library.js", "ui/master.js",
  "ui/reference.js", "ui/topic.js", "ui/code-fix-panel.js",
];

console.log(`来源：${where}；装载根 ${parseModuleImports(root).length} 条 import\n`);
let total = 0;
for (const key of SCOPED) {
  const m = modules.find((x) => x.key === key);
  if (!m) { console.log(`✗ ${key} 不在模块表里`); continue; }
  const effects = wiringEffects(m.text);
  total += effects.length;
  console.log(`== ${key}：求值期接线 ${effects.length} 条`);
  for (const e of effects) console.log(`     ${String(e.line).padStart(5)}: ${e.text.slice(0, 92)}`);
}
console.log(`\n合计 ${total} 条接线语句（11 个模块）`);
