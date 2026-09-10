// 取证（第十轮续）：`refine/smoke-01` 在**批跑上下文**里偶发（单跑 6/6 绿、批内约 1/3 红），
// 且失败时长 ≈45s（= 等待预算耗尽）。批跑器只打印 stdout 末 6 行 → 看不到是哪几项红。
//
// 本脚本 = 反复跑 refine 全批，但把 smoke-01 那一支的**完整 stdout/stderr** 落盘，
// 失败即停并打印全文，供定性「是树点击丢失、还是读盘慢、还是别的」。
//
// 用法：node .scratch/code-editor-refine/diag-capture-fail.mjs [最多轮数]
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFileSync, readFileSync } from "node:fs";
import { rebuildTab } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const ROUNDS = Number(process.argv[2] || 4);
const SCRIPTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  .map((i) => `.scratch/code-editor-refine/smoke-${String(i).padStart(2, "0")}.mjs`);

for (let round = 1; round <= ROUNDS; round++) {
  console.log(`===== 第 ${round} 轮 =====`);
  for (const script of SCRIPTS) {
    await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
    const t0 = Date.now();
    const r = spawnSync(process.execPath, [join(ROOT, script)], {
      encoding: "utf8", timeout: 120000, cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: "utf8" },
    });
    const ms = Date.now() - t0;
    const out = (r.stdout || "") + (r.stderr || "");
    const tail = (r.stdout || "").trim().split("\n").slice(-1)[0];
    console.log(`${r.status === 0 ? "PASS" : "FAIL"} ${script.split("/").pop().padEnd(14)} ${String(ms).padStart(6)}ms | ${tail}`);
    if (r.status !== 0) {
      const f = join(OUT, `fail-capture-${Date.now()}.txt`);
      writeFileSync(f, `# ${script} exit=${r.status} ${ms}ms\n\n` + out, "utf8");
      console.log("\n---- 完整输出（已落盘 " + f + "）----");
      console.log(out);
      process.exit(1);
    }
  }
}
console.log(`\n${ROUNDS} 轮全绿（未复现）`);
