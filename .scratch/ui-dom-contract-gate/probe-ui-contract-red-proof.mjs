// 红证（工单 ui-dom-contract-gate/04）：五条 UI 行为契约**真的会红**吗。
//
// 口径：在**真源码**上做一处最小注入（摘掉模块的绑定），跑一遍 contracts，
// 断言"该红的那条红"，然后**逐字节复原**并复核（sha256 前后相等 + 工作树 git 干净度不变）。
//
// 为什么用真源码而不是内存副本：这一层测的就是"真页面 + 真事件"，
// 注入必须走真 HTTP 路径（webapp 的 STATIC_DIR 是模块级常量，没法从外面重定向——
// 那是产品设计，不为测试改）。所以探针自带**前置干净性检查 + 事后逐字节复原复核**，
// 照 .scratch/module-hwcheck/probe-09-guard-strength.py 的先例。
//
// 用法：node .scratch/ui-dom-contract-gate/probe-ui-contract-red-proof.mjs
// ⚠ 跑的时候别同时跑别的测试套件（它真的改库内文件）。
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = REPO + "src/contest_generator/static/";
const SPEC = "tests/browser/ui-contract.spec.mjs";
const sha = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");

// 每个场景：{ 名字, 目标文件, 注入, 期望红的用例名片段 }
//
// 注入只取"**绑定**"这一类（摘掉监听器）——那是 ui 层唯一无法用纯函数用例覆盖的东西，
// 也正是这一层存在的理由。**不**注入"改存储键"那类：用例与产品读同一个常量，
// 两侧一起漂时契约照样绿（红证实测确认），键值的冻结归 tests/js 侧的纯函数用例
// ——这条已写进 spec 文件头的注释，别再拿它当红证。
const SCENARIOS = [
  {
    name: "guide：摘掉子页签点击委托",
    file: STATIC + "js/ui/guide.js",
    from: '  nav.addEventListener("click", (e) => {',
    to: '  if (false) nav.addEventListener("click", (e) => {',
    expect: "新手指引子页签",
  },
  {
    name: "step-state：摘掉卡头折叠监听",
    file: STATIC + "js/ui/step-state.js",
    from: '    h2.addEventListener("click", (e) => {',
    to: '    if (false) h2.addEventListener("click", (e) => {',
    expect: "生成页卡片折叠",
  },
  {
    name: "welcome：摘掉「不再显示」的接线",
    file: STATIC + "js/ui/welcome.js",
    from: '  $("btn-welcome-dismiss")?.addEventListener("click", () => {',
    to: '  if (false) $("btn-welcome-dismiss")?.addEventListener("click", () => {',
    expect: "欢迎卡「不再显示」",
  },
];

function killStrayServers() {
  try {
    execFileSync("powershell", ["-NoProfile", "-Command",
      "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | "
      + "Where-Object { $_.CommandLine -like '*contest_generator.webapp*' } | "
      + "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], { stdio: "ignore" });
  } catch (e) { /* 没有残留也正常 */ }
}

function runContracts() {
  killStrayServers();
  let out = "";
  try {
    out = execFileSync("node",
      ["--test", "--test-concurrency=1", SPEC],
      { cwd: REPO, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } catch (e) {
    out = String(e.stdout || "") + String(e.stderr || "");
  }
  const failed = [...out.matchAll(/^✖ (.+?) \(/gm)]
    .map((m) => m[1])
    // 文件级失败行（`✖ tests\browser\ui-contract.spec.mjs`）不是用例，滤掉——
    // 它是"整个文件挂了（语法/加载错误）"的汇总行，留在判据里会把反证判红。
    .filter((name) => !name.endsWith(".mjs"));
  return { failed: [...new Set(failed)], out };
}

// ---- 前置干净性检查：目标文件当前必须与 git HEAD 一致（否则复原复核无意义）----
const dirty = execFileSync("git", ["-C", REPO, "status", "--porcelain", "--",
  "src/contest_generator/static/"], { encoding: "utf8" }).trim();
if (dirty) {
  console.error("前置检查失败：静态目录本来就有未提交改动，先收干净再跑本探针：\n" + dirty);
  process.exit(2);
}

const results = [];
// 反证：不注入时必须全绿
{
  const { failed } = runContracts();
  results.push({ name: "反证：无注入 → 5 条契约全绿", ok: failed.length === 0,
    note: failed.join(" / ") || "0 条红" });
}

for (const s of SCENARIOS) {
  const before = sha(s.file);
  const original = readFileSync(s.file, "utf8");
  if (!original.includes(s.from)) {
    results.push({ name: s.name, ok: false, note: `注入锚点找不到（源码变了？）：${s.from}` });
    continue;
  }
  writeFileSync(s.file, original.replace(s.from, s.to));
  try {
    const { failed } = runContracts();
    const hit = failed.find((f) => f.includes(s.expect));
    const others = failed.filter((f) => !f.includes(s.expect));
    results.push({
      name: s.name,
      ok: !!hit && others.length === 0,   // 该红的红，且**只红那一条**
      note: hit ? `红了「${hit}」${others.length ? `；但也有无关的红：${others.join(" / ")}` : ""}`
        : `没红（实际红的是：${failed.join(" / ") || "无"}）`,
    });
  } finally {
    writeFileSync(s.file, original);
    const after = sha(s.file);
    if (after !== before) {
      results.push({ name: s.name + "（复原复核）", ok: false, note: "复原后 sha256 不等！" });
    }
  }
}

console.log("");
for (const r of results) console.log(`${r.ok ? "✔" : "✖"} ${r.name}  —— ${r.note}`);
const failedCount = results.filter((r) => !r.ok).length;
console.log(`\n${failedCount ? "FAIL" : "PASS"}：${results.length - failedCount}/${results.length} 条成立`);
const stillDirty = execFileSync("git", ["-C", REPO, "status", "--porcelain", "--",
  "src/contest_generator/static/"], { encoding: "utf8" }).trim();
console.log(stillDirty ? "⚠ 工作树仍不干净：\n" + stillDirty : "复原复核：静态目录与跑之前逐字节一致（git 干净）");
process.exitCode = failedCount || stillDirty ? 1 : 0;
