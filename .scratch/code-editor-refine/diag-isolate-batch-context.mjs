// 取证（第十轮续·A/B）：`refine/smoke-01` 的偶发到底是不是**批内上下文**造成的？
// 对照两组，各自 N 轮（每轮前重建标签页，与批跑器同约定），失败即捕获完整 stdout：
//   A 组：单跑 smoke-01（预期参考：之前实测 6/6 绿）
//   B 组：先跑 smoke-02..10，再跑 smoke-01（= 模拟批内顺序）
// 用法：node .scratch/code-editor-refine/diag-isolate-batch-context.mjs [每组轮数]
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFileSync } from "node:fs";
import { rebuildTab } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const N = Number(process.argv[2] || 6);
const S01 = ".scratch/code-editor-refine/smoke-01.mjs";
const OTHERS = [2, 3, 4, 5, 6, 7, 8, 9, 10]
  .map((i) => `.scratch/code-editor-refine/smoke-${String(i).padStart(2, "0")}.mjs`);

const run = async (script) => {
  await rebuildTab({ port: 9251, pageUrl: "http://127.0.0.1:8000/" });
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [join(ROOT, script)], {
    encoding: "utf8", timeout: 120000, cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: "utf8" },
  });
  return { status: r.status, ms: Date.now() - t0, out: (r.stdout || "") + (r.stderr || "") };
};

const found = [];
for (const group of ["A 单跑", "B 批内（先 02..10）"]) {
  console.log(`===== ${group} =====`);
  for (let i = 1; i <= N; i++) {
    if (group.startsWith("B")) {
      for (const s of OTHERS) {
        const r = await run(s);
        if (r.status !== 0) console.log(`  （前序 ${s.split("/").pop()} 也红了：exit=${r.status}）`);
      }
    }
    const r = await run(S01);
    console.log(`  ${group} 第 ${i} 次：${r.status === 0 ? "PASS" : "FAIL"} ${r.ms}ms`);
    if (r.status !== 0) {
      const f = join(ROOT, ".scratch", "code-editor-refine", `fail-capture-${group[0]}-${Date.now()}.txt`);
      writeFileSync(f, `# ${group} 第 ${i} 次 FAIL ${r.ms}ms\n\n` + r.out, "utf8");
      console.log("\n---- 完整输出（已落盘 " + f + "）----\n" + r.out);
      found.push({ group, i, ms: r.ms });
      break;
    }
  }
}
console.log("\n---- 汇总 ----");
console.log(found.length ? JSON.stringify(found) : `两组各 ${N} 次全绿（该条件下未复现）`);
