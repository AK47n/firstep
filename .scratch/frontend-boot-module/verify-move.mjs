// verify-move.mjs — 装载根搬家的**机械判定**（工单 frontend-boot-module/02）。
//
// 判据（独立于 apply-move.mjs 的实现，重新从 git 取收走前那一代来比）：
//   ① boot.js 去掉文件头后，与 `git show <base>:index.html` 里搬走的块内容**逐字相同**
//      （行尾归一后；index.html 是 CRLF、static/js/ 下既有 JS 全是 LF）
//   ② index.html 零 import（判据①，入参 = tests/js/boot-contract.mjs 的单源）
//   ③ index.html 只有一条 type="module" 装载标签，src = /js/boot.js
//   ④ index.html 除块之外的部分**逐字节未动**（markup / CSS / 555 个 id 都在里面）
//   ⑤ 装载清单 45 条、逐字保序（顺序敏感：ESM 求值顺序 = import 书写顺序）
//
// 用法：node .scratch/frontend-boot-module/verify-move.mjs [--base <rev>]
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import { indexHtmlImports, loadRootTag, parseModuleImports } from "../../tests/js/boot-contract.mjs";

tee(fileURLToPath(import.meta.url), process.argv.slice(2));   // 证据落 UTF-8

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const INDEX = "src/contest_generator/static/index.html";
const BASE = "b52022f1";                                // 收走前那个提交（spec 现场快照）
const args = process.argv.slice(2);
const base = args.includes("--base") ? args[args.indexOf("--base") + 1] : BASE;

const git = (...a) => execFileSync("git", a, {
  cwd: REPO, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"],
});
const openTag = '<script type="module">';
const HEADER_END = "---- 以下为原 index.html 宿主块逐字搬运";

const baseHtml = git("show", `${base}:${INDEX}`);       // git 里存 LF；工作树是 CRLF → 比较前归一
const nl = (t) => t.replace(/\r\n/g, "\n");
const s = baseHtml.indexOf(openTag);
const e = baseHtml.indexOf("</script>", s);
const movedAtBase = nl(baseHtml.slice(s + openTag.length, e));
const baseOutside = nl(baseHtml.slice(0, s) + "<!-- BLOCK -->" + baseHtml.slice(e + "</script>".length));

const boot = readFileSync(REPO + "src/contest_generator/static/js/boot.js", "utf8");
const headerLine = boot.split("\n").findIndex((l) => l.includes(HEADER_END));
const movedNow = headerLine < 0 ? null : boot.split("\n").slice(headerLine + 1).join("\n");

const html = readFileSync(REPO + INDEX, "utf8");
const nowOutside = nl(html.replace(/<script type="module" src="[^"]*"><\/script>/, "<!-- BLOCK -->"));
const nowImports = indexHtmlImports(html);
const tag = loadRootTag(html);
const specs = (t) => parseModuleImports(t).map((x) => `${x.spec}|${x.names.join(",")}|${x.bare}`);
const specsBoot = specs(boot);
const specsBase = specs(movedAtBase);

const checks = [
  ["① boot.js 去掉文件头 = 收走前搬走的块内容（逐字，行尾归一后）",
    movedNow !== null && movedNow === movedAtBase,
    movedNow === null ? "boot.js 里找不到搬运分隔标记" : `${movedAtBase.split("\n").length} 行对 ${(movedNow || "").split("\n").length} 行`],
  ["② index.html 零 import", nowImports.length === 0, `${nowImports.length} 条`],
  ["③ index.html 一条装载标签且 src=/js/boot.js",
    tag.count === 1 && tag.src === "/js/boot.js", `count=${tag.count} src=${tag.src}`],
  ["④ index.html 除块之外逐字节未动", nowOutside === baseOutside,
    nowOutside === baseOutside ? "一致" : "不一致（markup/CSS 被动过？）"],
  ["⑤ 装载清单 45 条且逐字保序",
    specsBoot.length === specsBase.length && specsBoot.every((x, i) => x === specsBase[i]),
    `${specsBase.length} 条（base）→ ${specsBoot.length} 条（boot.js）`],
  ["⑥ index.html 的 id 声明数不变",
    (html.match(/\bid="/g) || []).length === (baseHtml.match(/\bid="/g) || []).length,
    `${(baseHtml.match(/\bid="/g) || []).length} → ${(html.match(/\bid="/g) || []).length}`],
  ["⑦ index.html 的 CSS/标记行数不变（块除外）",
    nl(html).split("\n").length === nl(baseHtml).split("\n").length - (476 - 1),
    `${nl(baseHtml).split("\n").length} → ${nl(html).split("\n").length}（−475）`],
];

for (const [name, ok, note] of checks) console.log(`${ok ? "✔" : "✗"} ${name} —— ${note}`);
const failed = checks.filter(([, ok]) => !ok).length;
console.log(`\n${failed ? "FAIL" : "PASS"}：${checks.length - failed}/${checks.length} 条成立（base=${base}）`);
process.exitCode = failed ? 1 : 0;
