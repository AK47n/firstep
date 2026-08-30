// ui/progress.js — 共享进度面板工厂（阶段 2 工单 03）
//
// 推荐（recPanel，生成页 ui/generate-recommend.js）与提炼（distPanel，母版页
// ui/master.js）两个 SSE 工作流共用的进度状态机 + 双计时器 + 事件分发；面板
// 实例 = 实例化配置 + 事件回调，留在各自簇，本模块只提供工厂。
// 共享状态机语义：状态 = {startedAt, lastEventAt, timerId, finished}；计时器
// 每秒跳动是"没卡死"的唯一证明（模型单次调用期间后端不发任何事件，见
// ADR 0004）；finished 置位后流中断不再报"连接中断"（终态已到后的读流出错 /
// 流结束都放行）。事件词表在 events.py（后端唯一出处）——面板实例的 events
// 表是 JS 侧单点声明，改词表须同步这里与后端契约测试。
import { $ } from "/js/app.js";
import { fmtClock } from "/js/fx/core.js";
import { waitLabel } from "/js/fx/wait.js";

export function makeProgressPanel(spec) {
  const p = { startedAt: 0, lastEventAt: 0, timerId: null, finished: false };
  const totalEl = $(spec.timerTotalId);
  const callEl = $(spec.timerCallId);
  const events = spec.events || {};
  function tick() {   // 双计时器：总用时 + 当前轮/调用等待（lastEventAt = 上次事件心跳）
    const now = Date.now();
    totalEl.textContent = spec.totalLabel + fmtClock((now - p.startedAt) / 1000);
    callEl.textContent = spec.callLabel + fmtClock((now - p.lastEventAt) / 1000);
  }
  function start() {   // 新生命周期：计时归零，秒表跳起（自动清旧定时器，防双击）
    p.startedAt = Date.now();
    p.lastEventAt = Date.now();
    p.finished = false;
    if (p.timerId) clearInterval(p.timerId);
    p.timerId = setInterval(tick, 1000);
    tick();
  }
  function finish() {   // 终态：停表 + 置位（流中断守卫据此放行）
    p.finished = true;
    if (p.timerId) { clearInterval(p.timerId); p.timerId = null; }
  }
  function handleEvent(type, raw) {   // parseSSE 事件回调：JSON 解析 + 心跳 + 词表分发
    let data = {};
    try { data = JSON.parse(raw || "null") || {}; } catch { data = {}; }
    p.lastEventAt = Date.now();
    const handler = events[type];
    if (handler) handler(data);   // 预留事件类型（token 级流式等）——忽略
  }
  return { p, start, finish, handleEvent, tick };
}

/** 长任务秒表（工单 ux-walkthrough-02/12）：在状态元素后插入
 * `.wait-clock` span 显示「已等待 mm:ss」（每秒跳）。target 传元素或
 * 选择器字符串——选择器模式每帧重查元素并重挂 span，兼容容器被
 * innerHTML 重渲染的场景（如参数咨询面板）。流水线 start() → stop()；
 * 复用 fx/wait.js waitLabel（与 fmtClock 同源不漂移）。 */
export function makeWaitClock(target) {
  const clockEl = document.createElement("span");
  clockEl.className = "wait-clock";
  let timerId = null;
  let startedAt = 0;
  function currentEl() {
    return typeof target === "string" ? $(target) : target;
  }
  function render() {
    const el = currentEl();
    if (!el) { stop(); return; }
    if (!el.parentNode) { stop(); return; }       // 元素已离树（容器被换）：停表
    if (clockEl.parentNode !== el.parentNode) {
      el.insertAdjacentElement("afterend", clockEl);   // 容器重渲染后重挂
    }
    clockEl.textContent = waitLabel((Date.now() - startedAt) / 1000);
  }
  function start() {
    startedAt = Date.now();
    if (timerId) clearInterval(timerId);
    timerId = setInterval(render, 1000);
    render();
  }
  function stop() {
    if (timerId) { clearInterval(timerId); timerId = null; }
    if (clockEl.parentNode) clockEl.remove();   // 移除空 span，不留 6px 间隙（评审整改）
  }
  return { start, stop };
}

/** 长任务「取消本次等待」按钮（工单 ux-walkthrough-02/14）：与 makeWaitClock
 * 同款目标解析（元素 / 选择器，容器重渲染后重挂）；show 显示 → 点击触发
 * onClick（中止请求）→ hide 隐藏（流程 finally 调用）。取消反馈文案由各
 * 流水线在状态区给出（如「已取消等待：…」），按钮本身不置灰。 */
export function makeCancelButton(target, opts = {}) {
  const btnEl = document.createElement("button");
  btnEl.type = "button";
  btnEl.className = "wait-cancel";
  btnEl.textContent = opts.label || "取消本次等待";
  let handler = null;
  btnEl.addEventListener("click", () => { if (handler) handler(); });
  function currentEl() {
    return typeof target === "string" ? $(target) : target;
  }
  function attach() {
    const el = currentEl();
    if (!el || !el.parentNode) return false;
    if (btnEl.parentNode !== el.parentNode) el.insertAdjacentElement("afterend", btnEl);
    return true;
  }
  function show() { attach(); }
  function hide() { if (btnEl.parentNode) btnEl.remove(); }
  return { show, hide, onClick(fn) { handler = fn; } };
}
