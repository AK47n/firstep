// B13（gen-result-panel/01 收口）：生成结果面板**宽 / 窄屏**布局断言 + 截图。
//
// 源工单验收：「headless 截图目检（宽/窄屏）」——`#generate-result` 用 `.res-grid`
// （宽屏 `1fr 380px` 两列：`.res-main` 左 / `.res-side` 右；`@media (max-width:1179px)`
// 落单列）。本脚本把「两列 / 单列」做成几何断言（比目视更硬），两态各截一张图。
//
// 依赖：webapp 8000 + Chrome headless CDP 9251。零写库：只解除 `#generate-result`
// 的 hidden（生成结果区平时隐藏），不改任何数据。
import { writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const PORT = 9251;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const t = await rebuildTab({ port: PORT });
if (!t) { console.error("重建标签页失败"); process.exit(1); }
const c = await connect({ port: PORT, timeoutMs: 20000 });
const Eval = (e) => c.Eval(e);

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const shot = async (name) => {
  const s = await c.cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(ROOT, ".scratch", "gen-result-panel", name), Buffer.from(s.result.data, "base64"));
  console.log("截图已存档 " + name);
};

for (let i = 0; i < 120; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.getElementById('generate-result')`)) break;
  await sleep(250);
}

// 生成结果区平时 hidden（未生成）；布局断言需要它可见 → 只解除 hidden，零数据改动
await Eval(`document.getElementById('generate-result').classList.remove('hidden')`);
// 截图前必须滚到该区：否则截到的是页面顶部（第十四轮实测：视觉通道反馈「图里没有生成结果区」）
const focusResult = () => Eval(`document.getElementById('generate-result').scrollIntoView({ block: 'start' })`);

const geom = () => Eval(`(() => {
  const g = document.querySelector('#generate-result .res-grid');
  const m = g.querySelector('.res-main').getBoundingClientRect();
  const s = g.querySelector('.res-side').getBoundingClientRect();
  return {
    cols: getComputedStyle(g).gridTemplateColumns,
    main: { top: Math.round(m.top), bottom: Math.round(m.bottom), left: Math.round(m.left), right: Math.round(m.right), w: Math.round(m.width) },
    side: { top: Math.round(s.top), bottom: Math.round(s.bottom), left: Math.round(s.left), right: Math.round(s.right), w: Math.round(s.width) },
    vw: window.innerWidth,
  };
})()`);

// ---- 宽屏 1418（> 1179 → 两列）----
await c.cdp("Emulation.setDeviceMetricsOverride", { width: 1418, height: 802, deviceScaleFactor: 1, mobile: false });
await sleep(500);
const wide = await geom();
check("B13 宽屏：.res-grid 两列（1fr 380px）", wide.vw === 1418 && wide.cols.split(" ").length === 2, JSON.stringify(wide.cols));
check("B13 宽屏：.res-side 在 .res-main 右侧且同排（top 齐）",
  wide.side.left >= wide.main.right - 2 && Math.abs(wide.side.top - wide.main.top) <= 2,
  JSON.stringify({ main: wide.main, side: wide.side }));
check("B13 宽屏：右列宽 ≈ 380px", Math.abs(wide.side.w - 380) <= 2, "side.w=" + wide.side.w);
await focusResult();
await sleep(300);
await shot("shot-01-wide.png");

// ---- 窄屏 900（< 1179 → 单列）----
await c.cdp("Emulation.setDeviceMetricsOverride", { width: 900, height: 802, deviceScaleFactor: 1, mobile: false });
await sleep(500);
await focusResult();
await sleep(300);
const narrow = await geom();
check("B13 窄屏：.res-grid 单列", narrow.vw === 900 && narrow.cols.split(" ").length === 1, JSON.stringify(narrow.cols));
check("B13 窄屏：.res-side 落到 .res-main 下方（左端对齐）",
  narrow.side.top >= narrow.main.bottom - 2 && Math.abs(narrow.side.left - narrow.main.left) <= 2,
  JSON.stringify({ main: narrow.main, side: narrow.side }));
await shot("shot-01-narrow.png");

// ---- 既有 id 全部保留（工单验收项：JS 填充/显隐零改动的前提）----
const ids = ["res-dir", "btn-copy-dir", "res-artifacts", "res-includes", "res-modules", "res-score-points", "res-build-hint", "res-structure", "compile-banner"];
const present = await Eval(`(${JSON.stringify(ids)}).filter((id) => !!document.getElementById(id))`);
check("B13 既有 id 全部在位（9 个）", present.length === ids.length,
  `${present.length}/${ids.length}：缺 ${JSON.stringify(ids.filter((i) => !present.includes(i)))}`);
const labels = await Eval(`document.querySelectorAll('#generate-result .res-label').length`);
check("B13 每块有 .res-label 小标题（≥5）", labels >= 5, "labels=" + labels);
const structureInSide = await Eval(`(() => {
  const side = document.querySelector('#generate-result .res-side');
  const el = document.getElementById('res-structure');
  return !!side && !!el && side.contains(el);
})()`);
check("B13 结构树在右列（.res-side）且保持 pre.result 样式", structureInSide
  && await Eval(`document.getElementById('res-structure').classList.contains('result') || !!document.querySelector('#res-structure pre.result')`));

await c.cdp("Emulation.clearDeviceMetricsOverride").catch(() => {});
console.log("---- B13 总览 ----");
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
c.close();
process.exit(failed ? 1 : 0);
