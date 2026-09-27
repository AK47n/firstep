// fx/hwcheck-triage.js — 硬件检测栏目的纯函数：**现象回填 / AI 排障（本栏目唯一的 LLM 入口）**。
//
// 由 `fx/hwcheck.js` 按职责整段搬来（工单 hwcheck-hygiene/09），**只搬不改**。
// 模块约定与六件的依赖方向见 `fx/hwcheck-state.js` 头部——那份是**单源**，
// 别在这里再抄一遍（抄六遍就是六份会各自漂移的散文）。

import { esc } from "./core.js";

// ===========================================================================
// 工单 module-hwcheck/08：现象回填 + AI 排障（本栏目唯一的 LLM 入口）
//
// 分工照旧：**判据全在服务端**——事实约束（引脚名 / 模块名必须来自本次检测
// 上下文）与兜底文案都在 `hwcheck_triage` 域层，前端只做两件事：把"页面现在
// 的现象与勾选"装配成请求体、把服务端给的建议渲染成 HTML。前端不判建议对不对
// （那会变成第二个判据来源）。
// ===========================================================================

// 定性标签的兜底文案（服务端 verdict_label 缺失时才用；正常情况用服务端的）
const HWCHECK_VERDICT_FALLBACK = "先按下面的线索查";

// hwcheckSymptomText(state)：学生填的现象（去首尾空白；空串 = 还不能提交）。
export function hwcheckSymptomText(state) {
  return String((state && state.symptom) || "").trim();
}

// hwcheckCanTriage(state)：有检测工程 + 填了现象，才让点「让 AI 分析」。
// 没工程时后端必拒（400 目录不存在），这里是"按钮别让人白点"。
export function hwcheckCanTriage(state) {
  const dir = String((state && state.project && state.project.outputDir) || "");
  return !!dir && !!hwcheckSymptomText(state);
}

// hwcheckTriagePayload(state)：排障请求体（工程目录 / 现象 / 当前勾选）。
// 勾选随请求走（与页面上显示的是同一份）——服务端把它当**上下文**用（模型看得到
// 哪些还验），并在"这几秒里没人动过记录"时顺带落盘（工单 hwcheck-hygiene/03：
// 排障期间学生在页面上勾的那几条由清单端点写，比这份快照新，不许被盖掉）。
export function hwcheckTriagePayload(state) {
  return {
    output_dir: String((state && state.project && state.project.outputDir) || ""),
    symptom: hwcheckSymptomText(state),
    checked_ids: (state && Array.isArray(state.checklistChecked))
      ? state.checklistChecked.slice()
      : [],
  };
}

// hwcheckChecklistPayload(state)：勾选落盘请求体（零 LLM 的轻端点）。
export function hwcheckChecklistPayload(state) {
  return {
    output_dir: String((state && state.project && state.project.outputDir) || ""),
    checked_ids: (state && Array.isArray(state.checklistChecked))
      ? state.checklistChecked.slice()
      : [],
  };
}

// hwcheckAdviceState(state, payload)：排障响应 → 建议面板状态。
// 载荷缺 advice = 保留当前面板（出错响应不许把上一次的建议抹掉）；失败的
// 原因（message）单独存一个键——它是"为什么这次是兜底"，不是建议正文。
export function hwcheckAdviceState(state, payload) {
  const data = payload || {};
  const advice = (data.advice && typeof data.advice === "object") ? data.advice : null;
  if (!advice) {
    return {
      advice: (state && state.advice) || null,
      adviceMessage: String(data.message || (state && state.adviceMessage) || ""),
      adviceDegraded: !!(data.degraded || (state && state.adviceDegraded)),
    };
  }
  return {
    advice,
    adviceMessage: String(data.message || ""),
    adviceDegraded: !!data.degraded,
    triageError: "",
  };
}

// hwcheckRecordState(state, payload)：工程回读载荷里的检测记录 → 状态。
// 载荷没有 record 键（preview / generate 不带它）= 不动现状；有记录时把
// 现象 / 勾选 / 建议一起回显（刷新后"我上次填了什么、它说了什么"还在）。
export function hwcheckRecordState(state, payload) {
  const data = payload || {};
  const record = (data.record && typeof data.record === "object") ? data.record : null;
  if (!record) return {};
  const advice = (record.advice && typeof record.advice === "object") ? record.advice : null;
  return {
    symptom: String(record.symptom || ""),
    checklistChecked: Array.isArray(record.checked_ids)
      ? record.checked_ids.filter((id) => typeof id === "string")
      : [],
    advice,
    adviceMessage: "",
    adviceDegraded: !!(advice && advice.degraded),
  };
}

