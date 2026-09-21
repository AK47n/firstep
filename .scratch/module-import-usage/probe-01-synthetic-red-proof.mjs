// probe-01-synthetic-red-proof.mjs — 合成红证 CLI（工单 module-import-usage/01）。
//
// 用例表单源在 synthetic-cases.mjs（probe-02 的真红证第 ④ 段也用它）。
// 全成立 → 退出 0 并写 synthetic-red-proof.txt；任一条不成立 → 打印并非零退出。
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { syntheticChecks, CASES } from "./synthetic-cases.mjs";

const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };

const results = syntheticChecks();
say("=== 合成红证：判据的假绿反例 ＋ 防假红反向对照（module-import-usage/01）===");
say(`用例数：${CASES.length}`);
say("");
say("逐条（判据 = tests/js/import-usage.mjs::unusedImports；差分校准见用例表）：");
for (const r of results) {
  say(`  ${r.ok ? "PASS" : "FAIL"}  ${r.id.padEnd(32)} ${r.why}`);
  if (!r.ok) say(`        ↳ ${r.detail}`);
}
const bad = results.filter((r) => !r.ok);
say("");
say(`合成自检：${results.length - bad.length}/${results.length} 成立`);
say(bad.length ? `**FAIL**：${bad.map((b) => b.id).join(", ")}` : "**PASS**");
writeFileSync(fileURLToPath(new URL("./synthetic-red-proof.txt", import.meta.url)), lines.join("\n") + "\n", "utf8");
process.exit(bad.length ? 1 : 0);
