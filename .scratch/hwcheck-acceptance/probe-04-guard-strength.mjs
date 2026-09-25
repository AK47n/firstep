// probe-04-guard-strength.mjs — 工单 hwcheck-acceptance/04 的**判据强度反证**。
//
// 「真源码上全绿」证明不了判据有牙齿：把**真源码里的判据**改回旧口径，前端门禁里的
// 对应用例必须当场变红。6 条注入各跑一次 `node --test tests/js/hwcheck.test.mjs`
// （子进程），期望 **FAIL 且宣称的那条守卫出现在红名单里**；每次跑完**逐字节复原**
// 并复核（先例：`.scratch/hwcheck-unknown-device/probe-05-guard-strength.mjs`）。
//
// 注入面（每条都扎在**判据单源**上，不扎转调层）：
//   A 库内词表校验被拿掉（什么 slug 都往生成载荷里塞）→ fx 带入计划用例
//   B 库外自建件也照样带过去（不走生成链的东西进了载荷）→ fx 带入计划用例
//   C 引脚那一句被删（页面上不再说「引脚不带」）→ 引脚那一句用例
//   D ui 侧不再走 fx（自己手拼带入块）→ ui 侧结构钉
//   E 并入时把生成页已选的丢掉 → fx 并入判据用例
//   F 拒收理由退回「它就是被删了」（清单读失败时是假话）→ fx 拒收用例
//   G 检测页头副标题退回陈旧文案（「本版先做最小自检」）→ 副标题结构钉
//
// ⚠ "只展开一次"这条判据**不在本件射程**：它是真浏览器用例数请求条数验的
// （`tests/browser/hwcheck.spec.mjs`），数源码里 runExpand() 出现几次是实现细节
// 断言（双轴评审整改时从 tests/js 里删掉了）。
//
// ⚠ 本件会真的改 `src/` 下的文件：**别和测试套件同时跑**（含浏览器门禁）。
// 读写一律用 bytes——文本模式会把 CRLF 归一成 LF，复原复核会假红。
//
// 用法：node .scratch/hwcheck-acceptance/probe-04-guard-strength.mjs
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const FX = "src/contest_generator/static/js/fx/hwcheck.js";
const UI = "src/contest_generator/static/js/ui/hwcheck.js";
const REC = "src/contest_generator/static/js/ui/generate-recommend.js";
const HTML = "src/contest_generator/static/index.html";
const FILES = [FX, UI, REC, HTML];

const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };

