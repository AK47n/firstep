// 批跑器（工单 code-editor-cdp-hang/01 验收项 ④）：按「每支前重建标签页」约定批量跑 CDP 冒烟脚本。
//
// 约定落地方式：**不改各脚本**——由本 runner 在每支脚本启动前用 CDP 重建标签页
// （json/close/<id> + PUT json/new?<url>），保证每支脚本拿到的都是干净页（无脏缓冲 →
// 不会弹 beforeunload 对话框 → 不会挂死）。`--no-rebuild` 用于对照复现挂死。
//
// 用法：
//   node .scratch/cdp-smoke-run.mjs --port=9251 --scripts=a.mjs,b.mjs [--timeout=90] [--no-rebuild] [--rounds=1]
//   node .scratch/cdp-smoke-run.mjs --batch=overhaul          # 预置批次
//
// 输出：逐支 PASS/FAIL/挂死 + 汇总；挂死时打印现场并自动重建标签页恢复。
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import { rebuildTab, pageTarget, connect } from "./cdp-harness.mjs";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));   // 仓库根（本文件在 .scratch/ 下，往上两级）
const OUT = join(ROOT, ".scratch", "cdp-smoke-runs");
mkdirSync(OUT, { recursive: true });
const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const PORT = Number(argOf("port", "9251"));
const PAGE_URL = argOf("page", "http://127.0.0.1:8000/");
const TIMEOUT_S = Number(argOf("timeout", "90"));
const ROUNDS = Number(argOf("rounds", "1"));
const NO_REBUILD = argv.includes("--no-rebuild");
const BATCH = argOf("batch", "");

const BATCHES = {
  overhaul: [1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => `.scratch/code-page-vscode-overhaul/smoke-0${i}.mjs`),
  polish: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => `.scratch/code-editor-vscode-polish/smoke-0${i}.mjs`),
  refine: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => `.scratch/code-editor-refine/smoke-${String(i).padStart(2, "0")}.mjs`),
  viewer: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((i) => `.scratch/code-viewer-editor/smoke-${String(i).padStart(2, "0")}.mjs`),
  ideai: [5, 6, 7, 8].map((i) => `.scratch/code-ide-ai/smoke-0${i}.mjs`),
  treeops: [".scratch/code-tree-ops/smoke.mjs"],
  ideflow: [2, 3, 4].map((i) => `.scratch/code-ide-flow/smoke-0${i}.mjs`),
  bridge: [1, 2, 3, 4, 5].map((i) => `.scratch/mainc-codeview-bridge/smoke-0${i}.mjs`),
  libui: [
    ".scratch/master-library-ui-2/smoke.mjs",
    ".scratch/reference-library-ui/smoke.mjs",
    ".scratch/pdf-library-ui/smoke.mjs",
    ".scratch/module-library-ui/smoke.mjs",
  ],
  fem: [".scratch/frontend-es-modules/smoke.mjs"],
};

let SCRIPTS = argOf("scripts", "").split(",").map((s) => s.trim()).filter(Boolean);
if (!SCRIPTS.length && BATCH) {
  if (!BATCHES[BATCH]) { console.error(`未知批次 ${BATCH}（可选：${Object.keys(BATCHES).join(", ")}）`); process.exit(2); }
  SCRIPTS = BATCHES[BATCH];
}
if (!SCRIPTS.length) { console.error("请给 --scripts=a.mjs,b.mjs 或 --batch=<名>"); process.exit(2); }

const results = [];
let hangs = 0, fails = 0, passes = 0;

for (let round = 1; round <= ROUNDS; round++) {
  for (const script of SCRIPTS) {
    const name = script.replace(/^\.scratch\//, "");
    if (!NO_REBUILD) {
      const t = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
      if (!t) { console.error(`!! 无法重建标签页（CDP ${PORT} 不可达？）`); process.exit(3); }
    }
    const t0 = Date.now();
    if (argv.includes("--debug-path")) console.log(`      spawn: ${JSON.stringify(join(ROOT, script))} cwd=${JSON.stringify(ROOT)} exists=${existsSync(join(ROOT, script))}`);
    const r = spawnSync(process.execPath, [join(ROOT, script)], {
      encoding: "utf8", timeout: TIMEOUT_S * 1000, cwd: ROOT,
      env: { ...process.env, PYTHONIOENCODING: "utf8" },
    });
    const ms = Date.now() - t0;
    const out = (r.stdout || "") + (r.stderr || "");
    const tail = (r.stdout || "").trim().split("\n").slice(-2).join(" | ");
    const timedOut = !!(r.error && r.error.code === "ETIMEDOUT");
    const hangSig = /CDP 无响应|页面可能已挂死|页面未就绪|CDP 不可达/.test(out);
    // 现场判定：命令还回不回来
    let forensics = null;
    if (timedOut || hangSig) {
      const t = await pageTarget({ port: PORT, pageUrl: PAGE_URL, anyPage: true });
      try {
        const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 6000 });
        forensics = { eval_1plus1: await c.Eval("1+1", 6000), target: t && t.id.slice(0, 8) };
        c.close();
      } catch (e) {
        forensics = { unresponsive: String(e), target: t && t.id.slice(0, 8) };
      }
    }
    const hung = timedOut || (hangSig && forensics && forensics.unresponsive);
    const pass = !hung && r.status === 0;
    if (hung) hangs++; else if (pass) passes++; else fails++;
    const rec = { round, script: name, ms, exit: r.status, timedOut, hung, pass, tail, forensics };
    results.push(rec);
    const mark = hung ? "挂死" : pass ? "PASS" : "FAIL";
    console.log(`r${round} ${mark.padEnd(4)} ${name.padEnd(52)} exit=${String(r.status).padStart(4)} ${String(ms).padStart(6)}ms | ${tail}`);
    if (!pass) {
      const errTail = (r.stderr || "").trim().split("\n").slice(-12).join("\n       ");
      if (errTail) console.log(`      stderr: ${errTail}`);
      const outTail = (r.stdout || "").trim().split("\n").slice(-6).join("\n       ");
      if (outTail) console.log(`      stdout: ${outTail}`);
    }
    if (hung) {
      console.log(`      现场：${JSON.stringify(forensics)}`);
      const t = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
      console.log(`      已重建标签页恢复：${t ? "OK" : "失败"}`);
    }
  }
}
console.log(`\n---- 汇总 ----`);
console.log(`PASS ${passes} / FAIL ${fails} / 挂死 ${hangs}（共 ${results.length} 支次，${NO_REBUILD ? "未重建标签页（对照）" : "每支前重建标签页"}）`);
writeFileSync(join(OUT, `run-${Date.now()}.json`), JSON.stringify({ port: PORT, batch: BATCH || "(scripts)", noRebuild: NO_REBUILD, results }, null, 2), "utf8");
process.exit(hangs || fails ? 1 : 0);
