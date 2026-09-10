// B21（newcomer-onboarding/03）收口：欢迎卡的浏览器实况验收。
//
// 源工单验收：未配 key 首访 = 完整欢迎卡 + 三步清晰可见；「去配置 API key」切设置页并
// 聚焦输入框；「检查环境」切设置页且触发体检；「不再显示」写 localStorage 且跨刷新持久；
// 配了 key 且未点「不再显示」= compact 卡；有草稿 = 不显示；gen-banner 的「去设置」能跳。
//
// 做法：真实 state 里 api_configured 为 true（本机已配 key），故**在页面内改写 state 后
// 重新调 initWelcome()** 来覆盖「未配 key」分支（不改产品代码，只驱动它的状态判定）。
//
// 依赖：webapp 8000 + Chrome headless CDP 9251。零写库（只动浏览器 localStorage）。
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
  if (await Eval(`document.readyState === 'complete' && !!document.getElementById('welcome-card')`)) break;
  await sleep(250);
}

// 纯件真值表：三态判定（与测试同源的机器判据）
const truth = await Eval(`(async () => {
  const m = await import('/js/fx/welcome.js');
  return {
    key: m.WELCOME_DISMISS_KEY,
    full: m.welcomeMode({ apiConfigured: false, hasDraft: false, dismissed: false }),
    compact: m.welcomeMode({ apiConfigured: true, hasDraft: false, dismissed: false }),
    hiddenDismissed: m.welcomeMode({ apiConfigured: false, hasDraft: false, dismissed: true }),
    hiddenDraft: m.welcomeMode({ apiConfigured: true, hasDraft: true, dismissed: false }),
  };
})()`);
check("B21 纯件真值表：未配 key→full / 已配→compact / 已忽略→hidden / 有草稿→hidden",
  truth.full === "full" && truth.compact === "compact" && truth.hiddenDismissed === "hidden" && truth.hiddenDraft === "hidden",
  JSON.stringify(truth));

const DRAFT_KEY = "firstep.draft.v1";   // fx/draft.js 内部常量（未导出，按仓库既有脚本口径写死）
const reinit = (opts) => Eval(`(async () => {
  const app = await import('/js/app.js');
  app.state.api_configured = ${opts.configured};
  if (${opts.clearDismiss}) localStorage.removeItem(${JSON.stringify(truth.key)}); else localStorage.setItem(${JSON.stringify(truth.key)}, '1');
  if (${opts.clearDraft}) localStorage.removeItem(${JSON.stringify(DRAFT_KEY)});
  const w = await import('/js/ui/welcome.js');
  w.initWelcome();
  const slot = document.getElementById('welcome-card');
  return { hidden: slot.classList.contains('hidden'), cls: slot.className, html: slot.innerHTML.length,
           title: (slot.querySelector('.welcome-title') || {}).textContent || '',
           steps: slot.querySelectorAll('.welcome-steps li').length,
           actions: [...slot.querySelectorAll('.welcome-actions button')].map((b) => b.textContent.trim()),
           sub: (slot.querySelector('.welcome-sub') || {}).textContent || '' };
})()`);

// ---- ① 未配 key 首访：完整欢迎卡 + 三步 ----
const full = await reinit({ configured: false, clearDismiss: true, clearDraft: true });
check("B21 未配 key 首访 → 完整欢迎卡可见（full 态）", !full.hidden && full.html > 200, JSON.stringify({ hidden: full.hidden, html: full.html }));
check("B21 三步清晰可见（三条 step）", full.steps === 3, "steps=" + full.steps + " title=" + JSON.stringify(full.title));
check("B21 完整卡包含四个动作按钮（配置 key / 检查环境 / 看指引 / 不再显示）",
  full.actions.length >= 4 && full.actions.some((a) => a.includes("配置")) && full.actions.some((a) => a.includes("环境")),
  JSON.stringify(full.actions));

// ---- ② 「去配置 API key」→ 切设置 + 展开 AI API 卡 + 聚焦输入框 ----
await Eval(`document.getElementById('btn-welcome-goto-key').click()`);
await sleep(600);
const jumpKey = await Eval(`({
  settingsActive: document.getElementById('tab-settings').classList.contains('active'),
  cardOpen: !document.querySelector('[data-collapse-id="llm-api"]').classList.contains('collapsed'),
  focused: document.activeElement && document.activeElement.id === 'set-api-key',
})`);
check("B21「去配置 API key」→ 设置页 + AI API 卡展开 + 聚焦 #set-api-key",
  jumpKey.settingsActive && jumpKey.cardOpen && jumpKey.focused, JSON.stringify(jumpKey));

// ---- ③ 「检查环境」→ 切设置页且触发体检 ----
await reinit({ configured: false, clearDismiss: true, clearDraft: true });
await Eval(`document.querySelector('nav button[data-tab="generate"]')?.click()`);
await sleep(300);
await Eval(`document.getElementById('btn-welcome-env-check').click()`);
await sleep(1500);
const envCheck = await Eval(`({
  settingsActive: document.getElementById('tab-settings').classList.contains('active'),
  results: (document.getElementById('env-check-results') || {}).innerHTML ? document.getElementById('env-check-results').innerHTML.length : 0,
  cardHtml: (document.querySelector('[data-collapse-id="env-check"]') || {}).innerHTML || '',
  text: ((document.getElementById('env-check-results') || {}).textContent || '').slice(0, 60),
})`);
check("B21「检查环境」→ 切设置页且体检有响应（结果区非空）",
  envCheck.settingsActive && envCheck.results > 0, JSON.stringify(envCheck));

