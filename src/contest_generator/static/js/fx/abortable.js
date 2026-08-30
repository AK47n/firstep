// fx/abortable.js — 可取消长任务的中止控制器封装（工单 ux-walkthrough-02/14）：
// 分钟级长任务（拆解/执行/深化/参数速调/AI 对话/预读）等待期「取消本次
// 等待」——begin() 取新 AbortController 的 signal 传给 fetch / SSE 运行器；
// abort() 幂等（重复取消第二次返回 false）；isAbortError 统一识别取消错误。
// 纯函数无 DOM（AbortController 是浏览器/Node 内置事件 API）；取消按钮
// 的 DOM 工作在 ui 层（makeCancelButton，ui/progress.js）。
// 模块约定见 fx/core.js 头部。

/** 可中止实例：begin() 开新一轮（旧实例作废），abort() 幂等取消。
 * 返回 {begin, isActive, abort, clear}——clear 在流程 finally 调用。 */
export function makeAbortable() {
  let ctl = null;
  return {
    begin() {
      if (ctl && !ctl.signal.aborted) ctl.abort();   // 上一轮 in-flight 先取消（评审整改：不静默丢弃）
      ctl = new AbortController();
      return ctl.signal;
    },
    isActive() { return ctl !== null; },
    abort() {
      if (!ctl || ctl.signal.aborted) return false;   // 无进行中请求 / 已取消 = 无操作（幂等）
      ctl.abort();
      return true;
    },
    clear() { ctl = null; },
  };
}

/** 取消错误识别：fetch/流中止抛的 DOMException.name === "AbortError"。 */
export function isAbortError(err) {
  return !!(err && err.name === "AbortError");
}

if (typeof window !== "undefined") {
  Object.assign(window, { makeAbortable, isAbortError });
}
