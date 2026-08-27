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
import { taskCanFeedback, taskCardActions, tasksGridHTML, tasksProgressText, verifyStatusMarkup, taskLatestFeedbackNote } from "/js/fx/task.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { markStepDone } from "/js/ui/step-state.js";
import { scorePoints } from "./generate-recommend.js";  // 当前会话推荐评分点（历史目录为空）
import { reviseGetDir, reviseRenderDeepenDiff } from "./generate-revise.js";  // 已加载上下文（只读）+ diff 渲染器复用

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
  // 结果面板随渲染清除（每次执行/拆解后重建，防陈旧结果残留）
  const stale = $("tasks-result");
  if (stale) stale.remove();
  if (!plan || !(plan.tasks || []).length) {
    grid.classList.add("hidden");
    grid.innerHTML = "";
  } else {
    grid.innerHTML = tasksGridHTML(plan, {
      scorePoints: scorePoints,
      actions: (task) => {
        // 操作显隐单源 = fx/task.js taskCardActions（与后端转移表镜像，
        // 同一状态机一份 JS 编码——曾内联 if/else 与转移表分叉风险）
        const actions = taskCardActions(task.status);
        const parts = [];
        if (actions.includes("run")) {
          parts.push('<input type="text" id="task-note-' + esc(task.id)
            + '" placeholder="补充说明（可选）…" style="flex:1">'
            + '<button class="btn-task-run" data-task="' + esc(task.id) + '">做这一步</button>');
        }
        if (actions.includes("skip")) {
          parts.push('<button class="btn-task-skip" data-task="' + esc(task.id) + '">跳过</button>');
        }
        if (actions.includes("revert")) {
          parts.push('<button class="btn-task-revert" data-task="' + esc(task.id) + '">'
            + (task.status === "skipped" ? "恢复" : "重做") + "</button>");
        }
        if (actions.includes("mark")) {
          parts.push('<button class="btn-task-mark" data-task="' + esc(task.id) + '">确认通过</button>');
        }
        if (taskCanFeedback(task)) {
          parts.push('<button class="btn-task-feedback" data-task="' + esc(task.id) + '">上板反馈</button>'
            + '<div id="task-feedback-' + esc(task.id) + '" class="hidden" style="width:100%">'
            + '<textarea placeholder="描述上板实测现象（如：左轮不转 / 不沿线向右偏 / 灰度读不到）…" style="width:100%;min-height:56px"></textarea>'
            + '<button class="btn-task-feedback-send" data-task="' + esc(task.id) + '">按反馈修复</button>'
            + "</div>");
        }
        return parts.join("");
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
    // 兜底：报错引导「重新拆解」时按钮必须可见（计划外路径——目录加载自动
    // plan-read 失败 / 漏发事件——也不让用户死锁在一条必错的提示前）
    if (e.message && e.message.includes("已有任务清单")) {
      $("btn-tasks-replan").classList.remove("hidden");
    }
  } finally {
    tasksSetBusy(false);
  }
}

/** 单任务执行（工单 02 + task-feedback/02）：读补充框 → SSE（feedback 非空 =
 * 上板反馈轮）→ 状态回填渲染 + 结果面板。 */
async function tasksExecute(taskId, feedback) {
  if (tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在上方「上下文入口」加载当前会话或历史目录"; return; }
  const note = ($("task-note-" + taskId) || {}).value || "";
  tasksSetBusy(true);
  tasksResetMessages();
  $("tasks-status").textContent = "执行中…";
  try {
    const body = { output_dir: dir, task_id: taskId, note: note };
    if (feedback) body.feedback = feedback;
    const data = await tasksRunSSE("/api/tasks/execute", body, {
      task_executing: () => { $("tasks-status").textContent = "AI 实现本任务中…（分钟级调用，请等待）"; },
      compile_start: () => { $("tasks-status").textContent = "编译中…"; },
      fix_start: () => { $("tasks-status").textContent = "AI 修复中…（首轮编译未过，自动修复一轮）"; },
      verify_result: () => { $("tasks-status").textContent = "验证结果收集中…"; },
      llm_telemetry: (d) => {
        const tel = $("tasks-llm-telemetry");
        tel.textContent = formatLLMTelemetry(d);
        tel.classList.remove("hidden");
        recordLLMUsage(d);
      },
    });
    // 状态回填：done 载荷的 task 是最新形状，替换清单里对应任务再重渲染
    if (tasks.plan && tasks.plan.tasks) {
      tasks.plan.tasks = tasks.plan.tasks.map((t) => t.id === taskId ? data.task : t);
    }
    tasksRender();
    tasksRenderResult(taskId, data);
    if (data.status !== "failed") { markStepDone(11); }
    toast("ok", feedback ? "已按反馈修复" : "任务已完成");
    $("tasks-status").textContent = data.status === "failed"
      ? "任务失败（修复一轮后仍红）——可回滚或重试"
      : feedback
        ? "已按反馈修复——请再次上板验证，或确认通过进入下一卡"
        : "任务完成——继续下一卡或人工改标";
  } catch (e) {
    $("tasks-status").textContent = "";
    $("tasks-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
  }
}

/** 任务执行结果面板（照深化结果卡先例）：状态徽章 + 编译摘要 + diff + 备份 +
 * 回滚按钮（复用 /api/revise/rollback，同备份族——backup_tree 同盘）。
 * 徽章 + 摘要文案单源 = fx/task.js verifyStatusMarkup（与深化面板共用）。 */
function tasksRenderResult(taskId, data) {
  const markup = verifyStatusMarkup(data, {
    unverified: "未检测到编译工具链：任务结果已写入 main.c，但未经编译验证——请配置工具链后手动编译，或上板后人工标记为已验证。",
    failed: "编译验证未通过，任务结果已写入 main.c（已备份，可回滚）。",
  });
  const task = data.task || {};
  const backupId = data.backup_id || "";
  // 反馈轮提示：最近一轮若是上板反馈，把用户反馈原文展示在结果面板（追溯）
  // ——纯函数单源 fx/task.js taskLatestFeedbackNote（评审整改：胶水层不拼 HTML）
  const feedbackNote = taskLatestFeedbackNote(task);
  $("tasks-grid").insertAdjacentHTML("afterend",
    '<div class="item" id="tasks-result" style="margin-top:10px">'
    + '<div class="head"><span class="slug">' + esc(task.id || taskId) + " · " + esc(task.title || "") + " 执行结果</span> " + markup.badge + "</div>"
    + feedbackNote
    + '<div class="reason">' + markup.detail + "</div>"
    + '<div class="reason">备份：<span class="slug">' + esc(backupId || "—") + "</span>"
    + (backupId ? ' · <button class="btn-task-rollback danger" data-backup="' + esc(backupId) + '" data-task="' + esc(task.id || taskId) + '">回滚到本任务执行前</button>' : "")
    + "</div>"
    + reviseRenderDeepenDiff(data.main_diff, "任务")
    + "</div>");
}

/** 回滚到本任务执行前：复用 /api/revise/rollback（同备份族）→ 重读清单刷新。 */
async function tasksRollback(backupId, taskId) {
  if (tasks.busy) return;
  if (!await confirmModal({
    title: "确认回滚？",
    message: "将把输出目录整体恢复到该任务执行前的状态（含 main.c 与其余文件），本任务的改动全部撤销；已完成的其他任务不受影响（其改动已在各自备份与后续写盘中）。",
    danger: true,
    confirmText: "确认回滚",
  })) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在上方「上下文入口」加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-status").textContent = "回滚中…";
  try {
    await apiPost("/api/revise/rollback", { output_dir: dir, backup_id: backupId });
    // 回滚后重读清单（磁盘态 = 执行前：该任务状态回落 previous）
    await tasksReload();
    toast("ok", "已回滚到本任务执行前");
  } catch (e) {
    $("tasks-status").textContent = "";
    $("tasks-msg").textContent = "回滚失败：" + e.message;
  } finally {
    tasksSetBusy(false);
  }
}

/** 重读磁盘任务清单（回滚后 / 跨入口刷新 / 目录加载自动读回）：磁盘态即
 * 真相，内存态只作缓存。成功时绑定 tasks.outputDir（后续执行/回滚的目录
 * 权威来源；失败静默——清单损坏留待下一次操作提示）。 */
async function tasksReload() {
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) return;
  try {
    const data = await apiPost("/api/tasks/plan-read", { output_dir: dir });
    tasks.outputDir = dir;
    tasks.plan = data.plan || null;
    tasksRender();
  } catch (e) {
    // 读取失败（清单损坏 / 目录没了）：不清空旧展示，错误留给下一次操作提示
  }
}

/** 人工改标（工单 03）：跳过 / 恢复 / 重做 / 上板改标 → 落盘 + 单卡重渲染。 */
async function tasksSetStatus(taskId, status) {
  if (tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在上方「上下文入口」加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-msg").textContent = "";
  try {
    const data = await apiPost("/api/tasks/status", {
      output_dir: dir, task_id: taskId, status: status,
    });
    if (tasks.plan && tasks.plan.tasks) {
      tasks.plan.tasks = tasks.plan.tasks.map((t) => t.id === taskId ? data.task : t);
    }
    tasksRender();
    toast("ok", "状态已更新");
  } catch (e) {
    $("tasks-msg").textContent = e.message;   // 后端中文（含非法转移提示）
  } finally {
    tasksSetBusy(false);
  }
}

/** 上板反馈（工单 task-feedback/03）：展开反馈输入区（每卡一个 textarea，
 * 状态不落内存态——存在即展开，重渲染自然收起）。 */
function tasksFeedbackToggle(taskId) {
  const box = $("task-feedback-" + taskId);
  if (box) box.classList.toggle("hidden");
}

async function tasksFeedbackSend(taskId) {
  const box = $("task-feedback-" + taskId);
  if (!box) return;
  const textarea = box.querySelector("textarea");
  const feedback = (textarea && textarea.value || "").trim();
  if (!feedback) { $("tasks-msg").textContent = "请先描述上板实测现象（如「左轮不转」「灰度读不到」）"; return; }
  box.classList.add("hidden");
  await tasksExecute(taskId, feedback);
}

/** 回滚到指定轮次之前（工单 task-feedback/03）：撤销语义——代码恢复为该轮
 * 执行前快照、状态回该轮前终态；历史留痕保留。 */
async function tasksRollbackIteration(taskId, seq) {
  if (tasks.busy) return;
  if (!await confirmModal({
    title: "回到第 " + seq + " 轮之前？",
    message: "将撤销第 " + seq + " 轮（及其后所有轮次）的修改：代码恢复到该轮执行前，任务状态回到该轮之前。操作可再重做/反馈造出新轮次。",
    danger: true,
    confirmText: "确认回滚",
  })) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在上方「上下文入口」加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-status").textContent = "回滚中…";
  try {
    const data = await apiPost("/api/tasks/rollback-iteration", {
      output_dir: dir, task_id: taskId, seq: seq,
    });
    tasks.plan = data.plan || tasks.plan;
    tasksRender();
    toast("ok", "已回到第 " + seq + " 轮之前");
  } catch (e) {
    $("tasks-status").textContent = "";
    $("tasks-msg").textContent = "回滚失败：" + e.message;
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
  tasksExecute(btn.dataset.task, "");
});
// 上板反馈：展开输入区 / 发送反馈（工单 task-feedback/03）
$("tasks-grid").addEventListener("click", (event) => {
  const toggle = event.target.closest(".btn-task-feedback");
  if (toggle) { tasksFeedbackToggle(toggle.dataset.task); return; }
  const send = event.target.closest(".btn-task-feedback-send");
  if (send) tasksFeedbackSend(send.dataset.task);
});
// 任务卡状态按钮（跳过 / 恢复 / 重做 / 上板改标）
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-skip, .btn-task-revert, .btn-task-mark");
  if (!btn) return;
  const status = btn.classList.contains("btn-task-skip") ? "skipped"
    : btn.classList.contains("btn-task-mark") ? "verified" : "pending";
  tasksSetStatus(btn.dataset.task, status);
});
// 结果面板「回滚到本任务执行前」（同备份族，复用 /api/revise/rollback）
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-rollback");
  if (!btn) return;
  tasksRollback(btn.dataset.backup, btn.dataset.task);
});
// 轮次历史「回到这轮之前」（工单 task-feedback/03：撤销语义）
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-iteration-rollback");
  if (!btn) return;
  tasksRollbackIteration(btn.dataset.task, btn.dataset.seq);
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
    // 目录已加载：自动读回磁盘任务清单（若该目录拆解过）——任务卡与
    // 「重新拆解」按钮随之出现；无清单则保持占位等用户拆解。修复「提示
    // 已有清单却看不到重新拆解按钮」的死锁：此前只有 plan 已加载才显示
    // 按钮，而加载目录从未 plan-read，用户只能点「拆解任务」撞同样的错。
    tasksReload();
  }
});
// 修订重生成 → 任务清单已作废（后端已删除清单文件）：清空本簇缓存 + 提示
//（含陈旧结果面板——重置状态一致性，照 revise-context-loaded 同款）
window.addEventListener("tasks-invalidated", (event) => {
  const dir = event.detail && event.detail.output_dir;
  if (dir && tasks.outputDir && dir !== tasks.outputDir) return;  // 与当前目录无关：不动本簇状态
  tasks.outputDir = "";
  tasks.plan = null;
  $("tasks-grid").classList.add("hidden");
  $("tasks-grid").innerHTML = "";
  const stale = $("tasks-result");
  if (stale) stale.remove();
  $("tasks-progress").textContent = "";
  $("btn-tasks-replan").classList.add("hidden");
  $("tasks-status").textContent = "";
  $("tasks-msg").textContent = "任务清单已作废（修订重生成）：请点「拆解任务」按新工程重新拆解";
});

export { tasksPlan, tasksRender, tasksResetMessages };