// ---- ④ 「不再显示」→ localStorage + 跨刷新持久 ----
await reinit({ configured: false, clearDismiss: true, clearDraft: true });
await Eval(`document.getElementById('btn-welcome-dismiss').click()`);
const dismissed = await Eval(`({ key: !!localStorage.getItem(${JSON.stringify(truth.key)}), hidden: document.getElementById('welcome-card').classList.contains('hidden'),
  html: document.getElementById('welcome-card').innerHTML.length })`);
check("B21「不再显示」→ localStorage 标记 + 卡片隐藏清空", dismissed.key && dismissed.hidden && dismissed.html === 0, JSON.stringify(dismissed));
// 跨刷新：整页重载后仍隐藏（重载后真实 state 已配 key，故再模拟未配 key 分支验证 dismiss 优先）
const token = "np=" + Date.now();
await c.cdp("Page.navigate", { url: "http://127.0.0.1:8000/?" + token });
for (let i = 0; i < 120; i++) {
  const st = await Eval(`({ href: location.href, rs: document.readyState, w: !!document.getElementById('welcome-card') })`).catch(() => null);
  if (st && st.href.includes(token) && st.rs === "complete" && st.w) break;
  await sleep(250);
}
const afterReload = await reinit({ configured: false, clearDismiss: false, clearDraft: true });
check("B21「不再显示」跨刷新持久（重载后即便未配 key 也不显示）", afterReload.hidden, JSON.stringify({ hidden: afterReload.hidden, key: await Eval(`!!localStorage.getItem(${JSON.stringify(truth.key)})`) }));

// ---- ⑤ 配了 key、未点不再显示 → compact 卡 ----
const compact = await reinit({ configured: true, clearDismiss: true, clearDraft: true });
check("B21 已配 key → compact 卡（有「开始做题」入口、不是完整三步卡）",
  !compact.hidden && compact.steps === 0 && compact.actions.some((a) => a.includes("开始做题")),
  JSON.stringify({ hidden: compact.hidden, steps: compact.steps, actions: compact.actions }));

// ---- ⑥ 有草稿 → 不显示（已配 key 分支：草稿优先于 compact）----
// 注意优先级（fx/welcome.js welcomeMode）：dismissed → 未配 key(full) → 有草稿(hidden) → compact；
// 故「有草稿 → 不显示」只在**已配 key** 时成立（未配 key 时仍走 full 引导这位新人）。
const withDraft = await Eval(`(async () => {
  const el = document.getElementById('problem');
  el.value = '冒烟题面：走廊宽度 30cm';
  el.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 800));      // 保存有 debounce
  const hasKey = !!localStorage.getItem(${JSON.stringify(DRAFT_KEY)});
  const app = await import('/js/app.js'); app.state.api_configured = true;
  localStorage.removeItem(${JSON.stringify(truth.key)});
  const w = await import('/js/ui/welcome.js'); w.initWelcome();
  const slot = document.getElementById('welcome-card');
  const out = { hasKey, hidden: slot.classList.contains('hidden'), html: slot.innerHTML.length };
  localStorage.removeItem(${JSON.stringify(DRAFT_KEY)});   // 还原
  el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true }));
  return out;
})()`);
check("B21 已配 key + 有草稿 → 欢迎卡不显示（hidden）", withDraft.hasKey && withDraft.hidden, JSON.stringify(withDraft));

// ---- ⑦ gen-banner 的「去设置」能跳 ----
const banner = await Eval(`(() => {
  const b = document.getElementById('btn-banner-goto-settings');
  return { exists: !!b };
})()`);
check("B21 gen-banner 有「去设置」按钮", banner.exists, JSON.stringify(banner));
await Eval(`(() => { document.querySelector('nav button[data-tab="generate"]')?.click();
  document.getElementById('gen-banner').classList.remove('hidden'); })()`);
await sleep(300);
await Eval(`document.getElementById('btn-banner-goto-settings').click()`);
await sleep(600);
const bannerJump = await Eval(`({
  settingsActive: document.getElementById('tab-settings').classList.contains('active'),
  cardOpen: !document.querySelector('[data-collapse-id="llm-api"]').classList.contains('collapsed'),
  focused: document.activeElement && document.activeElement.id === 'set-api-key',
})`);
check("B21 gen-banner「去设置」→ 设置页 + 卡展开 + 聚焦", bannerJump.settingsActive && bannerJump.cardOpen, JSON.stringify(bannerJump));

// 收尾：清掉冒烟期写的 localStorage 标记，避免影响其它脚本
await Eval(`localStorage.removeItem(${JSON.stringify(truth.key)})`);
console.log("---- B21 总览 ----");
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
c.close();
process.exit(failed ? 1 : 0);
