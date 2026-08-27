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
    + taskIterationsHTML(task)
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

/** 任务卡操作显隐（单源，与后端 ALLOWED_STATUS_TRANSITIONS 镜像）：
 * 返回该状态下应显示的操作键（run = 做这一步；skip = 跳过；revert = 重做 /
 * 恢复；mark = 上板已验证）。doing = 无操作（执行中，退出终态由执行回填）。 */
export function taskCardActions(status) {
  switch (status) {
    case "pending": return ["run", "skip"];
    case "skipped": return ["revert"];
    case "verified": return ["revert"];
    case "unverified":
    case "failed": return ["run", "mark", "revert"];
    default: return [];
  }
}

/** 上板反馈按钮显隐（工单 task-feedback/03，单源）：非 doing 且已有可观察
 * 产物（执行过至少一轮 = 有迭代记录）或已是终态（unverified / failed /
 * verified——旧清单无迭代记录的终态任务也允许反馈）。从未执行且待做 →
 * 无上板对象，不显示。 */
export function taskCanFeedback(task) {
  if (!task || task.status === "doing") return false;
  const hasRun = (task.iterations || []).length > 0;
  const isTerminal = ["unverified", "failed", "verified"].includes(task.status);
  return hasRun || isTerminal;
}

/** 轮次种类标签（初始执行 / 上板反馈）。 */
export function taskIterationLabel(kind) {
  return kind === "execute" ? "初始执行"
    : kind === "feedback" ? "上板反馈" : "执行";
}

/** 轮次历史展开区（工单 task-feedback/03）：空历史 = 空串（不渲染）。
 * 每轮一行：轮次号 + 种类 + 反馈摘要（截断 40 字）+ 该轮终态徽章 +
 * 编译结果徽章（compile_summary，截断 40 字；颜色按该轮终态推断——
 * verified=绿 / failed=红 / 其余灰）+ 时间（at）+ 备份 + 「回到这轮之前」
 * 按钮（撤销语义——备份 = 该轮执行前快照，恢复后状态回该轮前终态）。
 * 无备份的轮次不给按钮（防御）。 */
export function taskIterationsHTML(task) {
  const iterations = (task && task.iterations) || [];
  if (!iterations.length) return "";
  const rows = iterations.map((it) => {
    const feedback = it.feedback
      ? '<span class="muted">「' + esc(it.feedback.length > 40
        ? it.feedback.slice(0, 40) + "…" : it.feedback) + "」</span> "
      : "";
    const compile = it.compile_summary
      ? ' <span class="badge ' + iterationCompileBadgeClass(it.status) + '">编译：'
        + esc(it.compile_summary.length > 40
          ? it.compile_summary.slice(0, 40) + "…" : it.compile_summary)
        + "</span>"
      : "";
    const at = it.at ? ' <span class="muted">' + esc(String(it.at)) + "</span>" : "";
    const rollback = it.backup_id
      ? '<button class="btn-task-iteration-rollback" data-task="' + esc(task.id || "")
        + '" data-seq="' + esc(String(it.seq)) + '">回到这轮之前</button>'
      : "";
    return '<div class="reason" style="margin-top:4px">第 ' + esc(String(it.seq))
      + " 轮 · " + esc(taskIterationLabel(it.kind)) + " " + feedback
      + '<span class="badge ' + taskStatusBadgeClass(it.status || "pending") + '">'
      + taskStatusLabel(it.status || "pending") + "</span>"
      + compile + at
      + (it.backup_id ? ' 备份 <span class="slug">' + esc(String(it.backup_id)) + "</span>" : "")
      + " " + rollback + "</div>";
  }).join("");
  return '<div class="muted" style="margin-top:8px">历史记录（共 ' + esc(String(iterations.length))
    + " 轮）</div>" + rows;
}

/** 编译结果徽章颜色：按该轮终态推断（verifyStatusMarkup 同判据——
 * verified=编译绿、failed=红、unverified=灰、其余灰）。 */
function iterationCompileBadgeClass(status) {
  switch (status) {
    case "verified": return "ok";
    case "failed": return "del";
    default: return "out";
  }
}

/** 结果面板「上板反馈」原文回溯（评审整改：Feature Envy——胶水层不再拼
 * HTML，纯函数单源）：最近一轮是上板反馈且有原文 → 返回展示 HTML（转义），
 * 否则空串。 */
export function taskLatestFeedbackNote(task) {
  const iterations = (task && task.iterations) || [];
  const last = iterations.length ? iterations[iterations.length - 1] : null;
  if (!last || last.kind !== "feedback" || !last.feedback) return "";
  return '<div class="reason">上板反馈：<span class="slug">'
    + esc(String(last.feedback)) + "</span></div>";
}

/** 验证状态徽章 + 摘要文案（深化 / 任务执行结果面板共用，单源防分叉——
 * 曾两处各抄一份 if/else，措辞漂移即分叉）。returns {badge, detail}：
 * badge = 内嵌 HTML 徽章；detail = 转义后的摘要文本（调用方决定布局）。
 * unverified 有两种成因（cause）：无工具链降级（默认文案「无工具链降级」）
 * 与手动验收待确认（verify_cause = manual，后端下发——编译绿但需上板观察），
 * 徽章必须按 cause 区分，不能只按 status（工单 03 评审发现）。 */
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
    const manual = data.verify_cause === "manual";
    return {
      badge: manual
        ? '<span style="color:var(--warn);font-weight:600">⚠ 未验证（上板确认）</span>'
        : '<span style="color:var(--warn);font-weight:600">⚠ 未验证（无工具链降级）</span>',
      detail: esc((data && data.message) || (manual ? fb.manual
        : fb.unverified)
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
    verifyStatusMarkup, taskCanFeedback, taskIterationLabel,
    taskIterationsHTML, taskLatestFeedbackNote,
  });
}
