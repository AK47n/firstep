// Windows 文本编码守卫（工单 gen-chain-audit/04）。
//
// 本轮踩过的三个坑，都值得钉住（前两个把工作直接打废过）：
//   ① 用 PowerShell 的 `Set-Content -Encoding utf8` **回写**源码/测试文件：Windows
//      PowerShell 5.1 按系统 ANSI 读原文件、再按 `utf8` 写（还带 BOM）——中文
//      UTF-8 源文件被读成 GBK 再写成 UTF-8，整份变双重编码乱码（本轮
//      `gen-chain-audit.mjs` 因此报废重写一次）。
//   ② 用 `Tee-Object` / `>` 落审计日志：Windows PowerShell 写的是 **UTF-16LE**，
//      日志整份乱码且 `Select-String` 再也匹配不到（本轮 `.scratch/gen-chain-audit/`
//      的日志全废，改成 node 的 spawnSync 收集 stdout 再 writeFileSync 才干净）。
//   ③ 用 PowerShell 的 `.ps1` 规范（UTF-8 **with** BOM）去要求 .js —— 相反，本仓的
//      JS 不该有 BOM（`tests/test_ps1_encoding.py` 只管 .ps1）。
//
// 判据（对**本仓自有**的源与文本产物）：
//   a. 不得带 BOM（.ps1 例外，见 ③）；
//   b. 不得含 U+FFFD（替换字符 = 解码失败留下的疤）——**白名单见下**；
//   c. 不得是 UTF-16（前两字节 FF FE / FE FF）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));

// 覆盖面：仓库自有的源码 / 前端资源 / 测试 / 文本产物（不含第三方 sources/、
// node_modules、目录库 library/ —— 那些由各自的守卫管）。
const ROOTS = [
  "src/contest_generator/static/js",   // 递归覆盖 fx/ ui/ 与 app.js
  "tests/js",
  "tests/browser",
  ".scratch/gen-chain-audit",
];
const EXTS = new Set([".js", ".mjs", ".json", ".md", ".txt", ".css", ".html"]);

// 白名单：**故意**含 U+FFFD 的行（不是编码事故）。目前只有一处 ——
// ui/files.js 的 readPickedText 用「解码后有没有替换字符」判 UTF-8 是否解坏，
// 决定要不要回退 GBK，那个字符本身就是判据（去掉它反而是 bug）。
const UFFFD_WHITELIST = [
  "src/contest_generator/static/js/ui/files.js",
];

function walk(dir, out = []) {
  let entries = [];
  try { entries = readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of entries) {
    if (e.name === "node_modules" || e.name === ".git") continue;
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (EXTS.has(e.name.slice(e.name.lastIndexOf(".")))) out.push(p);
  }
  return out;
}

const files = ROOTS.flatMap((r) => walk(join(ROOT, r)));

test("Windows 编码守卫：自有文本文件不得带 BOM / 不得是 UTF-16 / 不得含替换字符", () => {
  const bad = [];
  for (const f of files) {
    if (!statSync(f).isFile()) continue;
    const b = readFileSync(f);
    const rel = relative(ROOT, f).replace(/\\/g, "/");
    if (b.length >= 3 && b[0] === 0xef && b[1] === 0xbb && b[2] === 0xbf) {
      bad.push(`${rel}: 带 UTF-8 BOM（PowerShell 的 -Encoding utf8 写的）`);
      continue;
    }
    if (b.length >= 2 && ((b[0] === 0xff && b[1] === 0xfe) || (b[0] === 0xfe && b[1] === 0xff))) {
      bad.push(`${rel}: 是 UTF-16（PowerShell 的 Tee-Object / > 默认写的就是它）`);
      continue;
    }
    const s = b.toString("utf8");
    const rep = (s.match(/\uFFFD/g) || []).length;
    if (rep && !UFFFD_WHITELIST.includes(rel)) {
      bad.push(`${rel}: 含 ${rep} 个替换字符 U+FFFD（解码失败/双重编码的疤）`);
    }
  }
  assert.deepEqual(bad, [],
    "以下文件编码不干净（用 node 读写，别用 PowerShell 回写 UTF-8 源文件）：\n" + bad.join("\n"));
});

test("Windows 编码守卫：覆盖面不为空（防守卫自己失效）", () => {
  assert.ok(files.length > 50, `扫描到的文件只有 ${files.length} 个 —— 守卫的根目录/后缀配置漂了`);
  // 至少得覆盖到本轮改过的那几个目录，否则守卫是摆设
  const rels = files.map((f) => relative(ROOT, f).replace(/\\/g, "/"));
  for (const must of ["tests/browser/gen-chain-audit.mjs", "src/contest_generator/static/js/fx/generate.js"]) {
    assert.ok(rels.includes(must), `覆盖面里缺 ${must}`);
  }
});
