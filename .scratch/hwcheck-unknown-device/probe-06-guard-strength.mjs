// probe-06-guard-strength.mjs — 前端两条判据的**强度自检**（工单 hwcheck-unknown-device/06）。
//
// 「真源码上全绿」证明不了判据有牙齿：把**真源码里的判据**改回旧口径，前端门禁里的
// 对应用例必须当场变红。两条注入各跑一次 `node --test tests/js/hwcheck.test.mjs`
// （子进程），期望 **FAIL**；每次跑完**逐字节复原**并断言复原成功
// （先例：`.scratch/module-import-usage/probe-04-guard-strength.mjs`、
// `probe-05-guard-strength.mjs`）。
//
// 两条注入打的是本单新加的两条前端守卫：
//
//   * **命令表按 tag 分画法** —— 自建件那几行不再读载荷的 `tag`（当库内件画：
//     只剩 slug，没有标注词与名称）→ 用例「命令表：自建件那行带标注词与名称」必须红；
//   * **用户填的名称要 esc** —— 名称那一格不再过 `esc()`（用户随手填的文本直接
//     进 HTML）→ 用例「命令表：自建件的名称是用户随手填的，一律 esc」必须红。
//
// ⚠ 本件会真的改库内文件（`static/js/fx/hwcheck.js`）：**别和测试套件同时跑**。
//
// 用法：node .scratch/hwcheck-unknown-device/probe-06-guard-strength.mjs
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const TARGET = `${REPO}src/contest_generator/static/js/fx/hwcheck.js`;
const original = readFileSync(TARGET);                     // **原始字节**
const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };

const INJECTIONS = [
  {
    id: "命令表忽略 tag：自建件当库内件画",
    what: "命令表不再读载荷的 `tag` —— 自建件那几行只剩 slug，标注词与人读名一起消失"
      + "（页面与板上就不再是同一件事的两个说法）",
    patch: (t) => t.replace("  const label = tag", "  const label = false"),
    expectRed: "命令表：自建件那行带标注词与名称",
  },
  {
    id: "名称不转义：用户填的名字直接进 HTML",
    what: "自建件那一格的名称不再过 `esc()`（用户填的文本原样拼进 innerHTML）",
    patch: (t) => t.replace(
      '+ (name ? ` <span class="hwcheck-custom-name">${esc(name)}</span>` : "")',
      '+ (name ? ` <span class="hwcheck-custom-name">${name}</span>` : "")'),
    expectRed: "命令表：自建件的名称是用户随手填的，一律 esc",
  },
];

const run = () => {
  try {
    execFileSync("node", ["--test", "tests/js/hwcheck.test.mjs"], { cwd: REPO, encoding: "utf8" });
    return { code: 0, out: "" };
  } catch (e) {
    return { code: e.status ?? 1, out: `${e.stdout || ""}${e.stderr || ""}` };
  }
};

// 前置干净性检查（先例：探针被强杀会留下注入态）
const before = run();
say("=== 前端判据强度自检（工单 hwcheck-unknown-device/06）===");
say(`① 前置干净性：注入前跑一次门禁 → ${before.code === 0 ? "绿（符合预期）" : "**红**：先修工作树再跑本件"}`);
if (before.code !== 0) { say("**ABORT**：工作树本来就不干净"); write(); process.exit(1); }
say("");

let bad = 0;
for (const inj of INJECTIONS) {
  const orig = readFileSync(TARGET);
  const patched = inj.patch(orig.toString("utf8"));
  if (patched === orig.toString("utf8")) {
    say(`  ✗ ${inj.id}：**注入没落上**（锚点串变了）—— 这条自检会静默空转`);
    bad++;
    continue;
  }
  try {
    writeFileSync(TARGET, patched, "utf8");
    const r = run();
    // 判据是「**宣称的那条守卫**出现在红名单里」，不是"首条红恰好是它"：一条注入
    // 常常同时打红两三条守卫——按首条判定会把它误报成"名不副实"。
    const reds = r.out.split("\n").filter((l) => /✖/.test(l)).map((l) => l.trim());
    const firstFail = (reds[0] || "").slice(0, 110);
    const hit = reds.some((line) => line.includes(inj.expectRed));
    const ok = r.code !== 0 && hit;
    if (r.code !== 0 && !hit) {
      say(`        ✗ 宣称的守卫「${inj.expectRed}」不在红名单里：${firstFail}`);
    }
    if (!ok) bad++;
    say(`  ${ok ? "PASS" : "FAIL"}  ${inj.id}`);
    say(`        ${inj.what}`);
    say(`        门禁退出码 ${r.code}，红 ${reds.length} 条，首条红：${firstFail}`);
  } finally {
    writeFileSync(TARGET, orig);                            // **逐字节复原**
    if (!readFileSync(TARGET).equals(orig)) { say(`        ✗ 复原失败（${TARGET}）`); bad++; }
  }
}
say("");
say("复原复核：被注入文件与注入前**逐字节相同**");
say(bad === 0 ? "**强度自检：PASS**（两条注入都让前端门禁变红）" : `**强度自检：FAIL**（${bad} 条）`);

function write() {
  writeFileSync(
    fileURLToPath(new URL("./probe-06-guard-strength-front.txt", import.meta.url)),
    lines.join("\n") + "\n", "utf8");
}
write();
// 收尾再确认目标文件回到原始字节
if (!readFileSync(TARGET).equals(original)) { console.error("目标文件未复原！"); process.exit(2); }
process.exit(bad === 0 ? 0 : 1);
