// probe-01a-mask-equivalence.mjs — 硬判：`maskCommentsAndStrings` 的**行为与 base 逐字符相同**
// （工单 module-import-usage/01 的验收项）。做法：把 base 的 boot-contract.mjs 取到临时目录 import，
// 与新实现逐文件比输出；顺带量 maskNonCode 与它的差集（只在含 `${` 的地方差）。
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { maskCommentsAndStrings, maskNonCode, listJs } from "../../tests/js/boot-contract.mjs";

const BASE = process.argv[2] || "f1c9e1c7";
const REPO = fileURLToPath(new URL("../../", import.meta.url));
const dir = mkdtempSync(join(tmpdir(), "mask-base-"));
const tmpFile = join(dir, "boot-contract-base.mjs");
writeFileSync(tmpFile, execFileSync("git", ["show", `${BASE}:tests/js/boot-contract.mjs`], { cwd: REPO, encoding: "utf8" }), "utf8");
const old = await import(pathToFileURL(tmpFile).href);

const sources = [];
for (const rel of ["src/contest_generator/static/js", "tests/js", "tests/browser"]) {
  const abs = `${REPO}${rel}`.replace(/[\\/]+$/, "");
  for (const p of listJs(abs)) sources.push({ p, text: readFileSync(p, "utf8") });
}
// 也扫 .mjs（判据面自己）——那是模板串最密的地方
import { readdirSync } from "node:fs";
const walkMjs = (abs) => {
  for (const e of readdirSync(abs, { withFileTypes: true })) {
    const child = `${abs}/${e.name}`;
    if (e.isDirectory()) walkMjs(child);
    else if (e.name.endsWith(".mjs")) sources.push({ p: child, text: readFileSync(child, "utf8") });
  }
};
for (const rel of ["tests/js"]) walkMjs(`${REPO}${rel}`.replace(/[\/]+$/, ""));

let diff = 0, nonCodeDiffers = 0, files = 0;
for (const { p, text } of sources) {
  files++;
  const a = old.maskCommentsAndStrings(text);
  const b = maskCommentsAndStrings(text);
  if (a !== b) { diff++; console.log(`  ✗ 输出不同：${p}`); }
  if (maskNonCode(text) !== b) nonCodeDiffers++;
}
console.log(`扫描文件：${files}`);
console.log(`maskCommentsAndStrings vs base 输出不同的文件：${diff}（必须 0）`);
console.log(`maskNonCode 与它不同的文件（= 含模板表达式）：${nonCodeDiffers}（>0 说明新口径真的在起作用）`);
// 合成对照：模板表达式里 `esc` 的使用
const tpl = 'import { esc } from "./core.js";\nconst h = `<b>${esc(x)}</b>`;\n';
console.log(`合成：模板表达式里的 esc —— maskCommentsAndStrings 判死？${!/esc/.test(maskCommentsAndStrings(tpl).split("\n")[1])}；maskNonCode 判活？${/esc/.test(maskNonCode(tpl).split("\n")[1])}`);
rmSync(dir, { recursive: true, force: true });
process.exit(diff === 0 && nonCodeDiffers > 0 ? 0 : 1);
