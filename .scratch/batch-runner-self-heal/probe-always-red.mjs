// 取证探针（工单 batch-runner-self-heal/01）：**真红（无事件）**——永远断言失败。
// 与 probe-flake.mjs 的区别：不给状态、不给转机，用于验证「两次都红 = 真红」与
// 非绿支次落盘（本例事件序列应为空：探针不连 CDP）。
// 用法：node .scratch/batch-runner-self-heal/probe-always-red.mjs
console.log("PASS 5 / FAIL 2 | 真红探针：永远红（无事件序列）");
process.exit(1);
