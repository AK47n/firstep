// B18（frontend-es-modules-stage2/24）+ B19（/25）收口：两处「实况点按 / 实况滚动」验收。
//
//   B18 草稿清除按钮实况点按：共享 handler 抽取后行为逐字等价——点击 → clearDraft →
//       按钮文案「已清除」→ 1.5s 后回「清除草稿」；草稿键确实被清。
//   B19 main.c 编辑器滚动实况：`syncPanels(ta)` 单源——滚动 textarea 时
//       行号列（#main-c-nums）与高亮层（#main-c-hl）随动（scrollTop 相等）。
//
// 依赖：webapp 8000 + Chrome headless CDP 9251。零写库（只动浏览器内草稿键，用后还原）。
import { rebuildTab, connect } from "../cdp-harness.mjs";

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

for (let i = 0; i < 120; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.getElementById('main-c')`)) break;
  await sleep(250);
}
await Eval(`document.querySelector('nav button[data-tab="generate"]')?.click()`);
await sleep(400);

// ================= B18 草稿清除按钮 =================
// 先造一个草稿（与产品同键），确保「清除」有东西可清
const draftKey = await Eval(`(async () => { const m = await import('/js/fx/draft.js'); return m.DRAFT_KEY || 'firstep.draft.v1'; })()`);
await Eval(`localStorage.setItem(${JSON.stringify(draftKey)}, JSON.stringify({ problem: '冒烟草稿', platform: 'stm32' }))`);
const before = await Eval(`!!localStorage.getItem(${JSON.stringify(draftKey)})`);
check("B18 前置：浏览器里有草稿键", before, "key=" + draftKey);

const btnState0 = await Eval(`document.getElementById('btn-clear-draft').textContent.trim()`);
check("B18 按钮初始文案 =「清除草稿」", btnState0 === "清除草稿", JSON.stringify(btnState0));
await Eval(`document.getElementById('btn-clear-draft').click()`);
const afterClick = await Eval(`({ text: document.getElementById('btn-clear-draft').textContent.trim(),
  draft: !!localStorage.getItem(${JSON.stringify(draftKey)}) })`);
check("B18 点击 → 草稿已清 + 文案「已清除」", afterClick.draft === false && afterClick.text === "已清除", JSON.stringify(afterClick));
await sleep(1700);
const afterWait = await Eval(`document.getElementById('btn-clear-draft').textContent.trim()`);
check("B18 1.5s 后文案回「清除草稿」（两按钮共享 handler 的等价行为）", afterWait === "清除草稿", JSON.stringify(afterWait));
// 第二个入口（草稿卡上的同名按钮）也走同一 handler
const secondBtn = await Eval(`(() => { const b = document.getElementById('btn-draft-clear'); if (!b) return null; b.click(); return document.getElementById('btn-draft-clear').textContent.trim(); })()`);
check("B18 第二个入口（#btn-draft-clear）同样生效（同一 handler）", secondBtn === null || secondBtn === "已清除", JSON.stringify(secondBtn));

// ================= B19 main.c 滚动三同步 =================
const filled = await Eval(`(() => {
  const ta = document.getElementById('main-c');
  const lines = [];
  for (let i = 1; i <= 200; i++) lines.push('int v' + i + ' = ' + i + ';   /* 行 ' + i + ' */');
  ta.value = lines.join('\\n');
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return { lines: 200, numsLines: document.getElementById('main-c-nums').textContent.split('\\n').length };
})()`);
check("B19 输入后行号列行数随内容更新", filled.numsLines >= 200, JSON.stringify(filled));
const hlTok = await Eval(`document.getElementById('main-c-hl').querySelectorAll('[class*="tok-"]').length`);
check("B19 高亮层有 token span（cHighlight 生效）", hlTok > 0, "tok=" + hlTok);

const scrolled = await Eval(`(() => {
  const ta = document.getElementById('main-c'); const nums = document.getElementById('main-c-nums'); const hl = document.getElementById('main-c-hl');
  ta.scrollTop = 300; ta.scrollLeft = 0;
  ta.dispatchEvent(new Event('scroll'));
  return { ta: ta.scrollTop, nums: nums.scrollTop, hl: hl.scrollTop, hlLeft: hl.scrollLeft,
           taMax: ta.scrollHeight - ta.clientHeight };
})()`);
check("B19 滚动 textarea → 行号列随动（scrollTop 相等）", scrolled.ta > 0 && scrolled.nums === scrolled.ta, JSON.stringify(scrolled));
check("B19 滚动 textarea → 高亮层随动（scrollTop / scrollLeft 相等）",
  scrolled.hl === scrolled.ta && scrolled.hlLeft === 0, JSON.stringify(scrolled));
const scrolled2 = await Eval(`(() => {
  const ta = document.getElementById('main-c'); const nums = document.getElementById('main-c-nums'); const hl = document.getElementById('main-c-hl');
  const target = Math.round((ta.scrollHeight - ta.clientHeight) * 0.8);
  ta.scrollTop = target; ta.dispatchEvent(new Event('scroll'));
  return { target, ta: ta.scrollTop, nums: nums.scrollTop, hl: hl.scrollTop };
})()`);
check("B19 再滚到 80% 处仍三方同步", scrolled2.nums === scrolled2.ta && scrolled2.hl === scrolled2.ta, JSON.stringify(scrolled2));
// 还原：清掉冒烟内容与草稿键，避免影响其它脚本
await Eval(`(() => { const ta = document.getElementById('main-c'); ta.value = ''; ta.dispatchEvent(new Event('input', { bubbles: true })); localStorage.removeItem(${JSON.stringify(draftKey)}); })()`);
check("B19 收尾还原（内容与草稿键已清）", await Eval(`document.getElementById('main-c').value === ''`));

console.log("---- B18/B19 总览 ----");
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
c.close();
process.exit(failed ? 1 : 0);
