// probe-07-guard-strength.mjs — 前端知情文案判据的**强度自检**（工单 hwcheck-unknown-device/07）。
//
// 「真源码上全绿」证明不了判据有牙齿：把**真源码里的知情文案**改回含糊口径，
// 前端门禁里的对应用例必须当场变红。注入跑 `node --test tests/js/my-devices.test.mjs`
// （子进程），期望 **FAIL**；跑完**逐字节复原**并断言复原成功
// （先例：`probe-05/06/12-guard-strength.mjs`）。
//
// 注入打的是本单的前端守卫：**页面明说资料会被送到 AI 通道**（票面硬要求——
// 文案被改含糊、或"AI 不写代码"那半句被删掉时，用例「资料入口明说…」必须红）。
//
// ⚠ 本件会真的改库内文件（`static/js/fx/my-devices.js`）：**别和测试套件同时跑**。
//
// 用法：node .scratch/hwcheck-unknown-device/probe-07-guard-strength.mjs
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const TARGET = `${REPO}src/contest_generator/static/js/fx/my-devices.js`;
const original = readFileSync(TARGET);                     // **原始字节**
const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };

const INJECTIONS = [
  {
    id: "知情文案改含糊（不再明说送 AI 通道 / 不再说 AI 不写代码）",
    what: "MY_DEVICE_MATERIAL_NOTICE 换成一句含糊话 —— 用户在不知情的情况下把"
      + "手册送出去，正是票面要防的那件事",
    expectRed: ["资料入口明说「资料会被送到 AI 通道」"],
    patch: (t) => t.replace(
      'export const MY_DEVICE_MATERIAL_NOTICE =\n'
      + '  "有手册 / 卖家页？把关键几行贴进来（或选一个文件），AI 抽成草稿你逐字段确认。"\n'
      + '  + "资料会被送到 AI 通道抽取——AI 只填草稿：不写代码、不生成判据；不想传就手填，一样能测。";',
      'export const MY_DEVICE_MATERIAL_NOTICE = "粘贴资料后点击抽取即可。";'),
  },
];

const run = () => {
  try {
    execFileSync("node", ["--test", "tests/js/my-devices.test.mjs"], { cwd: REPO, encoding: "utf8" });
    return { code: 0, out: "" };
  } catch (e) {
    return { code: e.status ?? 1, out: `${e.stdout || ""}${e.stderr || ""}` };
  }
};

// 前置干净性检查（先例：探针被强杀会留下注入态）
const before = run();
say("=== 前端判据强度自检（工单 hwcheck-unknown-device/07）===");
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
    // 判据是「**宣称的守卫**出现在红名单里」，不是"首条红恰好是它"：一条注入
    // 常常同时打红两三条守卫——按首条判定会把它误报成"名不副实"。
    const reds = r.out.split("\n").filter((l) => /✖/.test(l)).map((l) => l.trim());
    const firstFail = (reds[0] || "").slice(0, 110);
    const missed = inj.expectRed.filter((name) => !reds.some((line) => line.includes(name)));
    const ok = r.code !== 0 && missed.length === 0;
    if (missed.length > 0) {
      say(`        ✗ 宣称的守卫不在红名单里：${missed.join(" / ")}（首条红：${firstFail}）`);
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
say(bad === 0 ? "**强度自检：PASS**（注入都让前端门禁变红）" : `**强度自检：FAIL**（${bad} 条）`);

function write() {
  writeFileSync(
    fileURLToPath(new URL("./probe-07-guard-strength-front.txt", import.meta.url)),
    lines.join("\n") + "\n", "utf8");
}
write();
// 收尾再确认目标文件回到原始字节
if (!readFileSync(TARGET).equals(original)) { console.error("目标文件未复原！"); process.exit(2); }
process.exit(bad === 0 ? 0 : 1);
