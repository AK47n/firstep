// service-stopped.js — 「应用服务已停止」可见态（工单 bfcache-return-register/01）。
//
// ## 这条可见态为什么存在
//
// 启动器模式（`FIRSTEP_LAUNCHER=1`，双击 `start-app.vbs`）下「关掉最后一个页面 = 停服务」。
// 用户从应用**导航走**时浏览器可能把本文档冻结进 bfcache：`pagehide` 照发告别 ⇒ 服务端
// 见注册表空了就开始 1.5 秒倒计时 ⇒ 到点 `os._exit(0)`。用户**按后退**回来时文档从 bfcache
// 恢复、脚本一行都不重跑，`index.html` head 那段内联脚本会补登记一次（那是信号层，它不碰
// DOM）：宽限内回来 ⇒ 退出作废、应用照常；**晚于宽限回来 ⇒ 服务已经退出**，补登记必然失败。
//
// 第二种情况就是本模块的活：页面还活着、但每个请求都连不上，用户面前原本是一片什么都不
// 响应的死页面。所以内联脚本在补登记失败时广播 `service-stopped`，这里给出说明与下一步。
//
// ## 恢复
//
// 服务不会自己回来（它是被「最后一个页面离开」关掉的），得用户再双击一次启动器。所以这里
// 每 2 秒探一次 `/api/health`：服务一回来就自动重新载入**一次**（用户不用再管这个页面）。
// 手动按钮留给"我已经确认服务在跑"的情况。
import { $, apiGet } from "/js/app.js";

// 事件名与 index.html 内联脚本广播的那个**同一份字面量**（判据 ⑦ 两侧同源；
// tests/js/tab-register-guard.test.mjs）。
const EVENT = "service-stopped";
// 落地态的键与内联脚本写的**同一份字面量**（`documentElement.dataset.serviceStopped`）：
// 广播是**一次性**的，而内联脚本可能在本模块装载之前就广播了（模块图装载途中被浏览器
// 冻结、再恢复那条路）—— 所以装载时先按这个键回读一次（判据 ⑦⑤ 会两侧对账）。
const POLL_MS = 2000;
let inited = false;
let timer = null;

/** 装可见态与恢复轮询（boot.js 调用；DOM 已就绪）。幂等：重复调用不会叠加监听。 */
export function initServiceStopped() {
  if (inited) return;
  inited = true;
  window.addEventListener(EVENT, show);
  const btn = $("btn-service-reload");
  if (btn) btn.addEventListener("click", () => location.reload());
  // 回读内联脚本写下的落地态：广播丢了也照样亮（否则那种时序下用户面前仍是死页面）。
  if (document.documentElement.dataset.serviceStopped === "1") show();
}

/** 显示说明并开始等后端回来。已在显示态就什么都不做（广播可能不止一次）。 */
function show() {
  const box = $("service-stopped");
  if (!box || !box.hidden) return;
  box.hidden = false;
  startPolling();
}

/** 每 2 秒探一次健康端点；服务回来了就重新载入（只重载一次，之后是正常页面）。 */
function startPolling() {
  if (timer !== null) return;
  timer = setInterval(async () => {
    try {
      await apiGet("/api/health");
    } catch (e) {
      return;                       // 还没起来：继续等（用户可能还没双击启动器）
    }
    clearInterval(timer);
    timer = null;
    location.reload();
  }, POLL_MS);
}