const INJECTIONS = [
  {
    file: FX,
    id: "A · 库内词表校验被拿掉",
    what: "`hwcheckHandoffPlan` 不再查词表 —— 词表外的 slug（已删除的模块）也会被塞进生成载荷",
    from: "    if (known.has(slug)) carry.push(slug);\n"
      + "    else if (mine.has(slug)) custom.push({ id: slug, name: mine.get(slug) });\n"
      + "    else unknown.push(slug);",
    to: "    carry.push(slug);",
    expectRed: "带入计划：库内件进 carry",
  },
  {
    file: FX,
    id: "B · 库外自建件也照样带过去",
    what: "分类里去掉「自建件」这一支 —— 不走生成链的 id 直接进生成载荷（生成时必 400）",
    from: "    else if (mine.has(slug)) custom.push({ id: slug, name: mine.get(slug) });\n"
      + "    else unknown.push(slug);",
    to: "    else carry.push(slug);",
    expectRed: "带入计划：库内件进 carry",
  },
  {
    file: FX,
    id: "C · 页面上不再说「引脚不带」",
    what: "带入块里那一句引脚说明被删（`hwcheckHandoffPinNote()` 不再进块）——"
      + "学生以为生成页会用检测页这组脚",
    from: '  rows.push(\'<div class="hwcheck-hint">\' + hwcheckHandoffPinNote()',
    to: '  rows.push(\'<div class="hwcheck-hint">\'',
    expectRed: "引脚",
  },
  {
    file: UI,
    id: "D · ui 侧不再走 fx",
    what: "带入块不再由 fx 渲染（本层自己拼）—— 理由文案变成第二份实现",
    from: "  box.innerHTML = hwcheckHandoffHTML(hwcheckHandoff(), {",
    to: "  box.innerHTML = \"\";\n  void hwcheckHandoff();\n  const _opts = ({",
    expectRed: "ui 侧走 fx",
  },
  {
    file: FX,
    id: "E · 并入时把生成页已选的丢掉",
    what: "`hwcheckHandoffMerge` 每次并入都从空集重算 —— 带一件过去就把用户已选的模块洗掉",
    from: "  const out = (Array.isArray(selected) ? selected : [])\n"
      + "    .map((slug) => String(slug == null ? \"\" : slug)).filter(Boolean);",
    to: "  const out = [];",
    expectRed: "并入判据",
  },
  {
    file: FX,
    id: "F · 拒收理由退回「它就是被删了」",
    what: "词表外的件只说一个成因（清单读失败时这句话是假的）—— 评审整改的回归",
    from: '      + "</span> 没有带过去：它现在既不在模块库清单里、也不在「我的器件」里"\n'
      + "      + \"（可能是这两份清单有一份没读出来——刷新一次再看；也可能这件确实已经删了）。\"\n"
      + '      + "生成链只认库内模块，硬塞进去只会在生成时被拒。</div>");',
    to: '      + "</span> 不在库内词表里，没有带过去（可能已经从模块库删掉了）。</div>");',
    expectRed: "一律拒收",
  },
  {
    file: HTML,
    id: "G · 副标题退回陈旧文案",
    what: "检测页头那句「本版先做「板子活着」最小自检」回来 —— 学生以为这一栏测不了器件",
    from: "（手上这件器件通不通——不用赛题、不用先选模块；选平台 + 选器件"
      + " → 接线表与默认脚冲突预警 → 生成检测工程逐件判通断 → 串口复测 → 现象回填让 AI 排障）",
    to: "（手上这件器件通不通——不用赛题、不用先选模块；本版先做「板子活着」最小自检）",
    expectRed: "副标题",
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

const originals = new Map(FILES.map((f) => [f, readFileSync(REPO + f)]));
const outAt = fileURLToPath(new URL("./probe-04-guard-strength.txt", import.meta.url));
function write() { writeFileSync(outAt, lines.join("\n") + "\n", "utf8"); }

say("=== 前端判据强度自检（工单 hwcheck-acceptance/04）===");
const before = run();
say(`① 前置干净性：注入前跑一次门禁 → ${before.code === 0 ? "绿（符合预期）" : "**红**：先修工作树再跑本件"}`);
if (before.code !== 0) {
  say("**ABORT**：工作树本来就不干净");
  write();
  process.exit(1);
}
say("");

let bad = 0;
try {
  for (const inj of INJECTIONS) {
    const orig = originals.get(inj.file);
    const text = orig.toString("utf8");
    const patched = text.replace(inj.from, inj.to);
    if (patched === text) {
      say(`  ✗ ${inj.id}：**注入没落上**（锚点串变了）—— 这条自检会静默空转`);
      bad++;
      continue;
    }
    try {
      writeFileSync(REPO + inj.file, patched, "utf8");
      const r = run();
      const reds = r.out.split("\n").filter((l) => /✖/.test(l)).map((l) => l.trim());
      const firstFail = (reds[0] || "").slice(0, 110);
      const hit = reds.some((line) => line.includes(inj.expectRed));
      const ok = r.code !== 0 && hit;
      if (!ok) bad++;
      say(`  ${ok ? "PASS" : "FAIL"}  ${inj.id}（${inj.file}）`);
      say(`        ${inj.what}`);
      say(`        门禁退出码 ${r.code}，红 ${reds.length} 条，首条红：${firstFail}`);
      if (r.code !== 0 && !hit) say(`        ✗ 宣称的守卫「${inj.expectRed}」不在红名单里`);
    } finally {
      writeFileSync(REPO + inj.file, orig);   // **逐字节复原**
    }
  }
} finally {
  // 收尾复核：四个文件都必须回到注入前的字节（被强杀时也尽量放回去）
  for (const f of FILES) {
    if (!readFileSync(REPO + f).equals(originals.get(f))) {
      writeFileSync(REPO + f, originals.get(f));
      say(`  ⚠ ${f} 曾被改动，已按原字节写回`);
    }
  }
}
say("");
for (const f of FILES) {
  const same = readFileSync(REPO + f).equals(originals.get(f));
  if (!same) bad++;
  say(`${same ? "✓" : "✗"} 逐字节复原 ${f}`);
}
say("");
say(bad === 0
  ? `**强度自检：PASS**（${INJECTIONS.length} 条注入都让前端门禁按预期变红，源码逐字节复原）`
  : `**强度自检：FAIL**（${bad} 条）`);
write();
process.exit(bad === 0 ? 0 : 1);
