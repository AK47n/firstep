// probe-04-guard-strength.mjs — 闸门用例的**强度自检**（工单 module-import-usage/03）。
//
// 「真源码上全绿」证明不了判据有牙齿：把**真源码里的判据**改回旧口径，闸门必须当场变红。
// 三种注入各跑一次 `node --test tests/js/import-usage-guard.test.mjs`（子进程），期望 **FAIL**；
// 每次跑完**逐字节复原**并断言复原成功（先例：`.scratch/ui-dom-contract-gate/probe-guard-strength.mjs`）。
//
// ⚠ 本件会真的改库内文件（`tests/js/import-usage.mjs`）：**别和测试套件同时跑**。
//
// 用法：node .scratch/module-import-usage/probe-04-guard-strength.mjs
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const TARGET = `${REPO}tests/js/import-usage.mjs`;
const original = readFileSync(TARGET);                     // **原始字节**
const origText = original.toString("utf8");
const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };

const INJECTIONS = [
  {
    id: "旧口径-不掩注释字符串",
    what: "正文退回 `hostBody`（只剥 import 与整行 //）＋ 按源名判 —— 注释/字符串能把死 import 喂绿",
    patch: (t) => t
      .replace("const body = criterionBody(script, imports);", "const body = hostBody(script, imports);")
      .replace("const unused = names.filter((n, i) => !identRe(locals[i]).test(body));",
        "const unused = names.filter((n) => !identRe(n).test(body));"),
  },
  {
    id: "naive 掩码-模板表达式一起掩掉",
    what: "正文改用 `maskCommentsAndStrings` —— `${esc(x)}` 里的真使用被判成死的（假红）",
    patch: (t) => t
      .replace('import { parseModuleImports, maskNonCode } from "./boot-contract.mjs";',
        'import { parseModuleImports, maskNonCode, maskCommentsAndStrings } from "./boot-contract.mjs";')
      .replace("let out = maskNonCode(script);", "let out = maskCommentsAndStrings(script);"),
  },
  {
    id: "取数面缩回只有装载根",
    what: "把判据面 `ALL` 退回只有装载根 —— **下限绊线当场红**（真源码仍 0 处，不设下限这条注入会静默溜过）",
    // 说清楚这条注入实际证明什么：它把"全模块"悄悄换成"只有 boot.js"。这时**零未使用那条仍绿**
    //（boot.js 确实是 0），唯一拦住它的是取数面体检的**下限**（语句数从 496 掉到 ~60 < 400）。
    // 评审（03）指出第一版把它写成"模块级死 import 无人报"是名不副实——如实改成本注释与下面的期望。
    // 首条红因此是「判据取数面体检」，不是「零未使用具名」。
    target: `${REPO}tests/js/import-usage-guard.test.mjs`,
    expectFirstRed: "判据取数面体检",
    patch: (t) => t.replace("const ALL = [{ key: \"boot.js\", text: ROOT }, ...MODULES];",
      "const ALL = [{ key: \"boot.js\", text: ROOT }];"),
  },
];

const run = () => {
  try {
    execFileSync("node", ["--test", "tests/js/import-usage-guard.test.mjs"], { cwd: REPO, encoding: "utf8" });
    return { code: 0, out: "" };
  } catch (e) {
    return { code: e.status ?? 1, out: `${e.stdout || ""}${e.stderr || ""}` };
  }
};

// 前置干净性检查（先例：探针被强杀会留下注入态）
const before = run();
say("=== 闸门用例强度自检（工单 module-import-usage/03）===");
say(`① 前置干净性：注入前跑一次闸门 → ${before.code === 0 ? "绿（符合预期）" : "**红**：先修工作树再跑本件"}`);
if (before.code !== 0) { say("**ABORT**：工作树本来就不干净"); write(); process.exit(1); }
say("");

let bad = 0;
for (const inj of INJECTIONS) {
  const target = inj.target || TARGET;
  const orig = readFileSync(target);
  const patched = inj.patch(orig.toString("utf8"));
  if (patched === orig.toString("utf8")) {
    say(`  ✗ ${inj.id}：**注入没落上**（锚点串变了）—— 这条自检会静默空转`);
    bad++;
    continue;
  }
  try {
    writeFileSync(target, patched, "utf8");
    const r = run();
    const firstFail = (r.out.split("\n").find((l) => /✖|not ok/.test(l)) || "").trim().slice(0, 110);
    let ok = r.code !== 0;
    // 名不副实的注入比不做还坏（03 评审实测）：声明了"首条红是哪条用例"就必须真的对上
    if (ok && inj.expectFirstRed && !firstFail.includes(inj.expectFirstRed)) {
      ok = false;
      say(`        ✗ 首条红不是宣称的「${inj.expectFirstRed}」：${firstFail}`);
    }
    if (!ok) bad++;
    say(`  ${ok ? "PASS" : "FAIL"}  ${inj.id}`);
    say(`        ${inj.what}`);
    say(`        闸门退出码 ${r.code}${firstFail ? `，首条红：${firstFail}` : ""}`);
  } finally {
    writeFileSync(target, orig);                            // **逐字节复原**
    const restored = readFileSync(target);
    if (!restored.equals(orig)) { say(`        ✗ 复原失败（${target}）`); bad++; }
  }
}
say("");
say("复原复核：所有被注入文件与注入前**逐字节相同**");
say(bad === 0 ? "**强度自检：PASS**（三条注入都让闸门变红）" : `**强度自检：FAIL**（${bad} 条）`);

function write() {
  writeFileSync(fileURLToPath(new URL("./guard-strength.txt", import.meta.url)), lines.join("\n") + "\n", "utf8");
}
write();
// 收尾再确认目标文件回到原始字节
if (!readFileSync(TARGET).equals(original)) { console.error("目标文件未复原！"); process.exit(2); }
process.exit(bad === 0 ? 0 : 1);
