// fx/core.js — 前端纯函数模块（工单 frontend-es-modules/01：共享件单源化）
//
// 模块约定（全部 fx/*.js 同守）：
// 1. 只含纯函数：收数据返数据，不碰 DOM / fetch / 定时器；
// 2. 浏览器端启用方式 = 主体脚本 module 化顶部静态 import（index.html 的
//    <script type="module"> 首部 import '/js/fx/...'，module 语义保证本模块
//    先求值）；window 同名桥（本文件尾部）为兼容层，供探针脚本 / devtools
//    按全局名取用；
// 3. node 端（tests/js）直接 import 本模块做单测，不再字符串提取；
// 4. 同域常量随函数入驻；新纯函数一律写进 fx 模块（勿回 index.html 内联）。
export function esc(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

export function formatSize(bytes) {
  if (!Number.isFinite(bytes)) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = bytes, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return (i === 0 ? String(Math.round(v)) : v.toFixed(1)) + " " + units[i];
}

export function fmtClock(sec) {   // 计时器显示：mm:ss（分可超 59）
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}
export function fmtDuration(sec) {   // 完成行："12 分 34 秒" / "45 秒" / "1 小时 2 分 3 秒"
  sec = Math.round(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const parts = [];
  if (h) parts.push(h + " 小时");
  if (m || h) parts.push(m + " 分");
  parts.push(s + " 秒");
  return parts.join(" ");
}

export function fmtEta(sec) {   // 剩余时间：人话（"约 12 分钟" / "约 1 小时 20 分" / "不到 1 分钟"）
  // 与 fmtDuration 同一套词形（小时 / 分 / 秒），只是**倒过来用**：
  // 剩余时间是估算，不该精确到秒——"剩余 720 秒" 要用户自己换算，而
  // "约 12 分钟" 一眼就知道要不要现在等（工单 resumable-download/05）。
  //
  // 分档：< 60 秒 = 「不到 1 分钟」；≥ 60 秒按**四舍五入到分**（59 秒 → 「约 1 分钟」：
  // 这个当口说「不到 1 分钟」会显得离谱）。上限 99 小时加「以上」，避免出现吓人的巨数。
  const total = Number(sec);
  if (!Number.isFinite(total) || total < 60) return "不到 1 分钟";
  const minutes = Math.round(total / 60);
  if (minutes < 60) return `约 ${minutes} 分钟`;
  const h = Math.floor(minutes / 60), m = minutes % 60;
  if (h > 99) return "约 99 小时以上";
  return m > 0 ? `约 ${h} 小时 ${m} 分` : `约 ${h} 小时`;
}

export function truncate(text, n) {
  text = String(text);
  return text.length <= n ? text : text.slice(0, n) + "…";
}

// --- 下载进度共用（工单 resumable-download/05：两条链路同一套口径） -------------
//
// 放在 core 而不是任一业务模块：资料库链路与完整包链路都要用，谁 import 谁都会让
// 两个同域模块互相依赖（后端也是这么分的：共用件下沉，见 download_resume.py）。

/** 速度低于这个值就明写「网络较慢」——**显示阈值**，不参与任何判定（慢 ≠ 失败）。 */
export const SLOW_SPEED_BPS = 50 * 1024;

/** 下载失败话术：按 `error_kind` 分两类（spec 的状态面契约）。
 *
 * - `verify`（下载内容与清单不符）：**重下也不会有变化**，必须说清楚，
 *   否则用户会一直点重试；
 * - 其余（network / 空）：网络类，带上**已下载百分比**并说明「重试会接着下」。
 *
 * **不许解析 `error` 文案**：文案会改、字段不会——分类的唯一判据是字段。
 */
export function downloadFailureText(status) {
  const s = status || {};
  const pct = downloadedPercent(s);
  if ((s.error_kind || "") === "verify") {
    return "下载内容校验失败（重新下载也不会有变化）；如果是刚发布的版本，请稍后重试或反馈给我们。";
  }
  return `网络中断（已下载 ${pct}%）；点击重试会从这里接着下。`;
}

/** 「正在自动重试（第 N 次）：…」那一行的话术（资料库与完整包共用）。
 *
 * 三个信息各从**自己的字段**来，一个都不从文案里抠：
 * 次数 = `retry_count`，原因 = `message`，从多少接着下 = `resume_percent`（-1 = 未知）。
 * 第一版是拿正则从 `message` 里摘「从 X% 接着下」——那等于把文案当接口
 * （双轴评审都判了它），所以后端把这三件事拆成了三个字段。
 */
export function retryProgressText(retryCount, message, resumePercent) {
  const attempt = Number(retryCount) || 1;
  const reason = String(message || "").trim() || "网络中断";
  const pct = Number(resumePercent);
  const tail = Number.isFinite(pct) && pct >= 0 ? `，从 ${pct}% 接着下` : "";
  return `正在自动重试（第 ${attempt} 次）：${reason}${tail}`;
}

/** 「自动重试 N 次」留痕（完成行用；没重试过 = 空串）。 */
export function retryNoteText(retryCount) {
  const n = Number(retryCount) || 0;
  return n > 0 ? `（下载中自动重试 ${n} 次）` : "";
}

/** 「已下载 X%」的百分比（总量未知 = 0；`error_kind` 只作分类不作百分比来源）。 */
export function downloadedPercent(status) {
  const s = status || {};
  const total = s.total_bytes || 0;
  if (total <= 0) return 0;
  return Math.min(100, Math.round(((s.total_downloaded_bytes || 0) / total) * 100));
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    esc, formatSize, fmtClock, fmtDuration, fmtEta, truncate,
    SLOW_SPEED_BPS, downloadFailureText, retryProgressText, retryNoteText,
    downloadedPercent,
  });
}
