// fx/task.js — 任务推进纯函数（工单 task-progress/01）：任务卡渲染 / 状态徽章 /
// 验收方式标注 / 进度汇总。共享件用 esc（fx/core.js）。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

export function taskStatusLabel(status) {
  switch (status) {
    case "pending": return "待做";
    case "doing": return "进行中";
    case "verified": return "已验证";
    case "unverified": return "未验证";
    case "failed": return "失败";
    case "skipped": return "已跳过";
    default: return "未知";
  }
}

export function taskStatusBadgeClass(status) {
  switch (status) {
    case "verified": return "ok";
    case "doing": return "out";
    case "failed": return "del";
    case "unverified": return "unverified";
    case "skipped": return "same";
    default: return "out";
  }
}

export function taskVerifyLabel(verify) {
  return verify === "manual" ? "需上板人工确认" : "编译验证";
}

export function taskScoreRefsText(scoreRefs, points) {
  if (!scoreRefs || !scoreRefs.length) return "";
  const byId = {};
  (points || []).forEach((p) => { if (p && p.id) byId[p.id] = p; });
  return scoreRefs.map((id) => {
    const point = byId[id];
    if (!point) return id;
    const score = (typeof point.score === "number" && Number.isFinite(point.score))
      ? " " + point.score + " 分"
      : "";
    return id + "（" + (point.part === "basic" ? "基础" : point.part === "development" ? "发挥" : "其他") + score + "）";
  }).join("、");
}

export function taskCardHTML(task, index, opts) {
  const o = opts || {};
  const badge = '<span class="badge ' + taskStatusBadgeClass(task.status) + '">'
    + taskStatusLabel(task.status) + "</span>";
  const refs = taskScoreRefsText(task.score_refs, o.scorePoints);
  const deps = (task.depends_on || []).length
    ? '<div class="muted" style="margin-top:4px">前置：' + esc(task.depends_on.join("、")) + "</div>"
    : "";
  const verifyNote = task.verify === "manual"
    ? '<span class="muted"> · ' + taskVerifyLabel(task.verify) + "</span>"
    : "";
  return '<div class="item" data-task-id="' + esc(task.id) + '">'
    + '<div class="head"><span class="slug">' + task.id + " · " + esc(task.title) + "</span>"
    + " " + badge + "</div>"
    + '<div class="reason">' + esc(task.description) + "</div>"
    + (refs ? '<div class="muted" style="margin-top:4px">评分点：' + esc(refs) + verifyNote + "</div>" : (verifyNote ? '<div class="muted" style="margin-top:4px">' + verifyNote + "</div>" : ""))
    + deps
    + (o.actions ? '<div class="row" style="margin-top:8px">' + o.actions(task, index) + "</div>" : "")
    + "</div>";
}

export function tasksGridHTML(plan, opts) {
  const p = plan || {};
  const tasks = p.tasks || [];
  if (!tasks.length) return '<div class="muted">（任务清单为空——请点「拆解任务」生成）</div>';
  return tasks.map((task, i) => taskCardHTML(task, i, opts)).join("");
}

export function tasksProgressText(plan) {
  const tasks = (plan || {}).tasks || [];
  const done = tasks.filter((t) => t.status === "verified" || t.status === "skipped").length;
  return "进度 " + done + "/" + tasks.length;
}

/** 验证状态徽章 + 摘要文案（深化 / 任务执行结果面板共用，单源防分叉——
 * 曾两处各抄一份 if/else，措辞漂移即分叉）。returns {badge, detail}：
 * badge = 内嵌 HTML 徽章；detail = 转义后的摘要文本（调用方决定布局）。 */
export function verifyStatusMarkup(data, fallbacks) {
  const compile = (data && data.compile) || {};
  const fb = fallbacks || {};
  if (data && data.status === "verified") {
    return {
      badge: '<span class="ok" style="font-weight:600">✓ 已验证（编译通过）</span>',
      detail: esc("编译通过 · exit "
        + (compile.exit_code === null || compile.exit_code === undefined ? "—" : compile.exit_code)
        + (compile.summary ? " · " + compile.summary : "")),
    };
  }
  if (data && data.status === "unverified") {
    return {
      badge: '<span style="color:var(--warn);font-weight:600">⚠ 未验证（无工具链降级）</span>',
      detail: esc((data && data.message) || fb.unverified
        || "未检测到编译工具链：结果已写入 main.c，但未经编译验证——请配置工具链后手动编译（上板类任务可直接人工标记为已验证）。"),
    };
  }
  return {
    badge: '<span style="color:var(--danger);font-weight:600">✗ 未通过（编译验证失败）</span>',
    detail: esc((data && data.message) || fb.failed
      || "编译验证未通过，结果已写入 main.c（已备份，可回滚）。"),
  };
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    taskStatusLabel, taskStatusBadgeClass, taskVerifyLabel,
    taskScoreRefsText, taskCardHTML, tasksGridHTML, tasksProgressText,
    verifyStatusMarkup,
  });
}
