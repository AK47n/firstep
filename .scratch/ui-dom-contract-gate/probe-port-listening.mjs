// 夹具自检：portListening 的判据（工单 ui-dom-contract-gate/01 评审整改时抓到的错法）。
// 起一个真监听 → 必须判"有监听"；相邻端口 → 必须判"空闲"；关掉 → 必须回到"空闲"。
// 用法：node .scratch/ui-dom-contract-gate/probe-port-listening.mjs
import { readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "node:net";

// portListening 没导出（夹具内部件）——从源码里抠出来单跑，判据同一份实现。
const SRC = readFileSync(new URL("../../tests/browser/server.mjs", import.meta.url), "utf8");
const START = SRC.indexOf("function portListening(");
const END = SRC.indexOf("\n}\n", START) + 3;
const body = SRC.slice(START, END);
const tmp = join(tmpdir(), `port-listening-${Date.now()}.mjs`);
writeFileSync(tmp, `import { spawn } from "node:child_process";\n${body}\nexport { portListening };\n`);
const { portListening } = await import(`file://${tmp.replace(/\\/g, "/")}`);
rmSync(tmp, { force: true });

const srv = createServer();
await new Promise((r) => srv.listen(0, "127.0.0.1", r));
const port = srv.address().port;

const listening = await portListening(port);
const neighbour = await portListening(port === 65535 ? port - 1 : port + 1);
await new Promise((r) => srv.close(r));
await new Promise((r) => setTimeout(r, 300));
const afterClose = await portListening(port);

console.log(`监听中 ${port} → ${listening}（期望 true）`);
console.log(`相邻端口 → ${neighbour}（期望 false）`);
console.log(`关闭后 ${port} → ${afterClose}（期望 false）`);
const ok = listening === true && neighbour === false && afterClose === false;
console.log(ok ? "PASS" : "FAIL");
process.exitCode = ok ? 0 : 1;
