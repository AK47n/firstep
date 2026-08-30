// fx/wait.js — 长任务等待展示纯函数（工单 ux-walkthrough-02/12）：
// 六类分钟级等待（推荐/修订/参数/修复/商量/预读）统一「已等待 mm:ss」
// 计时文案。复用 fx/core.js fmtClock（mm:ss，分可超 59）作唯一计时显示；
// 无阶段场景用 WAIT_GENERIC_LINE 通用行（推荐面板首条事件前兜底）。
// 纯函数无 DOM；秒表实例（setInterval + 兄弟 span）在 ui 层
// （makeWaitClock，ui/progress.js）。模块约定见 fx/core.js 头部。
import { fmtClock } from "./core.js";

/** 无阶段场景的通用等待行（阶段来源缺失时用）。 */
export const WAIT_GENERIC_LINE = "AI 正在处理…（可能要几分钟）";

/** 已等待标签：复用 fmtClock（0 秒 →「已等待 00:00」，1 分 →「已等待 01:00」，
 * 小时级分可超 59，两位补零与既有计时器显示一致）。 */
export function waitLabel(sec) {
  return "已等待 " + fmtClock(sec);
}

if (typeof window !== "undefined") {
  Object.assign(window, { WAIT_GENERIC_LINE, waitLabel });
}
