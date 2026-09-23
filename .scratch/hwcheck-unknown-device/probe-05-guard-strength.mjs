// probe-05-guard-strength.mjs — 前端两条判据的**强度自检**（工单 hwcheck-unknown-device/05）。
//
// 「真源码上全绿」证明不了判据有牙齿：把**真源码里的判据**改回旧口径，前端门禁里的
// 对应用例必须当场变红。两条注入各跑一次 `node --test tests/js/hwcheck.test.mjs`
// （子进程），期望 **FAIL**；每次跑完**逐字节复原**并断言复原成功
// （先例：`.scratch/module-import-usage/probe-04-guard-strength.mjs`）。
//
// 两条注入打的是本单新加的两条前端守卫：
//
//   * **标注词不互串** —— 计划面板的标注词改成写死的 `[专精]`（自建件冒充"库内验证过
//     的结论"）→ 用例「与库内专精件外观可区分」必须红；
//   * **接线区不许编一行** —— 接线区不再过滤 `wiring_text`（没有线可接的件也画一行）
//     → 用例「一件自建件都没有 = 空串」必须红。
//
// ⚠ 本件会真的改库内文件（`static/js/fx/hwcheck.js`）：**别和测试套件同时跑**。
//
// 用法：node .scratch/hwcheck-unknown-device/probe-05-guard-strength.mjs
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
    id: "标注词互串：计划面板写死 [专精]",
    what: "计划面板不再读载荷的 tag_text，改写死 `[专精]` —— 自建件冒充库内验证过的结论"
      + "（两条守卫同时开火：'标注词来自载荷' 与 '不许出现 [专精]'）",
    patch: (t) => t.replace(
      '  const tag = one.tag_text\n'
      + '      ? `<span class="hwcheck-section-tag custom">${esc(one.tag_text)}</span>`\n'
      + '      : "";',
      '  const tag = `<span class="hwcheck-section-tag custom">[专精]</span>`;'),
    expectRed: "计划面板：与库内专精件**外观可区分**",
  },
  {
    id: "接线区不过滤：没有线可接的件也画一行",
    what: "`hwcheckCustomWiringHTML` 不再过滤 `wiring_text` —— 非 I2C 件也被画出一行接线说明",
    patch: (t) => t.replace(
      '  const list = (Array.isArray(items) ? items : []).filter(\n'
      + '    (item) => item && item.wiring_text);',
      '  const list = (Array.isArray(items) ? items : []);'),
    expectRed: "计划面板：**一件自建件都没有 = 空串**",
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
say("=== 前端判据强度自检（工单 hwcheck-unknown-device/05）===");
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
    // 常常同时打红两三条守卫（本轮实测：写死 `[专精]` 会先撞上"标注词来自载荷"，
    // 再撞上"不许出现 [专精]"）——按首条判定会把它误报成"名不副实"。
    const reds = r.out.split("\n").filter((l) => /✖/.test(l)).map((l) => l.trim());
    const firstFail = (reds[0] || "").slice(0, 110);
    const hit = reds.some((line) => line.includes(inj.expectRed));
    let ok = r.code !== 0 && hit;
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
    fileURLToPath(new URL("./probe-05-guard-strength-front.txt", import.meta.url)),
    lines.join("\n") + "\n", "utf8");
}
write();
// 收尾再确认目标文件回到原始字节
if (!readFileSync(TARGET).equals(original)) { console.error("目标文件未复原！"); process.exit(2); }
process.exit(bad === 0 ? 0 : 1);
