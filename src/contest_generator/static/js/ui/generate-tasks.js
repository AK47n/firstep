// ui/generate-tasks.js — 生成页 · 任务推进簇（工单 task-progress/01-03：
// 拆解任务 / 逐任务执行 / 状态管理）DOM 胶水。
//
// 任务推进 = 生成后的主推进入口：AI 把题面 + 功能需求 + 评分点 + 模块接口 +
// main.c 拆成有序任务清单（落盘 .contest_tasks.json）→ 任务卡逐张执行 →
// 每步备份 + 编译验证闭环 → 状态徽章实时更新。
//
// 本簇状态 = tasks（私有对象）；输出目录复用「修订与深化」卡的已加载上下文
// （reviseGetDir——跨簇只读 import，主写簇归 generate-revise.js）。
// 赛道事件词表镜像 events.py：task_planning / task_executing / compile_start /
// fix_start / verify_result / llm_telemetry / done / error。
// 纯件在 fx/task.js（taskStatusLabel / taskCardHTML / tasksGridHTML …）。
// 依赖：app.js（$ / apiPost / toast）+ fx/core.js（esc）+ fx/llm.js
//（parseSSE / formatLLMTelemetry）+ fx/task.js + ui/usage.js（recordLLMUsage）
// + ui/step-state.js（markStepDone）+ ui/confirm.js（confirmModal）。
import { $, apiPost, toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { esc } from "/js/fx/core.js";
import { parseSSE, formatLLMTelemetry } from "/js/fx/llm.js";
import { tasksGridHTML, tasksProgressText } from "/js/fx/task.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { markStepDone } from "/js/ui/step-state.js";
import { scorePoints } from "./generate-recommend.js";  // 当前会话推荐评分点（历史目录为空）
import { reviseGetDir } from "./generate-revise.js";  // 已加载上下文的输出目录（只读）

let tasks = {
  outputDir: "",      // 拆解 / 执行针对的输出目录
  plan: null,         // /api/tasks/plan 的 done 载荷
  busy: false,        // 任一流程运行中（按钮置灰）
};

function tasksSetBusy(busy) {
  tasks.busy = busy;
  ["btn-tasks-plan", "btn-tasks-replan"].forEach((id) => { $(id).disabled = busy; });
}

function tasksRender() {
  const plan = tasks.plan;
  const grid = $("tasks-grid");
  if (!plan || !(plan.tasks || []).length) {
    grid.classList.add("hidden");
    grid.innerHTML = "";
  } else {
    grid.innerHTML = tasksGridHTML(plan, {
      scorePoints: scorePoints,
      actions: (task) => {
        // 工单 02 起按状态显隐「做这一步」/ 回滚；01 只展示（操作随簇扩展）
        const show = task.status === "pending" || task.status === "failed"
          || task.status === "unverified";
        return show ? '<button class="btn-task-run" data-task="' + esc(task.id) + '">做这一步</button>' : "";
      },
    });
    grid.classList.remove("hidden");
  }
  $("tasks-progress").textContent = tasksProgressText(plan);
  $("btn-tasks-replan").classList.toggle("hidden", !(plan && (plan.tasks || []).length));
}

function tasksResetMessages() {
  $("tasks-msg").textContent = "";
  $("tasks-status").textContent = "";
  const tel = $("tasks-llm-telemetry");
  tel.classList.add("hidden");
  tel.textContent = "";
}

/** SSE 流（reviseRunSSE 同款语义：done 载荷返回；error 终态 / 断线 throw）。 */
async function tasksRunSSE(url, body, handlers) {
  let finished = false;
  let done = null;
  let errorMsg = null;
  let resp;
  try {
    resp = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch (e) { throw new Error(e.message); }
  if (!resp.body) throw new Error("服务响应无流");
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || ("请求失败（HTTP " + resp.status + "）"));
  }
  await parseSSE(resp, (type, raw) => {
    let data = {};
    try { data = JSON.parse(raw || "null") || {}; } catch { data = {}; }
    if (type === "done") { done = data; finished = true; }
    else if (type === "error") { errorMsg = data.message || "请求失败"; finished = true; }
    else if (handlers[type]) handlers[type](data);
  });
  if (errorMsg) throw new Error(errorMsg);
  if (!done) throw new Error(finished ? "服务未返回结果" : "连接中断：本次操作未完成，可安全重试");
  return done;
}

/** 拆解任务（force = 重新拆解：旧清单备档后覆盖）。 */
async function tasksPlan(force) {
  if (tasks.busy) return;
  const dir = reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在上方「上下文入口」加载当前会话或历史目录"; return; }
  if (force && !await confirmModal({
    title: "重新拆解？",
    message: "将重新生成任务清单：旧清单会备档为 .contest_tasks.json.bak，当前任务进度（含已完成状态）随旧清单一起归档。",
    confirmText: "重新拆解",
  })) return;
  tasksSetBusy(true);
  tasksResetMessages();
  $("tasks-status").textContent = "请求中…";
  try {
    const body = { output_dir: dir };
    if (scorePoints && scorePoints.length) body.score_points = scorePoints;
    if (force) body.force = true;
    const data = await tasksRunSSE("/api/tasks/plan", body, {
      task_planning: () => { $("tasks-status").textContent = "AI 拆解任务中…（分钟级调用，请等待）"; },
      llm_telemetry: (d) => {
        const tel = $("tasks-llm-telemetry");
        tel.textContent = formatLLMTelemetry(d);
        tel.classList.remove("hidden");
        recordLLMUsage(d);
      },
    });
    tasks.outputDir = dir;
    tasks.plan = data;
    tasksRender();
    markStepDone(11);
    $("tasks-status").textContent = "拆解完成——逐卡点「做这一步」，每步编译验证";
    toast("ok", force ? "已重新拆解" : "任务清单已就绪");
  } catch (e) {
    $("tasks-status").textContent = "";
    $("tasks-msg").textContent = e.message;   // 后端中文（含缺题面 / 已有清单提示）
  } finally {
    tasksSetBusy(false);
  }
}

$("btn-tasks-plan").addEventListener("click", () => tasksPlan(false));
$("btn-tasks-replan").addEventListener("click", () => tasksPlan(true));
// 任务卡「做这一步」事件委托（列随状态重渲染，监听器挂容器）
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-run");
  if (!btn) return;
  // 执行在工单 02 实现：本工单先占位提示（按钮仅在清单就绪后出现）
  $("tasks-msg").textContent = "任务执行在下一个版本开放（工单 02）——当前版本请先核对任务清单";
});
// 跨簇通知（revise 上下文入口加载后广播）：目录不同 = 旧清单与当前目录无关，
// 清空本簇状态（显示占位，等用户拆解）——revise 簇负责状态生命周期与广播时机，
// 本簇只消费事件（零模块耦合：跨簇取值走 reviseGetDir 单点已够）。
window.addEventListener("revise-context-loaded", (event) => {
  const dir = event.detail && event.detail.output_dir;
  if (dir !== tasks.outputDir) {
    tasks.outputDir = "";
    tasks.plan = null;
    $("tasks-grid").classList.add("hidden");
    $("tasks-grid").innerHTML = "";
    $("tasks-progress").textContent = "";
    $("btn-tasks-replan").classList.add("hidden");
    $("tasks-status").textContent = "";
    $("tasks-msg").textContent = "";
  }
});

export { tasksPlan, tasksRender, tasksResetMessages };
