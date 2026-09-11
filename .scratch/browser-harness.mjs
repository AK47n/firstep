// .scratch/browser-harness.mjs —— playwright 侧「姿势」助手（工单 real-acceptance/07）
//
// 为什么另起一个文件（而不是塞进 cdp-harness.mjs）：cdp-harness 是**零依赖的裸 CDP
// 传输层**（connect / rebuildTab + 判定纯函数，服务 overhaul/refine 那批脚本），本文件
// 是**playwright page 对象**的操作姿势（真机验收脚本那批）。本文件同样零依赖：
// **不 import playwright**，page 由调用方传进来 —— 于是「姿势」本身可以用假 page 单测
// （tests/js/browser-harness.test.mjs），不必起浏览器。
//
// 四个坑（第十六轮 B24 实测；全文见
// .scratch/real-acceptance/issues/07-browser-acceptance-pitfalls.md，真机单照抄
// 挂账单 01 的「B 组统一前置 · 姿势清单」）：
//
//   坑 1 · 折叠 + 页签：`.card.collapsed > *:not(h2) { display:none !important }`。
//          卡默认折叠、卡内又是页签式时不展开 + 不切页签 ⇒ 卡内元素全不可见，
//          playwright 的 `fill/click` 一路等到 30s 超时，报错只说 "element is not
//          visible"——看不出是页签没切。姿势 = expandCard()。
//   坑 2 · `waitForFunction(fn, arg, options)`：**超时是第三个参数**，写第二个会被当
//          arg ⇒ 拿到默认 30s（现场表现「我明明写了 15 分钟，却 30 秒就红」）。
//          本文件的助手不吃这个坑（超时都是显式 options 对象）。
//   坑 3 · `page.evaluate` 里 await 长流程 = 单次 CDP 调用挂几十秒（分析实测 28s，
//          深化分钟级），期间 node 侧任何 evaluate 都可能拿不到响应，看着像「渲染进程
//          无响应」。姿势 = **kick off 不 await** + pollUntil() 在 node 侧轮询 DOM。
//   坑 4 · 模态确认不点 = 请求根本不发（`reviseApply` / `reviseRollback` 各有一层
//          confirmModal；服务端日志里只有 analyze 就是这个原因）。姿势 = 等模态出现，
//          **按按钮文字**点：`page.locator(".confirm-modal button, .modal button")
//          .filter({ hasText: /执行修订|确认回滚/ })`——别只等状态行。
//
// 约定：本文件只放「与具体页面无关」的姿势；页面里元素 id / 文案归各脚本自己。

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// cardSelector：卡片 id → 选择器（"card-revise" 与 "#card-revise" 都认）。
export function cardSelector(cardId) {
  const s = String(cardId || "").trim();
  if (!s) throw new Error("expandCard：cardId 不能为空");
  return s.startsWith("#") || s.startsWith(".") || s.startsWith("[") ? s : "#" + s;
}

// observationDone：轮询观测是否到达终态。
//   - 对象：看 `done` 字段（`{done:true, …}` = 终态；`{done:false, st:"…"}` = 未到）
//   - 其余（true / 1 / "ok"）：真值即终态
export function observationDone(v) {
  if (v && typeof v === "object") return !!v.done;
  return !!v;
}

// asObservation：把任意返回值统一成对象（非对象包成 `{value}`），
// 便于调用方既能拿到终态快照、又能读 elapsedMs / timeout。
export function asObservation(v) {
  return v && typeof v === "object" && !Array.isArray(v) ? v : { value: v };
}

// pollUntil(page, fn, {timeoutMs, every, label}) —— node 侧轮询 DOM（坑 3 的姿势）。
//
//   fn 在**页面里**执行（page.evaluate），返回 `{done, …观测字段}`；done 为真值即终态。
//   返回 = **最后一次观测对象** + `{done, elapsedMs, observations, timeout?}`
//   —— 终态快照（如 `st` / `msg` / 行数）与判定同一份数据，脚本不再自己存一份。
//   evaluate 抛错（导航中途 / 元素还没渲染出来）按「未就绪」处理，不炸；超时如实返回
//   `timeout:true`（并往 stderr 打一行，批跑器的输出里能看到），由脚本决定怎么记。
export async function pollUntil(page, fn, { timeoutMs = 600000, every = 3000, label = "" } = {}) {
  const t0 = Date.now();
  let last = null;
  let observations = 0;
  for (;;) {
    let v = null;
    try { v = await page.evaluate(fn); } catch { v = null; }
    observations++;
    last = v;
    const elapsedMs = Date.now() - t0;
    if (observationDone(v)) return { ...asObservation(v), done: true, elapsedMs, observations };
    if (elapsedMs >= timeoutMs) {
      console.error(`[browser-harness] 轮询超时（${label || "未命名"}，${timeoutMs}ms）：`
        + `最后一次观测 ${JSON.stringify(v)}`);
      return { ...asObservation(v), done: false, timeout: true, elapsedMs, observations, label };
    }
    await sleep(every);
  }
}

// expandCard(page, cardId, tabSelector, {attachMs, visibleMs}) —— 展开卡 + 切页签 + 等可见（坑 1）。
//
//   顺序（这条顺序就是姿势本身）：
//     ① waitForSelector(卡, {state:"attached"})——卡在 DOM 里（display:none 也算 attached）
//     ② 页面内一次做完：`classList.remove("collapsed")` + 点页签（DOM click——
//        playwright 的 click 要求可见，折叠态下必然失败；DOM click 不受可见性限制）
//     ③ waitForSelector(页签条 || 卡, {state:"visible"})——**可见性判据**：折叠态整块
//        `display:none`，页签条可见 ⇔ 卡真的展开了（这就是「等卡变可见」的可靠写法）
//   返回 `{card, witness, wasCollapsed, tabFound}`（调用方可据此记 note）。
//   ③ 超时抛错带上下文：多半是「卡所在步骤整块没显示」（如结果区要走过一次生成），
//   而不是选择器写错——这正是坑 1 花掉的那 30 秒换来的信息。
export async function expandCard(
  page, cardId, tabSelector = "",
  { attachMs = 20000, visibleMs = 15000 } = {},
) {
  const card = cardSelector(cardId);
  await page.waitForSelector(card, { state: "attached", timeout: attachMs });
  const state = await page.evaluate(([sel, tab]) => {
    const el = document.querySelector(sel);
    if (!el) return { card: false, wasCollapsed: false, tabFound: false };
    const wasCollapsed = el.classList.contains("collapsed");
    el.classList.remove("collapsed");
    let tabFound = false;
    if (tab) {
      const t = document.querySelector(tab);
      if (t) { t.click(); tabFound = true; }
    }
    return { card: true, wasCollapsed, tabFound };
  }, [card, tabSelector || ""]);
  const witness = tabSelector || card;
  try {
    await page.waitForSelector(witness, { state: "visible", timeout: visibleMs });
  } catch {
    throw new Error(`expandCard：展开 ${card}`
      + `${tabSelector ? " + 切页签 " + tabSelector : ""} 后 ${witness} 仍不可见`
      + `（${visibleMs}ms）——卡所在步骤可能整块没显示（例如结果区要走过一次生成），`
      + `或页签选择器不对（实测真值：修复中心卡 #card-fix-center、`
      + `修订页签 #revise-tabs .revise-tab[data-tab="revise"]）`);
  }
  return { ...state, card, witness };
}
