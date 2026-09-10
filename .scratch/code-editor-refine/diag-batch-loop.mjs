// 取证（第十轮收尾）：走**完整 refine 批顺序**（01 在前，与 cdp-smoke-run 的 refine 批一致），
// 反复若干轮，统计 smoke-01 的复现率（改版前：单跑 6/6 绿、批内约 1/3 红、另有 A 组第 2 次红）。
// 每轮前重建标签页（与批跑器同约定）；失败即落盘完整输出。
// 用法：node .scratch/code-editor-refine/diag-batch-loop.mjs [轮数]
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFileSync } from "node:fs";
import { rebuildTab } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const ROUNDS = Number(process.argv[2] || 5);
const SCRIPTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  .map((i) => `.scratch/code-editor-refine/smoke-${String(i).padStart(2, "0")}.mjs`);

let fail01 = 0, otherFails = [];
for (let round = 1; round <= ROUNDS; round++) {
  let s01 = null;
  for (const script of SCRIPTS) {
    await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
    const t0 = Date.now();
    const r = spawnSync(process.execPath, [join(ROOT, script)], {
      encoding: "utf8", timeout: 120000, cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: "utf8" },
    });
    const ms = Date.now() - t0;
    const out = (r.stdout || "") + (r.stderr || "");
    const name = script.split("/").pop();
    if (name === "smoke-01.mjs") s01 = { status: r.status, ms, out };
    else if (r.status !== 0) otherFails.push(`${name} exit=${r.status}`);
  }
  console.log(`第 ${round} 轮：smoke-01 ${s01.status === 0 ? "PASS" : "FAIL"} ${s01.ms}ms | ${(s01.out.trim().split("\n").slice(-1)[0] || "")}`);
  if (s01.status !== 0) {
    fail01++;
    const f = join(ROOT, ".scratch", "code-editor-refine", `batch-loop-fail-${Date.now()}.txt`);
    writeFileSync(f, `# 第 ${round} 轮 smoke-01 FAIL ${s01.ms}ms\n\n` + s01.out, "utf8");
    console.log(s01.out);
    console.log("已落盘 " + f);
  }
}
console.log(`\n---- ${ROUNDS} 轮：smoke-01 失败 ${fail01} 次；其它脚本失败 ${otherFails.length} 次 ${JSON.stringify(otherFails)} ----`);
