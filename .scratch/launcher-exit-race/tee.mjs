// tee.mjs — 把脚本打印的内容**同时**落一份 UTF-8 文件（工单 frontend-boot-module 的探针基建）。
//
// 为什么需要它：本机 PowerShell 的 `node x.mjs > out.txt` 会把 stdout 写成 **UTF-16LE**，
// 于是证据文件在 read/grep 工具里被当成二进制、中文整份乱码（本仓
// `tests/js/windows-text-encoding.test.mjs` 明文记过这个坑）。让脚本自己写文件，
// 编码就不经过 shell。
//
// 用法（脚本开头一行）：
//     import { tee } from "./tee.mjs";
//     tee(process.argv[1], process.argv.slice(2));     // 缺省落 <脚本名>.txt，--out <path> 可覆盖
import { appendFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";

export function tee(scriptPath, args = []) {
  const out = args.includes("--out")
    ? args[args.indexOf("--out") + 1]
    : scriptPath.replace(/\.mjs$/, ".txt");
  const lines = [];
  const wrap = (orig, sink) => (...a) => {
    lines.push(a.map((x) => (typeof x === "string" ? x : String(x))).join(" "));
    orig.apply(console, a);
    void sink;
  };
  const origLog = console.log;
  const origErr = console.error;
  console.log = wrap(origLog, 1);
  console.error = wrap(origErr, 2);
  writeFileSync(out, "", "utf8");                    // 清空/建文件（UTF-8，无 BOM）
  const flush = () => {
    if (!lines.length) return;
    appendFileSync(out, lines.join("\n") + "\n", "utf8");
    lines.length = 0;
  };
  process.on("exit", () => {
    console.log = origLog; console.error = origErr;
    flush();
    origLog(`（证据已落 ${basename(out)}，UTF-8）`);
  });
  return out;
}