// hwcheckChecklistState(state, payload)：勾选落盘端点的响应 → 只更新勾选。
// **只认 checked_ids**（工单 08 评审整改）：这个端点的响应里也带着记录里的
// 现象与建议，整份采纳会把用户"还没提交的现象"覆盖成服务端旧值——下一页
// 提交时那句原话就丢了。现象的真源是输入框，建议的真源是排障端点。
export function hwcheckChecklistState(state, payload) {
  const data = payload || {};
  const record = (data.record && typeof data.record === "object") ? data.record : null;
  if (!record || !Array.isArray(record.checked_ids)) return {};
  return {
    checklistChecked: record.checked_ids.filter((id) => typeof id === "string"),
  };
}

// hwcheckTriageErrorHTML(message)：排障请求本身失败（网络 / 400）的提示。
// 与"模型失败"分开说：模型失败是 200 + 兜底建议，"请求失败"才是这一段。
export function hwcheckTriageErrorHTML(message) {
  return `<div class="error">AI 排障没能提交：${esc(message || "")}</div>`;
}

// hwcheckAdviceEmptyHTML()：还没分析过 / 还没生成工程时的占位。
export function hwcheckAdviceEmptyHTML() {
  return '<div class="hwcheck-hint">跑完一遍之后，把上面「实际现象」填进来，'
    + "点「让 AI 分析」——它会先说这更像接线、器件还是程序的问题，再给下一步查什么。"
    + "检测没过是正常结果，不用怕填。</div>";
}

// hwcheckAdviceHTML(advice)：建议面板 = 定性 + 一句话判断 + 可能原因 +
// 下一步查什么 + 反馈出口；`degraded` 那份明说"这是兜底文案、可重试"，
// 不把它当模型结论（票面：LLM 失败不阻断）。
export function hwcheckAdviceHTML(advice) {
  const data = (advice && typeof advice === "object") ? advice : null;
  if (!data) return hwcheckAdviceEmptyHTML();
  const degraded = !!data.degraded;
  const label = String(data.verdict_label || HWCHECK_VERDICT_FALLBACK);
  const causes = (Array.isArray(data.causes) ? data.causes : [])
    .filter((item) => typeof item === "string" && item.trim());
  const steps = (Array.isArray(data.steps) ? data.steps : [])
    .filter((item) => typeof item === "string" && item.trim());
  const summary = String(data.summary || "");
  const issue = String(data.issue_hint || "");
  const blocks = [];
  if (causes.length) {
    blocks.push('<div class="hwcheck-advice-block">'
      + '<div class="hwcheck-advice-title">可能原因</div><ul>'
      + causes.map((item) => `<li>${esc(item)}</li>`).join("") + "</ul></div>");
  }
  if (steps.length) {
    blocks.push('<div class="hwcheck-advice-block">'
      + '<div class="hwcheck-advice-title">下一步查什么</div><ol>'
      + steps.map((item) => `<li>${esc(item)}</li>`).join("") + "</ol></div>");
  }
  return `<div class="hwcheck-advice${degraded ? " degraded" : ""}">`
    + '<div class="hwcheck-advice-head">'
    + `<span class="hwcheck-advice-verdict">${esc(label)}</span>`
    + (degraded
      ? '<span class="badge no-master">兜底文案（AI 这次没给出来，可以重试）</span>'
      : "")
    + "</div>"
    + (summary ? `<div class="hwcheck-advice-summary">${esc(summary)}</div>` : "")
    + blocks.join("")
    + (issue ? `<div class="hwcheck-hint">${esc(issue)}</div>` : "")
    + "</div>";
}

// —— 探针桥（CDP / devtools 与页面内联脚本的既有出口）——
if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckSymptomText, hwcheckCanTriage, hwcheckTriagePayload,
    hwcheckChecklistPayload, hwcheckAdviceState, hwcheckRecordState,
    hwcheckChecklistState, hwcheckTriageErrorHTML, hwcheckAdviceHTML,
    hwcheckAdviceEmptyHTML, HWCHECK_VERDICT_FALLBACK,
  });
}
