// fx/ai-action.js — 全局「AI 行动中」计数闸状态机（工单 ai-action-banner/01）
// 纯函数：state = {count, label}，action = {type: "start"|"stop", label?}。
// 语义：start 计数 +1，count 由 0→1 时固定 label（首启固定——并发时横幅显示
// 最先启动的动作名，后续 start 不覆盖）；stop 计数 -1 下限 0，归零清 label。
// 动机：多簇 LLM 流程（预读/推荐/商量/任务/修复/修订/生成…）各自成对调用
// start/stop，共享计数保证嵌套存在时不早退、全部结束才隐藏（横幅纯观察者，
// 不改任何 busy 闸语义）。
export function aiActionStep(state, action) {
  if (!state || typeof state !== "object" || typeof state.count !== "number") return state;
  if (!action || typeof action !== "object") return state;
  if (action.type === "start") {
    const count = state.count + 1;
    const label = (state.count === 0 && typeof action.label === "string")
      ? action.label : state.label;
    return { count, label };
  }
  if (action.type === "stop") {
    const count = Math.max(0, state.count - 1);
    return { count, label: count === 0 ? "" : state.label };
  }
  return state;
}

/** 横幅文案（拼接单点在 fx，ui 胶水只调不拼——空 label 兜底「AI 行动中…」，
 *  评审整改：此前 ui 拼 "AI 行动中："+(label||"…") 输出「AI 行动中：…」带冒号，
 *  与 spec 契约「AI 行动中…」不符）。 */
export function aiActionBannerLabel(label) {
  return label ? "AI 行动中：" + label : "AI 行动中…";
}
