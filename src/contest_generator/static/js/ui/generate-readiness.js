// ui/generate-readiness.js — 生成页 · 就绪检查面板（工单 a3-readiness-check/01-02：
// 判据与 btn-generate 前置校验同源——「检查单结论」与「点了生成被拦的提示」
// 永不吵架）DOM 胶水（阶段 2 工单 19，源自 index.html 检查能否生成节）。
//
// 簇体全量迁入：readinessState（判据单源——btn-generate 监听器（host）与
// refreshGenOverview（generate-steps）各自 readiness 判定共用）/ renderReadinessPanel /
// refreshReadinessPanel / initReadinessCheck（按钮 + 容器事件委托：.rc-go 定位 /
// .rc-recommend 一键跑推荐——与「让 AI 推荐」同一入口）。纯件在 fx/readiness.js
//（工单 08 迁）。
// 状态读：A 簇 generate-recommend（chosenPlatform / selectedSlugs /
// setRecommendClarifications / startRecommend）+ ui/step-state.js（stepDoneSet /
// stepCard——工单 12 拥有；issue 所述 generate-steps.js 不实）+
// 本模块拥有 desktopTopicOutputEnabled（工单 21 自 generate-core 归位——判据输入）。
// 跨簇读方：generate-steps.js 经静态 import 调 readinessState（工单 18 的
// setStepsDeps 接缝已由本票取代）；host 经顶部 import 调 readinessState（btn-generate
// 监听器）/ refreshReadinessPanel（setOnStepChange 回调）/ initReadinessCheck（启动区）。
import { $, apiPost } from "/js/app.js";
import {
  generateReadinessChecks, readinessSoftChecks, readinessRowHTML,
  readinessRowsHTML, outputDirWarnRow,
} from "/js/fx/readiness.js";
import { stepDoneSet, stepCard } from "/js/ui/step-state.js";
import { chosenPlatform, selectedSlugs, setRecommendClarifications, startRecommend } from "/js/ui/generate-recommend.js";

// ---------------------------------------------------------------------------
// 检查能否生成（工单 a3-readiness-check/01-02）：判据与 btn-generate 前置校验
// 同源（单一事实源，先例 collectBindings/pin-verdict-seam/01）——「检查单结论」
// 与「点了生成被拦的提示」永不吵架。渲染走纯函数（node:test 直抽直测），
// 交互在 initReadinessCheck 用容器事件委托。
// ---------------------------------------------------------------------------
// 已迁至 static/js/fx/readiness.js（工单 08）：generateReadinessChecks / readinessSoftChecks /
// readinessRowHTML / readinessRowsHTML。

// 桌面输出开关（工单 21 自 ui/generate-core.js 归位）：readinessState 的
// desktopOutput 判据输入（「输出目录手动」开 = 桌面输出关）。纯 DOM 读，
// core / steps 簇经静态 import 读（单向依赖——无环）。
function desktopTopicOutputEnabled() {
  const checkbox = $("desktop-topic-output");
  return checkbox ? checkbox.checked : true;
}
function readinessState() {
  return {
    chosenPlatform: chosenPlatform,
    selectedSlugs: selectedSlugs,
    problem: $("problem").value.trim(),
    desktopOutput: desktopTopicOutputEnabled(),
    outputDir: $("output-dir").value.trim(),
    recommended: stepDoneSet.has(5),
    hasMainC: !!$("main-c").value.trim(),
  };
}
function renderReadinessPanel() {
  const box = $("readiness-check");
  if (!box || box.classList.contains("hidden")) return;
  const state = readinessState();
  // 一键跑推荐需要题面：题面缺时不给自动按钮（引导先去第 1 步）
  const recommendEnabled = !!state.problem;
  box.innerHTML =
    readinessRowsHTML(generateReadinessChecks(state), { recommendEnabled })
    + readinessRowsHTML(readinessSoftChecks(state), { recommendEnabled: false })
    + '<div id="readiness-warn-slot"></div>';
}

// 输出目录预警槽（工单 beginner-gap-closure/06）：/api/generate/preview-dir 是
// 纯静态预览（零 LLM 调用、不烧 token——粘题面无编号时后端回 needs_title，
// 前端静默）。按载荷缓存防每次状态变化重复请求；请求失败静默降级（预览不
// 阻断检查单——warn 只是提前告知，生成时覆盖/拒绝逻辑不变）。
// 评审整改（06 轮 Standards 轴）：fetch 返回 / 缓存命中后**重新按 id 查槽**再
// 写入——渲染重建（setOnStepChange 等）会换新槽节点，写进已分离的旧节点会
// 整段丢弃（预警消失）。
let _dirWarnCacheKey = null;
let _dirWarnCache = null;
async function refreshOutputDirWarn() {
  const box = $("readiness-check");
  if (!box || box.classList.contains("hidden")) {
    _dirWarnCacheKey = null;
    return;
  }
  const state = readinessState();
  const topicInput = $("topic-id");
  const payload = {
    create_desktop_topic_dir: state.desktopOutput,
    platform: state.chosenPlatform || "",
    topic_id: topicInput ? topicInput.value.trim() : "",
    problem_text: state.problem,
    output_dir: state.outputDir,
  };
  const key = JSON.stringify(payload);
  if (key !== _dirWarnCacheKey) {
    _dirWarnCacheKey = key;
    try {
      _dirWarnCache = await apiPost("/api/generate/preview-dir", payload);
    } catch {
      _dirWarnCache = null;  // 静默降级：预览失败不打断检查单
    }
  }
  const slot = $("readiness-warn-slot");  // 重建后取当前槽，防陈旧节点
  if (!slot) return;
  const warn = outputDirWarnRow(_dirWarnCache);
  slot.innerHTML = warn
    ? readinessRowsHTML([warn], { recommendEnabled: false })
    : "";
}

function refreshReadinessPanel() {
  renderReadinessPanel();
  void refreshOutputDirWarn();
}
function initReadinessCheck() {
  const btn = $("btn-readiness-check");
  const box = $("readiness-check");
  if (!btn || !box) return;
  btn.addEventListener("click", () => {
    box.classList.toggle("hidden");
    if (!box.classList.contains("hidden")) refreshReadinessPanel();
  });
  // 事件委托：定位按钮 / 一键跑推荐（与「让 AI 推荐」同一入口）
  box.addEventListener("click", (e) => {
    const go = e.target.closest(".rc-go");
    if (go) {
      const card = stepCard(parseInt(go.dataset.step, 10));
      if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const rec = e.target.closest(".rc-recommend");
    if (rec) {
      const problem = $("problem").value.trim();
      if (!problem) {
        const card = stepCard(1);
        if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      setRecommendClarifications([]);
      startRecommend(problem);
    }
  });
}



// ---- 本簇导出面（host / generate-steps 顶部 import 活绑定调用点） ----
export { readinessState, desktopTopicOutputEnabled, renderReadinessPanel, refreshReadinessPanel, initReadinessCheck };
