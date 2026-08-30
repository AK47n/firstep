// fx/errors.js — 前端错误展示纯函数（工单 ux-walkthrough-02/11）：
// parseError 把 fetch（handle 抛的 Error{status,message}）/ SSE 内联
// （{detail,status}）/ AbortError / 字符串 / null 归一为 {text, status, kind}；
// isLongError 裁定「长错误/500 → 常驻可复制」策略。纯函数无 DOM/fetch，
// toast 等 UI 动作在 ui 层（app.js toastError）。模块约定见 fx/core.js 头部。

/** 错误解析：返回 {text, status, kind}。
 * kind ∈ error（业务 / HTTP）/ cancelled（AbortError）/ unknown（无凭据）。
 * HTTP >= 500 的 text 带「请求失败（HTTP N）：」前缀（防重复前缀：message
 * 已以该前缀开头则不叠加）。 */
export function parseError(err, fallback) {
  const fb = String(fallback || "请求失败（未知原因）");
  if (err == null) return { text: fb, status: null, kind: "unknown" };
  if (typeof err === "string") return { text: err || fb, status: null, kind: "error" };
  const raw = err.status;
  const status = (raw !== null && raw !== undefined && raw !== "" && Number.isFinite(Number(raw)))
    ? Number(raw)
    : null;
  if (err.name === "AbortError") {
    return { text: "请求已取消（任务未被删除，可稍后重试）", status, kind: "cancelled" };
  }
  let text = "";
  if (typeof err.detail === "string" && err.detail) text = err.detail;
  else if (typeof err.message === "string" && err.message) text = err.message;
  if (status && !text.startsWith("请求失败（HTTP")) {
    text = "请求失败（HTTP " + status + "）：" + text;
    if (text.endsWith("：")) text = text.slice(0, -1);   // 无 detail 时不留悬空冒号
  }
  return { text: text || fb, status, kind: status && status >= 500 ? "server" : "error" };
}

/** 长错误 / 5xx 判定：服务器错误或超阈值 → 常驻可复制（toastError 用）。
 * 5xx 判定走 parseError 的 kind（单一出处，防两处分叉）。 */
export const ERROR_LONG_THRESHOLD = 120;
export function isLongError(parsed) {
  if (!parsed) return false;
  if (parsed.kind === "server") return true;
  return String(parsed.text || "").length > ERROR_LONG_THRESHOLD;
}

/** SSE/裸 fetch 错误体归一（SSE 内联 6 处共用，工单 ux-walkthrough-02/11）：
 * status + json 错误体 → parseError（同一解析路径，消息含 HTTP 状态）。 */
export function parseHttpError(status, data) {
  return parseError({ ...(data || {}), status: Number(status) || null });
}

if (typeof window !== "undefined") {
  Object.assign(window, { parseError, parseHttpError, isLongError, ERROR_LONG_THRESHOLD });
}
