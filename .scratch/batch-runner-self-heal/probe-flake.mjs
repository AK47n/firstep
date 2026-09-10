// 取证探针（工单 batch-runner-self-heal/01）：**确定性偶发**——第一次红、第二次绿。
// 与 Chrome 无关，只靠状态文件计数，故「首红复绿」是确定发生的，不靠运气。
// （批跑器会给每支脚本设 `CDP_BATCH_TARGET` 约定标签页；本探针不连 CDP，故忽略之。）
// 用法：node .scratch/batch-runner-self-heal/probe-flake.mjs
import { readFileSync, writeFileSync, rmSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const STATE = join(HERE, "tmp-flake-state.txt");

// 状态文件缺失 = 第 1 次（不能 ENOENT 崩掉：那会让探针连「确定性红」都不是）
const prev = existsSync(STATE) ? readFileSync(STATE, "utf8").trim() : "0";
const n = Number(prev || "0") + 1;
writeFileSync(STATE, String(n), "utf8");

if (n < 2) {
  console.log("PASS 0 / FAIL 1 | 确定性偶发探针：第 1 次故意红");
  process.exit(1);
}
console.log("PASS 1 / FAIL 0 | 确定性偶发探针：第 2 次绿（首红复绿 = 偶发）");
rmSync(STATE, { force: true });        // 不留状态：下一次整批从「第 1 次红」重新开始
process.exit(0);
