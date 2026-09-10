// B14（ui-detail/01、/02、/03 收口）：三处视觉细节的机器判据 + 截图。
//
//   01 步进导航状态：`.step-nav .step-dot` 的 `.warn` 新态（黄 dot + warn-dim 底色）
//      与 `.done` 容器底色——用「挂类后计算样式确实变化」验证，而不是只看 CSS 文本；
//   02 动效令牌：`:root` 的 `--dur-fast/--dur-base/--dur-slow/--ease-ui` 存在，
//      且页面元素的计算 transition 真的取到这些值；
//   03 卡分组：`.card-group` 规则存在，且生成页卡 10/11 的 DOM 里真有分组容器。
//
// 依赖：webapp 8000 + Chrome headless CDP 9251。零写库。
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
const shot = async (dir, name) => {
  const s = await c.cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(ROOT, ".scratch", dir, name), Buffer.from(s.result.data, "base64"));
  console.log("截图已存档 " + name);
};

for (let i = 0; i < 120; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.getElementById('gen-overview')`)) break;
  await sleep(250);
}
await Eval(`(() => { const b = [...document.querySelectorAll('nav button')].find((x) => x.dataset.tab === 'generate'); if (b) b.click(); })()`);
await sleep(400);

// ================= 01 步进导航状态 =================
// CSSOM 递归扫描（.step-dot 规则在 @media (min-width:1180px) 里，顶层扫不到）
const scanRules = (sel) => Eval(`(() => {
  const rules = [];
  const walk = (list) => {
    for (const r of list) {
      if (r.selectorText && r.selectorText.includes(${JSON.stringify(sel)})) rules.push(r.selectorText);
      if (r.cssRules) walk(r.cssRules);
    }
  };
  for (const sheet of document.styleSheets) {
    try { walk(sheet.cssRules); } catch (e) { /* 跨源忽略 */ }
  }
  return rules;
})()`);
const dotCss = await scanRules("step-dot");
check("B14-01 CSS 里有 .step-dot.warn / .step-dot.done 规则",
  dotCss.some((s) => s.includes(".warn")) && dotCss.some((s) => s.includes(".done")),
  JSON.stringify(dotCss.filter((s) => s.includes(".warn") || s.includes(".done"))));
// 读计算样式时必须**等 transition 落定**：`.step-dot` 等元素有
// `transition: background-color var(--dur-fast)`，加类后立刻读会拿到动画起始值
// （第十四轮实测：不等就永远读到旧色，误判成「规则没生效」）。
const setCls = (add, remove) => Eval(`(() => {
  const d = document.querySelector('.step-nav .step-dot');
  ${add.map((c) => `d.classList.add(${JSON.stringify(c)})`).join(";")};
  ${remove.map((c) => `d.classList.remove(${JSON.stringify(c)})`).join(";")};
  return d.className;
})()`);
const readDot = () => Eval(`(() => {
  const d = document.querySelector('.step-nav .step-dot');
  const i = d.querySelector('.dot') || d;
  return { dot: getComputedStyle(d).backgroundColor + '|' + getComputedStyle(d).borderColor + '|' + getComputedStyle(d).color,
           inner: getComputedStyle(i).backgroundColor + '|' + getComputedStyle(i).color,
           cls: d.className, vw: window.innerWidth, mq1180: matchMedia('(min-width: 1180px)').matches };
})()`);
const base = await readDot();
await setCls(["warn"], []);
await sleep(400);
const warn = await readDot();
await setCls([], ["warn"]);
await setCls(["done"], []);
await sleep(400);
const done = await readDot();
await setCls([], ["done"]);
const warnDim = await Eval(`getComputedStyle(document.documentElement).getPropertyValue('--warn-dim').trim()`);
console.log("  诊断：", JSON.stringify({ cls: base.cls, vw: base.vw, mq1180: base.mq1180, warnDim }));
check("B14-01 .warn 挂上后计算样式确实变化（dot 底色 = warn-dim）",
  warn.dot !== base.dot && warn.dot.includes("227, 163, 65"), JSON.stringify({ base: base.dot, warn: warn.dot }));
check("B14-01 .done 挂上后计算样式确实变化（容器底色 = ok-dim）",
  done.dot !== base.dot && done.dot.includes("63, 185, 80"),
  JSON.stringify({ base: base.dot, done: done.dot }));
// 三处状态同源（stepDoneSet + genOverviewWarn）——检查渲染函数确实按同一判据加类
const sameSrc = await Eval(`(async () => {
  const m = await import('/js/ui/generate-steps.js');
  const src = m.refreshGenOverview ? m.refreshGenOverview.toString() : '';
  return { hasFn: typeof m.refreshGenOverview === 'function', warnInSrc: src.includes('warn'), doneInSrc: src.includes('done') };
})()`);
check("B14-01 refreshGenOverview 同时维护 warn/done 两类（同源判据）",
  sameSrc.hasFn && sameSrc.warnInSrc && sameSrc.doneInSrc, JSON.stringify(sameSrc));
await shot("ui-detail", "shot-01-step-nav.png");

// ================= 02 动效令牌 =================
const tokens = await Eval(`(() => {
  const cs = getComputedStyle(document.documentElement);
  return { fast: cs.getPropertyValue('--dur-fast').trim(), base: cs.getPropertyValue('--dur-base').trim(),
           slow: cs.getPropertyValue('--dur-slow').trim(), ease: cs.getPropertyValue('--ease-ui').trim() };
})()`);
check("B14-02 :root 定义四个动效令牌", !!(tokens.fast && tokens.base && tokens.slow && tokens.ease), JSON.stringify(tokens));
const usages = await Eval(`(() => {
  const cs = getComputedStyle(document.documentElement);
  const want = { fast: cs.getPropertyValue('--dur-fast').trim(), base: cs.getPropertyValue('--dur-base').trim(), slow: cs.getPropertyValue('--dur-slow').trim() };
  const toS = (v) => { const n = parseFloat(v); return v.includes('ms') ? n / 1000 + 's' : v; };
  const wantS = Object.fromEntries(Object.entries(want).map(([k, v]) => [k, toS(v)]));
  const ease = cs.getPropertyValue('--ease-ui').trim();
  const targets = [...document.querySelectorAll('header nav button, .card, button.ghost, .step-nav .step-dot, .ov-chip, #toast')];
  let match = 0, sampled = 0;
  const seen = [];
  for (const el of targets.slice(0, 40)) {
    const s = getComputedStyle(el);
    const durs = (s.transitionDuration || '').split(',').map((x) => x.trim());
    const eases = (s.transitionTimingFunction || '').split(',').map((x) => x.trim());
    if (!durs.length || durs.every((d) => d === '0s' || d === '')) continue;
    sampled++;
    const okDur = durs.some((d) => Object.values(wantS).includes(d));
    const okEase = eases.some((e) => e === ease);
    if (okDur || okEase) match++;
    if (seen.length < 6) seen.push({ el: el.tagName + '.' + (el.className || '').toString().split(' ')[0], durs, eases: eases.slice(0, 1) });
  }
  return { want: wantS, ease, sampled, match, seen };
})()`);
check("B14-02 采样元素的计算 transition 取自这些令牌", usages.sampled > 0 && usages.match >= Math.ceil(usages.sampled * 0.8),
  `sampled=${usages.sampled} match=${usages.match}`);
console.log("  采样样例：", JSON.stringify(usages.seen));
await shot("ui-detail", "shot-02-motion.png");

// ================= 03 卡分组 =================
const groupCss = await Eval(`(() => {
  const rules = [];
  for (const sheet of document.styleSheets) {
    let list = [];
    try { list = sheet.cssRules; } catch { continue; }
    for (const r of list) if (r.selectorText && r.selectorText.includes('card-group')) rules.push(r.selectorText);
  }
  return rules;
})()`);
check("B14-03 CSS 有 .card-group / .card-group-title 规则",
  groupCss.some((s) => s.includes(".card-group")) && groupCss.some((s) => s.includes(".card-group-title")),
  JSON.stringify(groupCss.slice(0, 6)));
const groups = await Eval(`(() => {
  const all = [...document.querySelectorAll('.card-group')];
  const withTitle = all.filter((g) => g.querySelector('.card-group-title'));
  const sample = withTitle[0] ? getComputedStyle(withTitle[0]) : null;
  return {
    total: all.length, withTitle: withTitle.length,
    titles: withTitle.map((g) => g.querySelector('.card-group-title').textContent.trim()).slice(0, 8),
    bg: sample ? sample.backgroundColor : null, border: sample ? sample.borderTopWidth + ' ' + sample.borderTopColor : null,
    inCard10: document.querySelectorAll('#card-fix-center .card-group, #fix-log-group').length,
    inCard11: document.querySelectorAll('#card-revise .card-group').length,
    cardReviseGroups: [...document.querySelectorAll('#card-revise .card-group-title')].map((t) => t.textContent.trim()),
  };
})()`);
check("B14-03 生成页有卡分组（.card-group + 小标题）", groups.total >= 3 && groups.withTitle >= 3, JSON.stringify({ total: groups.total, withTitle: groups.withTitle }));
check("B14-03 卡 10（编译输出/手动模式）已分组", groups.inCard10 >= 2, "count=" + groups.inCard10);
check("B14-03 卡 11（上下文入口/已加载上下文/影响分析/确认并执行）已分组", groups.inCard11 >= 2,
  JSON.stringify(groups.cardReviseGroups));
check("B14-03 分组容器有可见底/边框（panel-2 + border 令牌）", !!groups.bg && groups.bg !== "rgba(0, 0, 0, 0)" && !!groups.border,
  JSON.stringify({ bg: groups.bg, border: groups.border }));
console.log("  分组小标题：", JSON.stringify(groups.titles));
// 卡 10 = 「修复中心」(#card-fix-center)；滚到它再截（第十四轮实测：id 写错会截到页面顶部）
await Eval(`document.getElementById('card-fix-center')?.scrollIntoView({ block: 'start' })`);
await sleep(500);
await shot("ui-detail", "shot-03-card-group.png");

console.log("---- B14 总览 ----");
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
c.close();
process.exit(failed ? 1 : 0);
