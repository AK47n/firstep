// survey3.mjs — 收走前 index.html 宿主脚本块的构成（工单 frontend-boot-module 的 spec 依据）。
//
// 读的是**收走前那个提交**（`git show <base>:index.html`）——搬家之后工作树里已经没有
// 那个内联块了，这里量的是"被搬走的那一块长什么样"，所以必须从 git 取。
//
// 用法：node .scratch/frontend-boot-module/survey3.mjs [--base <rev>]
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";

tee(fileURLToPath(import.meta.url), process.argv.slice(2));   // 证据落 UTF-8

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const INDEX = "src/contest_generator/static/index.html";
const args = process.argv.slice(2);
const base = args.includes("--base") ? args[args.indexOf("--base") + 1] : "b52022f1";

const html = execFileSync("git", ["show", `${base}:${INDEX}`], {
  cwd: REPO, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"],
});
const s = html.indexOf('<script type="module">');
const e = html.indexOf("</script>", s);
const block = html.slice(s, e);
const lines = block.split("\n");
const defs = lines.filter((l) => /^(export\s+)?(async\s+)?(function|class|const|let|var)\b/.test(l));
const imports = lines.filter((l) => /^\s*import\b/.test(l));
const col0 = lines.filter((l) => l.trim() && /^[^\s]/.test(l));

console.log(`base=${base}；块：${lines.length} 行 / ${Buffer.byteLength(block, "utf8")} 字节`);
console.log(`  import 行 ${imports.length}；顶层定义行 ${defs.length}${defs.length ? "：" + defs.slice(0, 5) : ""}`);
console.log(`  列 0 行 ${col0.length} 条（去掉 import 与注释的语句 ${col0.filter((l) => !/^import\b/.test(l.trim()) && !l.trim().startsWith("//")).length}）`);
console.log(`  </script> 前是否有换行：${block.endsWith("\n") ? "有" : "无"}`);
const after = html.slice(e);
console.log(`  </script> 之后（${after.split("\n").length - 1} 行）：${after.split("\n").slice(0, 4).join(" | ")}`);
