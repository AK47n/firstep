// ui/ai-banner.js — 全局「AI 行动中」顶部粘性横幅胶水（工单 ai-action-banner/01）
// 计数闸语义见 fx/ai-action.js；本模块只做状态渲染：
// count > 0 → 显示 #ai-action-banner，文案 = aiActionBannerLabel(label)
// （有 label「AI 行动中：<label>」，空兜底「AI 行动中…」）；count 归零 → 隐藏。
// 元素缺失静默返回（安全降级——横幅是纯观察者，不阻塞任何流程）。
// 接入约定：各簇在「调用点级」成对调用 aiActionStart(label) / aiActionStop()
// （async 流程函数内 try 前 start、finally 后 stop），禁止接入共享 setBusy
// 闸函数（避免嵌套双计数）。
import { $ } from "/js/app.js";
import { aiActionStep, aiActionBannerLabel } from "/js/fx/ai-action.js";

let state = { count: 0, label: "" };

export function aiActionStart(label) {
  state = aiActionStep(state, { type: "start", label });
  render();
}

export function aiActionStop() {
  state = aiActionStep(state, { type: "stop" });
  render();
}

function render() {
  const el = $("ai-action-banner");
  if (!el) return;
  if (state.count > 0) {
    el.classList.remove("hidden");
    const labelEl = $("ai-action-label");
    if (labelEl) labelEl.textContent = aiActionBannerLabel(state.label);
  } else {
    el.classList.add("hidden");
  }
}
