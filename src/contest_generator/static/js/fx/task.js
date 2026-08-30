// fx/task.js — 任务推进纯函数（工单 task-progress/01）：任务卡渲染 / 状态徽章 /
// 验收方式标注 / 进度汇总。共享件用 esc（fx/core.js）。模块约定见 fx/core.js 头部。
import { esc, truncate } from "./core.js";
import { isMainCPath } from "./code.js";  // 错误行跳转可点判定（error-jump-task/02；code.js 无环）
import { flashPanelHTML } from "./flash.js";  // 任务卡烧录控制行（flash-step-button/01；flash.js 仅依赖 core.js，无环）
import { wiringDiagramHTML, wiringFromResources } from "./wiring.js";  // 接线图（task-wiring-diagram/03+05；wiring.js 仅依赖 core.js，无环）
import { mainDiffHTML } from "./diff.js";  // 任务「本轮变化」diff（task-changes-inline/01；diff.js 仅依赖 core.js，无环）

export function taskStatusLabel(status, verify) {
  switch (status) {
    case "pending": return "待做";
    case "doing": return "进行中";
    case "verified":
      // 工单 ux-walkthrough-02/18：任务状态「已验证」改人话——按验证方式分
      // 口径：manual = 上板实测通过 →「上板通过」；compile = 编译绿即
      // verified（从未上板）→「编译通过」（评审整改：防止过度声明）
      return verify === "manual" ? "上板通过" : "编译通过";
    case "unverified": return "待上板";   // 契约：任务=上板通过/待上板（工单 ux-walkthrough-02/18）
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
    return id + "（" + scorePartLabel(point.part) + score + "）";
  }).join("、");
}

/** 任务序号标签（工单 task-chat/03）：index = 清单内序号（0 起）→ 「第 N 步
 * （建议顺序）」。仅展示层换算——id / depends_on 不变（建议顺序 = LLM 拆解
 * 输出顺序，用户拍板不做手动重排；序号是建议不是强制，网格顶部有声明行；
 * 「（建议顺序）」是 spec 指定用户可见文案，不能只给序号）。 */
export function taskOrderLabel(index) {
  return "第 " + (Number(index) + 1) + " 步（建议顺序）";
}

/** 建议重做徽章（工单 idea-fix/02）：task.needs_redo 为真 → 卡头「⚠ 建议
 * 重做」；否则空串（未标记不渲染）。needs_redo 由后端灵活修正落地后写在
 * 受影响的既有任务上（._contest_tasks.json 字段，旧清单缺省 false）。 */
export function taskNeedsRedoBadge(task) {
  if (!task || !task.needs_redo) return "";
  return ' <span class="badge task-redo-badge">⚠ 建议重做</span>';
}

/** 想法分类标签（工单 idea-fix/02）：三档中文短词（与后端 IDEA_KINDS 词表
 * 镜像）。 */
function ideaKindLabel(kind) {
  switch (kind) {
    case "new_task": return "新功能任务";
    case "direct_fix": return "改现有代码";
    case "discussion": return "先讨论";
    default: return "未分类";
  }
}

/** 想法分类徽章色：新功能 = 绿（有明确产物）；改代码 = 黄（警告语义——
 * 直接改现有实现需谨慎）；讨论 = 灰。 */
function ideaKindBadgeClass(kind) {
  switch (kind) {
    case "new_task": return "ok";
    case "direct_fix": return "unverified";
    default: return "out";
  }
}

/** 想法分析结果卡（工单 idea-fix/02）：分类徽章 + AI 理解 + 按 kind 渲染落地
 * 按钮区（纯函数，无 DOM——胶水层负责取样式/定位）。
 *
 * analysis = {kind, reply, new_task, fix_summary, affected_task_ids}（后端
 * /api/tasks/idea/analyze 的 done 载荷）；opts.landedNote = 非空时按钮区替换
 * 为一条中性提示（插入/修正落地后防止重复点击造重复产物——功能已消费）。
 * 按钮 data-idea-kind 供网格委托分类；new_task 预览 = 建议任务标题/描述/依赖
 * 序号；direct_fix = 修正建议 + 受影响任务；discussion = 两个转换按钮（漏斗
 * 态：把 AI 建议重新成形为可落地动作）。全部文本经 esc 防注入。 */
export function ideaResultHTML(analysis, opts) {
  const a = analysis || {};
  const kind = ["new_task", "direct_fix", "discussion"].includes(a.kind)
    ? a.kind : "discussion";
  const o = opts || {};
  let html = '<div class="item idea-result" style="margin-top: var(--space-2)">'
    + '<div class="head"><span class="slug">💡 想法分析</span> '
    + '<span class="badge ' + ideaKindBadgeClass(kind) + '">' + ideaKindLabel(kind)
    + "</span></div>"
    // 故事 6「输入想法文本保留展示」：原文回显在结果卡（会话内；落盘以
    // .contest_tasks.json 为准——想法本身不落盘）
    + (o.idea ? '<div class="reason muted">你的想法：<span class="slug">' + esc(String(o.idea)) + "</span></div>" : "")
    + '<div class="reason">' + esc(a.reply || "") + "</div>";
  if (kind === "new_task") {
    const nt = a.new_task || {};
    const deps = (nt.depends_on || []).length
      ? " · 依赖：第 " + esc(nt.depends_on.join("、")) + " 步" : "";
    html += '<div class="reason muted">建议新任务：' + esc(nt.title || "（未给出标题）")
      + deps + "——" + esc(nt.description || "") + "</div>";
  } else if (kind === "direct_fix") {
    if (a.fix_summary) {
      html += '<div class="reason muted">修正建议：' + esc(String(a.fix_summary)) + "</div>";
    }
    if ((a.affected_task_ids || []).length) {
      html += '<div class="reason muted">受影响任务（落地后建议重做）：'
        + esc(a.affected_task_ids.map((id) => seqRef(id, o.seqById)).join("、")) + "</div>";
    }
  } else {
    html += '<div class="reason muted">这是先讨论的建议——可以继续补充想法，'
      + "或把 AI 的建议直接落地：</div>";
  }
  if (o.landedNote) {
    html += '<div class="reason muted" style="margin-top: var(--space-2)">' + esc(String(o.landedNote)) + "</div>";
  } else {
    const buttons = kind === "new_task"
      ? ideaActionButtonHTML("btn-idea-insert", "生成任务", kind)
      : kind === "direct_fix"
        ? ideaActionButtonHTML("btn-idea-fix", "改动预览并执行", kind)
        : ideaActionButtonHTML("btn-idea-to-task", "把建议变成任务", kind)
          + ideaActionButtonHTML("btn-idea-to-fix", "把建议变成修正", kind);
    html += '<div class="row" style="margin-top: var(--space-2)">' + buttons + "</div>";
  }
  return html + "</div>";
}

/** 想法结果卡的落地按钮（data-idea-kind 供委托分类；落地后由胶水层
 * re-render 换 landedNote）。 */
function ideaActionButtonHTML(cls, label, kind) {
  return '<button class="' + cls + '" data-idea-kind="' + esc(kind) + '">'
    + esc(label) + "</button>";
}

/** 下一步待执行任务（工单 step-next-guide/01）：清单顺序上当前卡**之后**第一个
 * status ∈ {pending, failed} 的任务——「做完一步 → 该点哪张卡」的引导口径。
 * verified（编译绿闭环）/ unverified（待上板）/ doing（执行中）/ skipped（已跳过）
 * 不算可执行；找不到 → null（调用方不提示不滚动）。纯函数，无 DOM。 */
export function nextTaskHint(plan, currentId) {
  const tasks = (plan || {}).tasks || [];
  if (!currentId) return null;
  const start = tasks.findIndex((t) => t && t.id === currentId);
  if (start < 0) return null;
  for (let i = start + 1; i < tasks.length; i++) {
    const t = tasks[i];
    if (t && (t.status === "pending" || t.status === "failed")) {
      return { id: t.id, orderIndex: i, title: t.title || "" };
    }
  }
  return null;
}

/** 当前卡内的「下一步 → 第 N 步：标题」提示行（工单 step-next-guide/01）：
 * 纯 HTML 串（title 经 esc 防注入；序号人话化，工单 beginner-gap-closure/03）；
 * 无下一步 → 空串（调用方不渲染）。 */
export function taskNextHintHTML(plan, currentId) {
  const next = nextTaskHint(plan, currentId);
  if (!next) return "";
  return '<div class="task-next-hint">下一步 → 第 ' + esc(String((next.orderIndex ?? 0) + 1))
    + " 步：" + esc(next.title) + "</div>";
}

/** 未完成的前置任务（工单 prereq-soft-guide/01，温和引导）：任务 depends_on
 * 中状态不在 {verified, skipped} 的前置（skipped = 用户已主动放弃，不再阻断
 * ——否则跳过前置会造成依赖死锁）；返回 [{id, title, status}]，无依赖 / 无
 * plan / 前置 id 在清单中找不到 / 全部完成 = 空数组；status 缺省按 pending。 */
export function unresolvedPrereqs(task, plan) {
  const deps = (task && task.depends_on) || [];
  if (!deps.length || !plan || !plan.tasks) return [];
  const byId = new Map(plan.tasks.map((t) => [t && t.id, t]));
  const out = [];
  for (const id of deps) {
    const dep = byId.get(id);
    if (!dep) continue;
    const status = dep.status || "pending";
    if (status !== "verified" && status !== "skipped") {
      out.push({ id, title: dep.title || "", status });
    }
  }
  return out;
}

export function taskCardHTML(task, index, opts) {
  const o = opts || {};
  const badge = '<span class="badge ' + taskStatusBadgeClass(task.status) + '">'
    + taskStatusLabel(task.status, task.verify) + "</span>"
    // 待上板标注（工单 stepwise-deepen/02，spec「在总览与卡片上明确标注
    // 待上板」）：unverified = 结果已写入但未经编译验证 / 或需上板人工确认，
    // 下一步物理动作 = 上板（烧录观察）→ 卡上明示，与总览口径一致
    + (task.status === "unverified" ? ' <span class="badge unverified">待上板</span>' : "")
    // 建议重做徽章（工单 idea-fix/02）：灵活修正落地后受影响任务标记
    + taskNeedsRedoBadge(task);
  const refs = taskScoreRefsText(task.score_refs, o.scorePoints);
  // 元信息行（工单 task-card-polish/01）：资源 / 需上板 / 评分点 / 前置合并为
  // 一行紧凑 chips（原先各占一条 muted 行，层级弱）；文案与顺序：资源 →
  // 需上板 → 评分点 → 前置；全空 = 空串（不渲染）
  const metaItems = [];
  const resChips = taskResourceChipsHTML(task);
  if (resChips) metaItems.push('<span class="task-meta-item">资源：' + resChips + "</span>");
  if (task.verify === "manual") {
    metaItems.push('<span class="task-meta-item task-meta-warn">'
      + esc(taskVerifyLabel(task.verify)) + "</span>");
  }
  if (refs) metaItems.push('<span class="task-meta-item">评分点：' + esc(refs) + "</span>");
  if ((task.depends_on || []).length) {
    // 温和引导（工单 prereq-soft-guide/01）：前置未完成 → 警告色 + 悬停提示
    //（文案不变；警告只做视觉标记，不阻断）
    const pend = unresolvedPrereqs(task, o.plan);
    const warnCls = pend.length ? " task-meta-warn" : "";
    const title = pend.length
      ? ' title="前置未完成：' + esc(pend.map((p) => seqRef(p.id, o.seqById)).join("、")) + '"'
      : "";
    metaItems.push('<span class="task-meta-item' + warnCls + '"' + title + '>前置：'
      + esc(task.depends_on.map((d) => seqRef(d, o.seqById)).join("、")) + "</span>");
  }
  const meta = metaItems.length ? '<div class="task-meta">' + metaItems.join("") + "</div>" : "";
  return '<div class="item task-card" data-task-id="' + esc(task.id) + '">'
    + '<div class="head"><span class="slug">' + taskOrderLabel(index)
    + " · " + esc(task.title) + "</span>"
    + " " + badge + "</div>"
    + '<div class="reason">' + esc(task.description) + "</div>"
    + meta
    + taskIterationsHTML(task)
    // 本轮变化槽位（工单 task-changes-inline/01）：执行结果卡内注入位——胶水层
    // 在任务执行完成后把「本轮变化」区插入锚点之后；无注入 = 零占位（空 span）。
    + '<span class="task-changes-anchor" data-changes-anchor></span>'
    + taskDialogAdoptHTML(task)
    // 执行中阶段槽（工单 ux-polish-02/06）：doing 态渲染 spinner + 阶段文案，
    // 胶水层随 SSE 事件就地更新（面板顶部状态行保留为汇总）
    + (task.status === "doing" ? taskPhaseHTML(task.id, "执行中…") : "")
    + taskNextActionHTML(task, o)
    // 上板自检清单常驻（工单 task-insight/02，spec 轴评审整改：结果面板只在
    // 执行时渲染一次，刷新后不重建——勾选态 localStorage 无处回显 = 故事 3
    // 「刷新勾选仍在」只写不可读。任务卡随 tasksRender 每次重建，最新轮
    // checklist 常驻卡上（结果面板副本并存），刷新后勾选立即回显）。
    // checklistState 由胶水层提供（读 localStorage 纯函数桥，fx 无副作用）。
    + taskCardChecklistHTML(task, o)
    // 微编辑 + 调序（工单 idea-suite/04，收编为「⋯ 更多」下拉）：低频微调
    // 收进小字 details 菜单（编辑任务信息 / 上移 / 下移）+ 编辑态表单
    // （opts.editing(task.id) 为真 = 胶水层已展开该卡编辑表单）
    + '<div class="row" style="margin-top: var(--space-2);gap:6px">'
    + taskMoreMenuHTML(task, index, Number(o.total) || 0, !!(o.editing && o.editing(task.id)))
    + "</div>"
    + (o.editing && o.editing(task.id) ? taskEditFormHTML(task, o) : "")
    // 任务卡烧录控制行（工单 flash-step-button/01）：已实现过的步骤（有迭代
    // 记录或已终态 = taskCanFeedback 判据）常驻「烧录到板子」——做完一步直接
    // 在卡上烧录上板检测；pending/skipped/doing 不显示（防烧旧固件 / 防并发）。
    // 卡内独立容器（uid = task.id），与执行结果面板的烧录行（uid = "result"）并存。
    // task.id 假值不渲染（评审整改：裸 id 传空 → flashContainer 缺省降成
    // "result" 撞结果面板容器；真实 id 由后端生成非空，此处防御）
    + (o.outputDir && task.id && taskCanFeedback(task) ? flashPanelHTML(o.outputDir, task.id) : "")
    + (o.actions ? '<div class="row" style="margin-top: var(--space-2)">' + o.actions(task, index) + "</div>" : "")
    + "</div>";
}

export function tasksGridHTML(plan, opts) {
  const p = plan || {};
  const tasks = p.tasks || [];
  if (!tasks.length) return '<div class="muted">（任务清单为空——请点「拆解任务」生成）</div>';
  // 建议顺序声明（工单 task-chat/03）：序号是 AI 按方便实现顺序排的建议，
  // 不强制——用户可跳着做（depends_on 只作展示，后端无强制闸）
  const seqById = {};
  tasks.forEach((t, i) => { if (t && t.id) seqById[t.id] = i + 1; });
  return '<div class="muted" style="margin-bottom:6px">'
    + "建议按序号从上往下做（AI 按方便实现的顺序排）——不强制，可跳着做</div>"
    + tasks.map((task, i) => taskCardHTML(task, i, {
      ...(opts || {}),
      seqById,           // 编辑表单依赖回填（工单 idea-suite/04）
      total: tasks.length,
      plan: p,           // 前置温和引导（工单 prereq-soft-guide/01）
    })).join("");
}

/** 已完成任务数（口径：verified 编译绿 + skipped 已跳过）——进度文本 /
 * 第11步页签徽章 / 总览同源计数，改口径只改这一处（step11-tabs-ui/02 评审整改）。 */
export function tasksDoneCount(plan) {
  const tasks = (plan || {}).tasks || [];
  return tasks.filter((t) => t.status === "verified" || t.status === "skipped").length;
}

export function tasksProgressText(plan) {
  const tasks = (plan || {}).tasks || [];
  return "进度 " + tasksDoneCount(plan) + "/" + tasks.length;
}

/** 进度总览（工单 stepwise-deepen/02）：分段进度条 + 汇总文案。
 * 口径（spec）：已完成 = verified（编译绿）；「待上板」= unverified（含无
 * 工具链降级与 manual 人工确认两种原因）；「已跳过」单列不计入完成；
 * 进行中 = doing；失败 = failed；待做 = pending。空清单 = 空串（容器隐藏）。 */
export function tasksOverviewHTML(plan) {
  const tasks = (plan || {}).tasks || [];
  const total = tasks.length;
  if (!total) return "";
  const count = (s) => tasks.filter((t) => t.status === s).length;
  const verified = count("verified");
  const doing = count("doing");
  const unverified = count("unverified");
  const failed = count("failed");
  const pending = count("pending");
  const skipped = count("skipped");
  const seg = (n, cls, label) => n
    ? '<div class="seg ' + cls + '" style="width:' + (n / total * 100) + '%" '
      + 'title="' + esc(label) + "：" + n + '"></div>'
    : "";
  const bar = '<div class="tasks-overview-bar">'
    + seg(verified, "seg-ok", "已通过") + seg(doing, "seg-doing", "进行中")
    + seg(unverified, "seg-unverified", "待上板") + seg(failed, "seg-failed", "失败")
    + seg(pending, "seg-pending", "待做") + seg(skipped, "seg-skipped", "已跳过")
    + "</div>";
  const summary = "已完成 <b style=\"color:var(--ok-bright)\">" + verified + "</b>/" + total
    + (doing ? " · 进行中 " + doing : "")
    + (unverified ? " · 待上板 " + unverified : "")
    + (failed ? " · 失败 " + failed : "")
    + (pending ? " · 待做 " + pending : "")
    + (skipped ? " · <span class=\"muted\">已跳过 " + skipped + "（不计入完成）</span>" : "");
  // 全部完成引导（工单 ux-polish-02/06）：无 pending/failed/doing/unverified
  // = 全部任务已闭环（verified/skipped）→「去交付」按钮（切交付页签，胶水层委托）
  const allDone = !["pending", "failed", "doing", "unverified"].some(
    (s) => tasks.some((t) => t.status === s));
  const doneLine = allDone
    ? '<div class="tasks-done-line" style="margin-top: var(--space-2)"><span class="muted" style="color:var(--ok-bright)">全部完成 🎉</span>'
      + ' <button type="button" class="btn-task-goto-delivery" data-action="goto-delivery">去交付</button></div>'
    : "";
  return bar + '<div class="muted" style="margin-top: var(--space-1)">' + summary + "</div>" + doneLine;
}

/** 执行中任务卡的阶段槽（工单 ux-polish-02/06）：doing 态渲染 spinner + 阶段
 * 文案（胶水层随 SSE 事件更新 .task-phase-text）；非 doing 不渲染。 */
export function taskPhaseHTML(taskId, text) {
  return '<div class="task-phase" data-phase-task="' + esc(taskId || "") + '">'
    + '<span class="task-spinner" aria-hidden="true"></span>'
    + '<span class="task-phase-text">' + esc(text || "执行中…") + "</span></div>";
}

/** 任务卡 details 展开态快照（工单 ux-polish-02/06）：grid innerHTML 重建会
 * 复位卡上 <details>（更多菜单 / 自检清单 / 本轮变化）——渲染前快照按任务 id
 * 记录打开的 details 类名，渲染后恢复。纯函数（接收含 dataset/querySelectorAll
 * 的 DOM 类对象，与 attachCelebrate 同模式），无 DOM 全局依赖。 */
export function taskDetailsSnapshot(cards) {
  const out = {};
  for (const c of cards || []) {
    const id = c && c.dataset && c.dataset.taskId;
    if (!id) continue;
    const open = [];
    const list = c.querySelectorAll ? c.querySelectorAll("details[open]") : [];
    for (const d of list) {
      for (const cls of String(d.className || "").split(/\s+/)) {
        if (cls && cls !== "task-card" && cls.indexOf("task-") === 0) open.push(cls);
      }
    }
    if (open.length) out[id] = open;
  }
  return out;
}

/** 恢复任务卡 details 展开态：snap = taskDetailsSnapshot 输出；类名缺失/无
 * 匹配元素 = 跳过（重建后结构变化不报错）。 */
export function taskDetailsRestore(cards, snap) {
  if (!snap) return;
  for (const c of cards || []) {
    const id = c && c.dataset && c.dataset.taskId;
    const open = id && snap[id];
    if (!open || !open.length) continue;
    for (const cls of open) {
      const list = c.querySelectorAll ? c.querySelectorAll("details." + cls) : [];
      for (const d of list) d.open = true;
    }
  }
}

/** 任务卡操作显隐（单源，与后端 ALLOWED_STATUS_TRANSITIONS 镜像）：
 * 返回该状态下应显示的操作键（run = 做这一步；skip = 跳过；revert = 重做 /
 * 恢复；mark = 上板已验证；recover = 执行中断恢复为待做）。doing = 默认无
 * 操作（执行中，退出终态由执行回填）；opts.recoverable（布尔，执行中断的
 * 僵尸卡恢复入口，工单 stuck-doing-recover/01）为 true 时 doing 显示
 * recover——前端在无活跃执行（!tasks.busy）时置 true；真实执行中的拦截
 * 由后端 _running_task_execs 注册表兜底（点击被 400 拒 + 提示）。
 * failed 无 mark（工单 ux-polish-02/05）：编译仍红的卡不能「确认通过」被
 * 误标已验证——只有 unverified（待上板人工确认）才有 mark。 */
export function taskCardActions(status, opts) {
  const recoverable = (opts && opts.recoverable) || false;
  switch (status) {
    case "pending": return ["run", "skip"];
    case "skipped": return ["revert"];
    case "verified": return ["revert"];
    case "unverified": return ["run", "mark", "revert"];
    case "failed": return ["run", "revert"];
    case "doing": return recoverable ? ["recover"] : [];
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
 * 每轮两行式（工单 task-card-polish/01 视觉重构 + 用户反馈补漏）：
 * 第一行 .task-iteration-line = 轮次号 + 种类 + 该轮终态徽章 + 编译结果徽章
 * （compile_summary，截 40 字；颜色按该轮终态推断——verified=绿 /
 * failed=红 / 其余灰）+「回到这轮之前」按钮（右对齐；撤销语义——备份 =
 * 该轮执行前快照，恢复后状态回该轮前终态）；第二行 .task-iteration-detail
 * = 带标签详情（上板反馈：/ 做了什么：/ 需要你做什么：，完整原文不截断——
 * 这两条是学生核心关注内容，截断会丢信息）+ 时间 · 备份小字行。
 * 无备份的轮次不给按钮（防御）；无任何详情/时间/备份 = 不渲染第二行。 */
export function taskIterationsHTML(task) {
  const iterations = (task && task.iterations) || [];
  if (!iterations.length) return "";
  const rows = iterations.map((it) => {
    const compile = it.compile_summary
      ? '<span class="badge ' + iterationCompileBadgeClass(it.status) + '">编译：'
        + esc(truncate(it.compile_summary, 40)) + "</span>"
      : "";
    const rollback = it.backup_id
      ? '<button class="btn-mini btn-task-iteration-rollback" data-task="' + esc(task.id || "")
        + '" data-seq="' + esc(String(it.seq)) + '">回到这轮之前</button>'
      : "";
    const detail = [];
    if (it.feedback) detail.push('<div class="task-iteration-detail-row"><b>上板反馈：</b>'
      + esc(String(it.feedback)) + "</div>");
    if (it.what_changed) detail.push('<div class="task-iteration-detail-row"><b>做了什么：</b>'
      + esc(String(it.what_changed)) + "</div>");
    if (it.user_action) detail.push('<div class="task-iteration-detail-row"><b>需要你做什么：</b>'
      + esc(String(it.user_action)) + "</div>");
    const meta = [];
    if (it.at) meta.push(esc(String(it.at)));
    if (it.backup_id) meta.push("已备份");
    return '<div class="task-iteration">'
      + '<div class="task-iteration-line">'
      + '<span class="task-iteration-title">第 ' + esc(String(it.seq)) + " 轮 · "
        + esc(taskIterationLabel(it.kind)) + "</span>"
      + '<span class="badge ' + taskStatusBadgeClass(it.status || "pending") + '">'
        + taskStatusLabel(it.status || "pending", it.verify) + "</span>"
      + compile + rollback
      + "</div>"
      + (detail.length || meta.length
        ? '<div class="task-iteration-detail">' + detail.join("")
          + (meta.length
            ? '<div class="task-iteration-detail-meta muted">' + meta.join(" · ") + "</div>"
            : "")
          + "</div>"
        : "")
      + "</div>";
  }).join("");
  return '<div class="muted task-iterations-title" style="margin-top: var(--space-2)">历史记录（共 '
    + esc(String(iterations.length)) + " 轮）</div>"
    + '<div class="task-iterations">' + rows + "</div>";
}

/** 最新一轮迭代（评审整改：三处「取末轮」收敛单源）；无轮次 = null。 */
function lastIteration(task) {
  const iterations = (task && task.iterations) || [];
  return iterations.length ? iterations[iterations.length - 1] : null;
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

/** 已采纳对话结论徽标（工单 task-chat/03）：任务 dialog_note 非空 → 徽标 +
 * 摘要（截 30 字）+ 取消采纳按钮；未采纳 = 空串（不渲染）。
 * dialog_note 由「有不懂的？问这里」对话区的采纳按钮写入（/api/tasks/dialog-adopt），
 * 执行时作为独立 prompt 段注入（<-> 后端 task_progress.set_task_dialog_note）。 */
export function taskDialogAdoptHTML(task) {
  const note = task && task.dialog_note;
  if (!note || !String(note).trim()) return "";
  const text = String(note).trim();
  return '<div class="muted" style="margin-top: var(--space-1)">'
    + '<span class="badge ok">已采纳对话结论</span> '
    + esc(text.length > 30 ? text.slice(0, 30) + "…" : text)  // 摘要截 30 字 = spec「前 30 字」定数
    + ' <button class="btn-task-dialog-clear" data-task="' + esc(task.id || "") + '">取消采纳</button>'
    + "</div>";
}

/** 「有不懂的？问这里」按钮（工单 task-chat/03 + 06 文案澄清）：本步有什么
 * 没懂/想确认的，点开向 AI 询问——AI 先判断可行性再给影响与修正建议，采纳的
 * 结论会带进下一步执行。doing = 执行中不可操作（不显示）；st.open 时文案
 * 「收起讨论」。 */
export function taskDialogButtonHTML(task, st) {
  if (!task || task.status === "doing") return "";
  const open = !!(st && st.open);
  return '<button class="btn-task-dialog' + (open ? " active" : "") + '" data-task="'
    + esc(task.id || "") + '">' + (open ? "收起讨论" : "有不懂的？问这里") + "</button>";
}

/** 任务对话区（工单 task-chat/03 + 06 文案澄清）：每卡「有不懂的？问这里」的
 * 展开区。st = {open, busy, history: [{role, content}]}；未展开 = 空串。
 * 历史全量渲染（用户 / AI 逐条，转义）；每条 AI 消息下挂「采纳这条结论」
 * 按钮（data-task + data-idx——可采纳任意一轮回复，采纳哪条由用户定）；
 * 底部输入框 + 发送（busy 时禁用，防并发一轮）。样式复用 .sugg-discuss-*（
 * 买件商量讨论区同一套，0 构建，不再造新视觉）。 */
export function taskDialogAreaHTML(task, st) {
  const s = st || {};
  if (!s.open) return "";
  const taskId = (task && task.id) || "";
  const history = s.history || [];
  const lines = history.map((m, i) => {
    const isAi = m.role === "assistant";
    const roleLabel = isAi ? "AI" : "我";
    const adopt = isAi
      ? ' <button class="btn-task-dialog-adopt" data-task-adopt="' + esc(taskId)
        + '" data-task="' + esc(taskId) + '" data-idx="'
        + esc(String(i)) + '">采纳这条结论</button>'
      : "";
    return '<div class="sugg-msg ' + (isAi ? "ai" : "user") + '">'
      + '<span class="sugg-msg-role">' + roleLabel + "</span>：" + esc(String(m.content))
      + adopt + "</div>";
  }).join("");
  if (!lines) {
    return '<div class="task-dialog-box">'
      + '<div class="sugg-msg muted">这一步有不懂或想确认的地方？把你的疑问告诉 AI——它会先判断可行性，再给影响与修正建议；确认后可点「采纳这条结论」，结论会带进下一步执行。</div>'
      + '<div class="sugg-discuss-row">' + dialogInputHTML(taskId, s) + "</div></div>";
  }
  return '<div class="task-dialog-box">'
    + '<div class="sugg-discuss-msgs">' + lines + "</div>"
    + '<div class="sugg-discuss-row">' + dialogInputHTML(taskId, s) + "</div>"
    + (s.busy ? '<div class="sugg-discuss-note">AI 回应中…（分钟级调用，请等待）</div>' : "")
    + "</div>";
}

/** 对话区输入行（send 语义共享：发送按钮 + busy 禁用）。st = 对话状态
 *（draft = 输入框未发送内容——重渲染不丢；busy = 一轮 LLM 调用中禁用输入）。 */
function dialogInputHTML(taskId, st) {
  return '<input id="task-dialog-input-' + esc(taskId) + '" class="sugg-discuss-input"'
    + ' placeholder="有不懂的或想确认的？在这里问（如：这一步烧录后应该观察到什么？）…" value="' + (st.draft || "") + '">'
    + '<button class="btn-task-dialog-send" data-task="' + esc(taskId) + '"'
    + (st.busy ? " disabled" : "") + ">" + (st.busy ? "回应中…" : "发送") + "</button>";
}

/** 结果面板「上板反馈」原文回溯（评审整改：Feature Envy——胶水层不再拼
 * HTML，纯函数单源）：最近一轮是上板反馈且有原文 → 返回展示 HTML（转义），
 * 否则空串。 */
export function taskLatestFeedbackNote(task) {
  const last = lastIteration(task);
  if (!last || last.kind !== "feedback" || !last.feedback) return "";
  return '<div class="reason">上板反馈：<span class="slug">'
    + esc(String(last.feedback)) + "</span></div>";
}

/** 步骤报告两块正文（工单 stepwise-deepen/02 + idea-fix/02 共用防分叉——
 * 历史教训：两处各抄一份 if/else，措辞漂移）。changed / action 为空 → 中文
 * 兜底（报告未生成 / 本步无需人工动作）。 */
export function taskStepReportBlocksHTML(changed, action) {
  const changedBlock = changed
    ? '<div class="reason"><b>AI 做了什么：</b>' + esc(changed) + "</div>"
    : '<div class="reason muted">本步说明为空（报告未生成或 AI 未总结）——可点「重做」重新执行以生成。</div>';
  const actionBlock = action
    ? '<div class="reason"><b>接下来你要做什么：</b>' + esc(action) + "</div>"
    : '<div class="reason muted">本步无需额外人工动作——请按验证结果继续（上板确认后点「确认通过」）。</div>';
  return changedBlock + actionBlock;
}

/** 步骤报告（工单 stepwise-deepen/02 + task-insight/02）：结果面板「AI 做了
 * 什么 / 接下来你要做什么」两块 + 上板自检清单（最新轮 checklist，可勾选
 * 备忘——key / checkedMap 由胶水层传入，空 = 无 checklist 段不渲染），取自
 * 最新一轮迭代（后端工单 01 落盘；报告调用失败 = 两字段空串——降级兜底文案
 * 中文，spec「降级路径必须有兜底文案」）。无轮次 = 空串（未执行过无报告可
 * 展示）。 */
export function taskStepReportHTML(task, opts) {
  const last = lastIteration(task);
  if (!last) return "";
  const o = opts || {};
  const perTask = wiringPer(task, o);
  const wiring = wiringSectionHTML(task, o, perTask);
  return '<div class="task-step-report" style="margin-top: var(--space-2);border-top:1px dashed var(--border);padding-top:6px">'
    + '<div class="muted" style="margin-bottom:2px">步骤报告（AI 本步总结）</div>'
    + (wiring ? '<div class="task-step-wiring" data-wiring-uid="' + esc(String(perTask && perTask.wiringUid || "")) + '" style="margin-top: var(--space-2)">' + wiring + "</div>" : "")
    + taskStepReportBlocksHTML(last.what_changed || "", last.user_action || "")
    + taskChecklistHTML(last, o.checkKey || "", o.checkedMap || {})
    + "</div>";
}

/** 引脚名判据单源（resource-overview-polish/01 评审整改）：resourceIsHardware 与
 * aggregateResourceGroups 共用——/^P[A-G]\d{1,2}$/i（MSPM0 PA/PB + STM32 PA-PG 兼容）。 */
function isPinName(name) {
  return /^P[A-G]\d{1,2}$/i.test(String(name == null ? "" : name).trim());
}

/** 资源名是否硬件实体（工单 task-insight/02 评审整改）：引脚（PA0/PB12，
 * 判据单源 isPinName）、
 * 外设（TIM1/UART0/ADC0/GPIOA 等）、中断（*_IRQn）。模块名（xunji）、函数名、
 * 宏名（LED_BEEP）不是硬件——任务间复用模块是正常代码复用，不构成互斥冲突
 * 暗雷，总览里不该标黄（AI 偶将模块名填入 resources，前端兜底降噪）。
 * 词表式判定：外设白名单 = TIM|TIMA|TIMB|UART|USART|SPI|I2C|I2S|ADC|DAC|DMA|CAN|PWM|COMP|GPIO[x]，
 * 中断 = 以 _IRQn 结尾。其余（含大写宏名）一律非硬件。 */
export function resourceIsHardware(name) {
  const s = String(name == null ? "" : name).trim();
  if (!s) return false;
  if (isPinName(s)) return true;
  if (/^(TIM|TIMA|TIMB|UART|USART|SPI|I2C|I2S|ADC|DAC|DMA|CAN|PWM|COMP)[A-Z]{0,1}\d*$/i.test(s)) return true;
  if (/^GPIO[A-Z]$/i.test(s)) return true;
  if (/_IRQn$/i.test(s)) return true;
  return false;
}

/** 任务卡资源徽标行（工单 task-insight/02）：本任务占用的互斥资源（拆解时
 * AI 标注 resources——引脚/外设/中断真实名；与其它任务共用也列出）。非硬件项
 * （模块名/函数名/宏名——AI 偶发误标）以 .res-soft muted 样式降级展示：
 * 信息保留但不与硬件资源同权重刺眼。空 = 空串（旧清单无该字段 / 不新增占用）。 */
export function taskResourcesHTML(task) {
  const chips = taskResourceChipsHTML(task);
  if (!chips) return "";
  return '<div class="muted" style="margin-top: var(--space-1)">资源：' + chips + "</div>";
}

/** 任务资源 chips 串（工单 task-card-polish/01 抽取）：只产 chips 内容，
 * 供任务卡元信息行（.task-meta）与 taskResourcesHTML（既有出口）共用，
 * 空 = 空串。 */
function taskResourceChipsHTML(task) {
  const resources = (task && task.resources) || [];
  if (!resources.length) return "";
  return resources.map((r) => {
    const name = String(r);
    return '<span class="res-chip' + (resourceIsHardware(name) ? "" : " res-soft") + '">'
      + esc(name) + "</span>";
  }).join(" ");
}

/** 资源聚合单源（resource-overview-polish/01）：plan.tasks[].resources →
 * 三组聚合——pins（引脚 /^P[A-G]\d{1,2}$/i，判据单源 isPinName）、other（外设/中断，
 * resourceIsHardware 其余真值）、soft（模块名/宏名等非硬件）。每组元素
 * {names, users, conflict}（soft 恒 conflict=false——非硬件不构成互斥冲突）：
 * pins 组内**用户集合相同**的条目合并 names（同一任务独占十几个引脚只占一行）；
 * names 保持首次出现顺序、组内冲突行先行；空聚合 → null。users [{id,title}]
 * 与 list/板图两视图共用（板图按 names 逐脚查用户）。 */
export function aggregateResourceGroups(plan) {
  const tasks = (plan || {}).tasks || [];
  const byResource = new Map();
  tasks.forEach((task, index) => {
    const resources = (task && task.resources) || [];
    resources.forEach((r) => {
      const name = String(r);
      if (!byResource.has(name)) byResource.set(name, []);
      byResource.get(name).push({ id: (task && task.id) || "t" + (index + 1), title: (task && task.title) || "", order: index + 1 });
    });
  });
  if (!byResource.size) return null;
  const isPin = (n) => /^P[A-G]\d{1,2}$/i.test(n);
  const userKey = (users) => users.map((u) => u.id).join("|");
  const pinRows = [];
  const pinByKey = new Map();
  const otherRows = [];
  const softRows = [];
  byResource.forEach((users, name) => {
    const hw = resourceIsHardware(name);
    const entry = { names: [name], users, conflict: hw && users.length >= 2 };
    if (isPin(name)) {
      const key = userKey(users);
      const row = pinByKey.get(key);
      if (row) row.names.push(name);
      else { pinByKey.set(key, entry); pinRows.push(entry); }
    } else if (hw) otherRows.push(entry);
    else softRows.push(entry);
  });
  // 组内冲突先行（同用户集合差异与稳定性由首次出现顺序保证）
  const sortRows = (rows) => rows.slice().sort((a, b) => Number(b.conflict) - Number(a.conflict));
  return { pins: sortRows(pinRows), other: sortRows(otherRows), soft: softRows };
}

/** 资源总览表（工单 task-insight/02，纯前端聚合零后端；resource-overview-polish/01
 * 重构为分组视图）：从 plan.tasks[].resources 聚合「资源名 → 用到的任务」。
 * **同一硬件资源**（引脚/外设/中断，判据 = resourceIsHardware）被 ≥2 任务占用 →
 * .res-conflict 行标黄「⚠ 多任务使用，上板前确认」（重复不一定是错——可能是先后
 * 复用，提示学生联调前确认）；非硬件项（模块名/函数名/宏名，如 xunji）多任务复用
 * = 正常代码复用，不标黄（.res-soft muted 样式，标题注「模块复用」降噪——AI 偶把
 * 模块名填入 resources，前端兜底不误导）。布局四段：⚠ 冲突资源（置顶）→ 引脚占用
 * （同任务独占合并 chips 行）→ 外设与中断 → 模块复用（details 默认收起）。全部任务
 * 无资源标注 = 空串（容器隐藏）。 */
export function resourcesOverviewHTML(plan) {
  const groups = aggregateResourceGroups(plan);
  if (!groups) return "";
  const rowHTML = (entry, rowClass, chipClass, note) => {
    const chips = entry.names.length > 1
      ? '<span class="res-chip-group">' + entry.names.map((n) => '<span class="res-chip' + chipClass + '">' + esc(n) + "</span>").join("") + "</span>"
      : '<span class="res-chip' + chipClass + '">' + esc(entry.names[0]) + "</span>";
    const userText = taskRefText(entry.users, 0);
    return '<div class="res-row' + rowClass + '">' + chips
      + '<span class="res-users">' + userText + "</span>"
      + (note ? note : "") + "</div>";
  };
  const conflictHRows = [...groups.pins, ...groups.other].filter((e) => e.conflict);
  const conflictHTML = conflictHRows.map((e) =>
    rowHTML(e, " res-conflict", "", '<span class="res-conflict-note">⚠ 多任务使用，上板前确认</span>')
  ).join("");
  const pinHTML = groups.pins.filter((e) => !e.conflict).map((e) => rowHTML(e, "", "", "")).join("");
  const otherHTML = groups.other.filter((e) => !e.conflict).map((e) => rowHTML(e, "", "", "")).join("");
  const softHTML = groups.soft.map((e) =>
    rowHTML(e, " res-soft", " res-soft", '<span class="res-soft-note">模块复用（非硬件，不算冲突）</span>')
  ).join("");
  const group = (title, inner, cls) => inner
    ? '<div class="res-group' + (cls ? " " + cls : "") + '"><div class="res-group-title">' + title + "</div>" + inner + "</div>"
    : "";
  const rows = group("⚠ 冲突资源（多任务硬件共享）", conflictHTML, "res-group-conflict")
    + group("引脚占用", pinHTML)
    + group("外设与中断", otherHTML)
    + (softHTML
      ? '<details class="res-soft-details"><summary class="res-group-title">模块复用（非硬件，不算冲突）</summary>' + softHTML + "</details>"
      : "");
  return '<div class="muted" style="margin-bottom:2px">资源总览（同一资源被多个任务占用 = 联调冲突暗雷，标黄提示）</div>'
    + '<div class="res-table">' + rows + "</div>";
}

/** 评分点分类中文标签（工单 score-coverage/02 抽取）：basic=基础 /
 * development=发挥 / 其余（unknown）=其他——与 taskScoreRefsText 同判据，
 * 两处共享单源。 */
function scorePartLabel(part) {
  return part === "basic" ? "基础" : part === "development" ? "发挥" : "其他";
}

/** 任务 id → 用户可见「第 N 步」（工单 beginner-gap-closure/03）：序号人话化，
 * 原始 id 不再上界面。seqById 缺省 {}；找不到 → 原样返回 id（防御：清单外的
 * 依赖/引用，避免丢信息）。 */
function seqRef(id, seqById) {
  const s = (seqById || {})[String(id == null ? "" : id)];
  return s != null ? "第 " + s + " 步" : String(id == null ? "" : id);
}

/** 用户可见任务引用（工单 beginner-gap-closure/03，自 score-coverage/02 抽取
 * 增长）：users 元素 {id, title, order?} → 「第 N 步：标题」（order 有则用，
 * 防御无 order 的旧聚合回退「id：标题」）。titleLimit 非零时标题截断
 * （覆盖总览 24 字）；返回原始串，调用方 esc。 */
export function taskUserLabel(u, titleLimit) {
  const title = titleLimit
    ? truncate((u && u.title) || "", titleLimit)
    : (u && u.title) || "";
  if (u && u.order != null) return "第 " + u.order + " 步：" + title;
  return String((u && u.id == null) ? "" : u.id) + "：" + title;
}

/** 任务引用行文本（「第 N 步：标题」串联，工单 score-coverage/02 抽取）：
 * users = [{id, title, order?}]；titleLimit 非零时标题截断（覆盖总览 24 字）——
 * 与 resourcesOverviewHTML 同形但总览要求标题截断，故带可选参数；全部 esc。 */
function taskRefText(users, titleLimit) {
  return users.map((u) => esc(taskUserLabel(u, titleLimit))).join(" · ");
}

/** 评分点覆盖总览（工单 score-coverage/02，纯前端聚合零后端）：题面每个
 * 评分点一行——id + 分类标签（基础/发挥/其他，与 taskScoreRefsText 同判据）
 * + 分值 + 描述截断（title 悬停全文）+ 覆盖它的任务（第 N 步：标题；原始
 * 任务 id 不上界面，工单 beginner-gap-closure/03）；**没有
 * 任何任务覆盖的评分点整行标红**（.score-point-miss + 「⚠ 无任务覆盖」）——
 * 交付前一眼可见丢分风险。任务引用了评分点清单之外的 id（AI 编造 / 清单
 * 外部改动）→ 每 id 一行「未识别引用」黄色警示（.score-point-unknown）。
 * 数据源 = plan.score_points（落盘值，工单 01）；空评分点 / 空清单 → ""。 */
export function scoreRefsOverviewHTML(plan) {
  const tasks = (plan || {}).tasks || [];
  const points = (plan || {}).score_points || [];
  if (!points.length || !tasks.length) return "";
  const known = new Set();
  points.forEach((p) => { if (p && typeof p.id === "string") known.add(p.id); });
  // 每评分点 → 覆盖它的任务（保序）
  const cover = {};
  tasks.forEach((task, index) => {
    const refs = (task && task.score_refs) || [];
    refs.forEach((id) => {
      if (typeof id !== "string") return;
      if (!cover[id]) cover[id] = [];
      cover[id].push({ id: (task && task.id) || "t" + (index + 1), title: (task && task.title) || "", order: index + 1 });
    });
  });
  const rows = points.map((p) => {
    const id = String(p.id || "");
    const users = cover[id] || [];
    const part = scorePartLabel(p.part);
    const score = (typeof p.score === "number" && Number.isFinite(p.score))
      ? " " + p.score + " 分"
      : "";
    const desc = typeof p.description === "string" ? p.description : "";
    const miss = users.length === 0;
    return '<div class="score-point-row' + (miss ? " score-point-miss" : "") + '">'
      + '<span class="score-chip">' + esc(id) + "</span>"
      + '<span class="score-point-part">' + esc(part) + "</span>"
      + (score ? '<span class="score-point-score">' + esc(score) + "</span>" : "")
      + '<span class="score-point-desc" title="' + esc(desc) + '">' + esc(truncate(desc, 60)) + "</span>"
      + (miss ? "" : '<span class="score-point-users">' + taskRefText(users, 24) + "</span>")
      + (miss ? '<span class="score-miss-note">⚠ 无任务覆盖</span>' : "")
      + "</div>";
  }).join("");
  // 清单外引用（AI 编造 / 清单外部改动）→ 警示行
  const unknownIds = Object.keys(cover).filter((id) => !known.has(id));
  const unknownRows = unknownIds.map((id) => {
    return '<div class="score-point-row score-point-unknown">'
      + '<span class="score-chip">' + esc(id) + "</span>"
      + '<span class="score-point-users">' + taskRefText(cover[id] || [], 24) + "</span>"
      + '<span class="score-unknown-note">未识别引用（不在评分点清单内）</span>'
      + "</div>";
  }).join("");
  return '<div class="muted" style="margin-bottom:2px">评分点覆盖总览（每个评分点对应哪些任务；无覆盖 = 丢分风险，标红提示）</div>'
    + '<div class="score-point-table">' + rows + unknownRows + "</div>";
}

/** 上板自检清单（工单 task-insight/02）：最新一轮的 checklist 渲染为可勾选
 * 列表——checkbox 勾选态存 localStorage（firstep.checklist.v1.<key>，key =
 * taskId+"/"+seq），纯备忘不影响状态机；勾选态由胶水层读盘后以 checkedMap
 * 传入（{序号: true}），纯函数不碰 localStorage（fx 约定无副作用）。空 = ""。
 * 默认收起（details 无 open）：清单 3-6 条原子项，卡/面板展开太长压重点；
 * 摘要行显示「N 项 · 已勾选 M」（M>0 才出现），收起也一眼可见进度。 */
export function taskChecklistHTML(iteration, key, checkedMap) {
  const items = (iteration && iteration.checklist) || [];
  // key 缺失 = 勾选无处持久化（无 taskId/seq 的调用点）：不渲染无用勾选
  if (!items.length || !key) return "";
  const checked = checkedMap || {};
  const checkedCount = items.reduce((n, _item, index) => n + (checked[index] ? 1 : 0), 0);
  const rows = items.map((item, index) => {
    const isChecked = !!checked[index];
    return '<label class="task-check-item"><input type="checkbox" class="task-check-input"'
      + ' data-check-key="' + esc(String(key || "")) + '" data-check-idx="' + esc(String(index)) + '"'
      + (isChecked ? " checked" : "") + "> " + esc(String(item)) + "</label>";
  }).join("");
  return '<details class="task-check-details" style="margin-top: var(--space-2)">'
    + '<summary class="task-check-summary">上板自检清单（' + String(items.length) + " 项"
    + (checkedCount ? " · 已勾选 " + String(checkedCount) : "") + "）</summary>"
    + '<div class="task-check-list" style="margin-top: var(--space-2)">'
    + '<div class="muted" style="margin-bottom:2px">勾选为个人备忘，不改变任务状态</div>'
    + rows + "</div></details>";
}

/** wiringOpts 单源提取（wiringSectionHTML / 两个展示位共用）：wiringOpts
 * 函数优先（每任务装配），缺省返回 null（回落 flat 字段——工单 03 契约）。
 * 哨兵一律 null（{} 真值会令 ctx=undefined 而吞掉 flat 回退——评审整改）。 */
function wiringPer(task, opts) {
  const o = opts || {};
  return (typeof o.wiringOpts === "function") ? (o.wiringOpts(task) || {}) : null;
}

/** 本步接线引用单点（工单 05 评审整改：①b 分支与胶水层 attachWiringInputs
 * 的「wiring 空 → resources ∩ 行反推 + inferred 判定」原为两处独立推导——
 * 已见漂移后果：toggle 重渲 caption 回退）。返回值 = {wiring, inferred}：
 * wiring = 最新轮引用（非空则用，inferred=false）或 resources 反推结果
 * （inferred=true——按资源标定，非 AI 引用）；均无 → {[], true}（调用方
 * 按空处理走退化）。数据纪律：线由 rows 决定，resources 只是选行名字。 */
export function taskWiringRefs(task, rows) {
  const last = lastIteration(task);
  const wiring = (last && last.wiring) || [];
  if (wiring.length) return { wiring, inferred: false };
  return {
    wiring: wiringFromResources((task && task.resources) || [], rows),
    inferred: true,
  };
}

/** 接线图区块（工单 task-wiring-diagram/03 + 04 + 05）：任务卡「下一步要做」与
 * 结果面板步骤报告共用同一装配（同一渲染函数、同一数据源——spec 决策）。
 *
 * 四级退化（任一情况不报错、不空白）：
 * ① wiring 引用非空且 board 可用 → 接线图（本步高亮；showAll 由
 *    wiringShowAll 传入，缺省 false = 只画本步线）；
 * ①b 无 wiring 引用但接线行可查（ctx.rows 非空，快照或 README 兜底）且
 *    本任务 resources ∩ 接线行非空 → 按资源标定接线图（inferred: true，
 *    caption 注明——工单 05：旧工程/校验全丢也能看到「引脚→端子」接线）；
 * ② 上述失败但任务有资源标注（wiringFallbackHTML 非空，胶水层按
 *    resourceIsHardware 判据预渲染资源高亮板图）→ 资源高亮板图；
 * ③ 都没有 → 空串（纯文字现状行为，调用方照常渲染文字指引）。
 * 数据装配 = opts.wiringCtx {board, rows}（快照 / /api/boards 同形板定义 +
 * 接线行；缺省 = 按退化路径）；工单 04 起胶水层经 opts.wiringOpts(task)
 * 传**每任务**装配（卡片 / 结果面板同任务但 uid 不同——见 wiringUid）。
 * perComputed = 调用方已取好的每任务装配（避免 wiringOpts(task) 执行两
 * 次——评审整改），缺省自行提取（03 契约调用方不传）。
 */
export function wiringSectionHTML(task, opts, perComputed) {
  const o = opts || {};
  const perTask = perComputed !== undefined ? perComputed : wiringPer(task, o);
  const ctx = perTask ? perTask.wiringCtx : o.wiringCtx;
  const fallback = perTask ? perTask.wiringFallbackHTML : o.wiringFallbackHTML;
  if (!ctx) return fallback || "";
  const refs = taskWiringRefs(task, ctx.rows || []);
  if (ctx.board && refs.wiring.length) {
    return wiringDiagramHTML({
      board: ctx.board,
      rows: ctx.rows || [],
      wiring: refs.wiring,
      showAll: perTask ? !!perTask.wiringShowAll : !!o.wiringShowAll,
      inferred: refs.inferred,
    });
  }
  return fallback || "";
}

/** 任务卡「下一步要做」粘性摘要（工单 stepwise-deepen/02 + 04 修正 +
 * task-wiring-diagram/04）：最新一轮报告的 user_action 非空 → 显示；唯一
 * 隐藏条件 = 该步已真正闭环（doing 执行中旧指引过期；verify=manual 且
 * verified = 用户已上板人工确认）。**compile 任务的 verified 只代表编译
 * 通过，仍需烧录上板**——指引必须常驻到用户实测（实测不符会走「上板反馈」
 * 自动重开，指引随新轮次更新）。让用户随时知道当前卡在哪个物理动作（接线 /
 * 烧录 / 观察）。opts.wiringCtx = 接线图数据装配（见 wiringSectionHTML）；
 * 图文并存：接线图置于顶部，原 user_action 文字保留在图下方。 */
export function taskNextActionHTML(task, opts) {
  if (!task || task.status === "doing") return "";
  if (task.verify === "manual" && task.status === "verified") return "";
  const last = lastIteration(task);
  const action = (last && last.user_action) || "";
  if (!String(action).trim()) return "";
  const perTask = wiringPer(task, opts);
  const wiring = wiringSectionHTML(task, opts, perTask);
  return '<div class="task-next-action" style="margin-top: var(--space-2);padding:4px 8px;'
    + 'border:1px solid var(--border);border-radius:var(--radius-md);background:var(--panel-2)">'
    + '<span class="badge out">下一步要做</span>'
    + (wiring ? '<div class="task-next-wiring" data-wiring-uid="' + esc(String(perTask && perTask.wiringUid || "")) + '" style="margin-top: var(--space-2)">' + wiring + "</div>" : "")
    + '<div style="margin-top: var(--space-2)">' + esc(String(action)) + "</div></div>";
}

/** 上板自检清单勾选键单源（工单 task-insight/02）：localStorage key =
 * firstep.checklist.v1.<taskId>/<seq>。纯函数（fx 约定无副作用），胶水层
 * 读写共用本函数——单源防 ui 层硬拼 key 与读取处漂移。 */
export function checklistStateKey(taskId, seq) {
  return "firstep.checklist.v1." + taskId + "/" + seq;
}

/** 任务卡上的最新轮 checklist（工单 task-insight/02，spec 轴评审整改——故事 3
 * 「刷新勾选仍在」的回显路径）：结果面板是执行时刻的一次性快照，刷新后消失；
 * 任务卡随 tasksRender 每次重建，最新轮 checklist 常驻卡上（与结果面板副本
 * 并存），勾选态经 opts.checklistState(taskId, seq)（胶水层读 localStorage）
 * 回显。无轮次 / 无 checklist / 未提供 state 桥 = 空串。
 * data-check-key 契约为裸键 "taskId/seq"（胶水层 change 委托 split 解析 +
 * checklistStateKey 包 localStorage 键；两处同步，勿改成完整 storage key）。 */
function taskCardChecklistHTML(task, o) {
  const last = lastIteration(task);
  if (!last || !(last.checklist || []).length) return "";
  const state = o.checklistState;
  if (typeof state !== "function") return "";  // 缺回显源：不画无法恢复勾选态的清单
  const key = task.id + "/" + last.seq;
  const checked = state(task.id, last.seq) || {};
  return taskChecklistHTML(last, key, checked);
}

/** 编译错误列表（工单 error-jump-task/02）：任务结果面板编译失败时列出
 * 「文件:行号 消息」；main.c 的行渲染为可点击（.task-err-jump data-line）——
 * 跳转单源 = fx/code.js maincJumpToLine（胶水层委托 + 错误码 toast）；非
 * main.c 错误（头文件/模块文件）不可点（修复中心才做源码行展开，故事 3）。
 * 空 / 非数组 → ""；全部 esc。 */
export function taskErrorsHTML(parsedErrors) {
  if (!Array.isArray(parsedErrors) || !parsedErrors.length) return "";
  const rows = [];
  for (const e of parsedErrors) {
    if (!e || typeof e !== "object") continue;
    const path = String(e.path == null ? "" : e.path);
    const line = Number(e.line);
    const message = String(e.message == null ? "" : e.message);
    if (!path && !message) continue;  // 全空条目无展示价值
    const jumpable = isMainCPath(path) && Number.isInteger(line) && line > 0;
    const loc = jumpable
      ? '<span class="task-err-jump" data-line="' + line + '">'
        + esc(path + ":" + line) + "</span>"
      : '<span class="muted">' + esc(path + (line ? ":" + line : "")) + "</span>";
    rows.push('<div class="task-err-row">' + loc + " " + esc(message) + "</div>");
  }
  return rows.length ? '<div class="task-err-list">' + rows.join("") + "</div>" : "";
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
      badge: '<span class="ok" style="font-weight:600">✓ 已通过编译验证</span>',
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
        || "未检测到编译工具链：结果已写入 main.c，但未经编译验证——请配置工具链后手动编译（上板类任务可直接人工标记为上板通过）。"),
    };
  }
  return {
    badge: '<span style="color:var(--danger);font-weight:600">✗ 未通过（编译验证失败）</span>',
    detail: esc((data && data.message) || fb.failed
      || "编译验证未通过，结果已写入 main.c（已备份，可回滚）。"),
  };
}

/** 任务执行结果「本轮变化」区（工单 task-changes-inline/01）：执行结果从网格
 * 末尾面板并入刚完成的任务卡——完整 diff / 编译验证详情 / 错误行跳转 / 备份
 * 回滚原地可见，无需滚动到网格底部。spec 决策（删重复）：步骤报告两块、
 * checklist 副本、feedback note、接线图**不重复**——卡上历史区（每轮详情
 * 原文）/ 常驻 checklist / 「下一步要做」接线图已有同源信息。
 * opts.open 控制 details 默认展开（执行完成自动展开；重开页面后变化区不存在
 * ——内存态 lastWiringResult 清零，不占地方）。data = /api/tasks/execute done
 * 载荷（task / status / compile.parsed_errors / main_diff / backup_id）；
 * data 缺失 → ""（防御，胶水层只在执行完成时调用）。 */
export function taskChangesHTML(task, data, opts) {
  if (!data || typeof data !== "object") return "";
  const o = opts || {};
  const t = task || {};
  const markup = verifyStatusMarkup(data, {
    unverified: "未检测到编译工具链：任务结果已写入 main.c，但未经编译验证——请配置工具链后手动编译，或上板后人工标记为上板通过。",
    failed: "编译验证未通过，任务结果已写入 main.c（已备份，可回滚）。",
  });
  const backupId = data.backup_id || "";
  const errorsHTML = taskErrorsHTML((data.compile && data.compile.parsed_errors) || []);
  const diffHTML = data.main_diff !== undefined ? mainDiffHTML(data.main_diff, "任务") : "";
  const parts = ['<div class="task-changes-detail">' + markup.detail + "</div>"];
  if (errorsHTML) parts.push(errorsHTML);
  parts.push('<div class="task-changes-backup">' + (backupId
    ? '已备份 · <button class="btn-task-rollback danger" data-backup="'
      + esc(String(backupId)) + '" data-task="' + esc(String(t.id || ""))
      + '">回滚到本任务执行前</button>' : "")
    + "</div>");
  if (diffHTML) parts.push(diffHTML);
  return '<details class="task-changes"' + (o.open ? " open" : "") + '>'
    + '<summary><span class="slug">本轮变化</span> ' + markup.badge + "</summary>"
    + '<div class="task-changes-body">' + parts.join("") + "</div></details>";
}

/** 全局商量消息行（工单 idea-suite/02）：用户 / AI 分行（复用
 * .sugg-msg 样式）+ at 时间；AI 回复挂三按钮——转成任务 / 转成修正（
 * data-global-action = task|fix，data-global-text = 该条全文，供胶水层走
 * 既有 idea 漏斗通道）、采纳为全局结论（adopt，写工程级注记）。
 * 文本进 data 属性前必须 esc（属性上下文防注入）。 */
function globalChatMessageHTML(msg) {
  const isAi = msg.role === "assistant";
  const text = String(msg.content);
  const roleLabel = isAi ? "AI" : "我";
  const actions = isAi
    ? ' <button class="btn-global-chat-action" data-global-action="task"'
      + ' data-global-text="' + esc(text) + '">转成任务</button>'
      + ' <button class="btn-global-chat-action" data-global-action="fix"'
      + ' data-global-text="' + esc(text) + '">转成修正</button>'
      + ' <button class="btn-global-chat-action" data-global-action="adopt"'
      + ' data-global-text="' + esc(text) + '">采纳为全局结论</button>'
    : "";
  const at = msg.at ? ' <span class="muted">' + esc(String(msg.at)) + "</span>" : "";
  return '<div class="sugg-msg ' + (isAi ? "ai" : "user") + '">'
    + '<span class="sugg-msg-role">' + roleLabel + "</span>：" + esc(text)
    + actions + at + "</div>";
}

/** 全局商量输入行（send 语义共享：输入框 + 发送按钮；busy 禁用防并发）。
 * draft = 输入框未发送内容（重渲染不丢）；busy 时按钮文案「回应中…」。 */
function globalChatInputHTML(s) {
  return '<div class="sugg-discuss-row"><input id="tasks-global-chat-input"'
    + ' class="sugg-discuss-input" placeholder="针对整个工程问 AI——如：整体架构要不要加滤波？赛道策略怎么取舍？…"'
    + ' value="' + esc(s.draft || "") + '">'
    + '<button class="btn-global-chat-send"' + (s.busy ? " disabled" : "") + ">"
    + (s.busy ? "回应中…" : "发送") + "</button></div>";
}

/** 全局工程级商量区（工单 idea-suite/02）：多轮对话历史落盘（后端
 * /api/tasks/idea/chat/*，.contest_idea_chat.json）；每条 AI 回复挂「转成
 * 任务 / 转成修正 / 采纳为全局结论」；st = {open, busy, chat, pending, draft}
 * ——chat = 后端 {messages:[{role,content,at}], note}（落盘真相）；pending =
 * 发送中尚未确认的用户消息（乐观展示，成功后被服务端 chat 替换）；未展开 =
 * 空串。历史全量渲染（转义）；空历史 + 无 pending → 引导文案。 */
export function globalChatHTML(st) {
  const s = st || {};
  if (!s.open) return "";
  const messages = ((s.chat && s.chat.messages) || []);
  const lines = messages.map(globalChatMessageHTML).join("");
  const pending = s.pending
    ? '<div class="sugg-msg user"><span class="sugg-msg-role">我</span>：'
      + esc(String(s.pending)) + "</div>"
    : "";
  const inner = (lines || pending)
    ? '<div class="sugg-discuss-msgs">' + lines + pending + "</div>"
    : '<div class="sugg-msg muted">这是针对整个工程的问题区（不绑任务卡）：'
      + "架构取舍 / 策略权衡 / 方案对不对，都能连续追问。AI 先给分析建议，"
      + "确认后可把回复「转成任务 / 转成修正」落地，或「采纳为全局结论」——"
      + "采纳后的结论会注入之后每一步任务执行与直接修正。</div>";
  return '<div class="task-dialog-box">' + inner
    + globalChatInputHTML(s)
    + (s.busy ? '<div class="sugg-discuss-note">AI 回应中…（分钟级调用，请等待）</div>' : "")
    + "</div>";
}

/** 全局结论徽标（工单 idea-suite/02）：chat.note 非空 → 「工程级全局结论」
 * 徽标 + 摘要（截 30 字）+ 清除按钮（data-global-action="clear"——复用聊天
 * 区按钮委托，挂在外层容器）；空 note = 空串（不渲染）。 */
export function globalNoteBadgeHTML(note) {
  if (!note || !String(note).trim()) return "";
  const text = String(note).trim();
  return '<div class="muted" style="margin-top: var(--space-1)">'
    + '<span class="badge ok">工程级全局结论</span> '
    + '<span title="' + esc(text) + '">' + esc(truncate(text, 30)) + "</span>"
    + ' <button class="btn-global-chat-action" data-global-action="clear">清除</button>'
    + "</div>";
}

/** 任务卡「⋯ 更多」菜单（收编自 idea-suite/04 的 ✏️ 编辑 + ↑/↓ 调序）：
 * 卡面只留一个小字下拉——编辑/调序属低频微调，裸按钮行太长太抢眼；
 * 菜单项 = 编辑任务信息（editing 态 =「收起编辑」）/ 上移 / 下移（边界
 * 禁用：首卡上移 / 末卡下移），data-task-action 与旧按钮一致（委托零改动，
 * 数据契约 edit|move-up|move-down + data-task）。
 * 原生 <details> 实现展开收起（零 JS 状态），菜单项点击后由胶水层委托
 * 收起（open=false）+ 重渲染；点击菜单外由胶水层 document 委托关闭。 */
export function taskMoreMenuHTML(task, index, total, editing) {
  const taskId = (task && task.id) || "";
  const n = Number(index), m = Number(total);
  const editLabel = editing ? "收起编辑" : "编辑任务信息";
  return '<details class="task-more-details">'
    + '<summary class="btn-task-more" title="更多操作（编辑 / 调序）">⋯ 更多</summary>'
    + '<div class="task-more-menu">'
    + '<button class="btn-task-edit" data-task-action="edit" data-task="'
    + esc(taskId) + '">' + editLabel + "</button>"
    + '<button class="btn-task-move" data-task-action="move-up" data-task="'
    + esc(taskId) + '"' + (n <= 0 ? " disabled" : "") + '>上移（换序）</button>'
    + '<button class="btn-task-move" data-task-action="move-down" data-task="'
    + esc(taskId) + '"' + (n >= m - 1 ? " disabled" : "") + '>下移（换序）</button>'
    + "</div></details>";
}

/** 任务卡编辑表单（工单 idea-suite/04）：标题/描述/依赖（逗号分隔 1 起序号，
 * 空 = 无依赖）/验收方式下拉（compile=编译验证 / manual=需上板人工确认）/
 * 评分点（逗号分隔，可空）。opts.seqById = {t1:1,...}（依赖 id → 序号回填——
 * 序号随调序变化，纯函数从 opts 拿映射）。保存/取消按钮 data-task-action =
 * edit-save|edit-cancel + data-task。全部当前值经 esc 回填（防注入）。 */
export function taskEditFormHTML(task, opts) {
  const o = opts || {};
  const seqById = o.seqById || {};
  const taskId = (task && task.id) || "";
  const depsText = (task.depends_on || [])
    .map((id) => (seqById[id] !== undefined ? String(seqById[id]) : id))
    .join(", ");
  const refsText = (task.score_refs || []).join(", ");
  return '<div class="task-edit-form" style="margin-top: var(--space-2)">'
    + '<label class="muted">标题</label>'
    + '<input type="text" id="task-edit-title-' + esc(taskId) + '" value="'
    + esc(task.title || "") + '">'
    + '<label class="muted">描述</label>'
    + '<textarea id="task-edit-desc-' + esc(taskId) + '" rows="2">'
    + esc(task.description || "") + "</textarea>"
    + '<label class="muted">依赖（逗号分隔的步骤序号，1 起；空 = 无依赖）</label>'
    + '<input type="text" id="task-edit-deps-' + esc(taskId) + '" value="'
    + esc(depsText) + '">'
    + '<label class="muted">验收方式</label>'
    + '<select id="task-edit-verify-' + esc(taskId) + '">'
    + '<option value="compile"' + (task.verify === "compile" ? " selected" : "")
    + ">编译验证</option>"
    + '<option value="manual"' + (task.verify === "manual" ? " selected" : "")
    + ">需上板人工确认</option></select>"
    + '<label class="muted">评分点（逗号分隔，可空）</label>'
    + '<input type="text" id="task-edit-refs-' + esc(taskId) + '" value="'
    + esc(refsText) + '">'
    + '<div class="row" style="margin-top: var(--space-2)">'
    + '<button class="btn-task-edit-save primary" data-task-action="edit-save" data-task="'
    + esc(taskId) + '">保存</button>'
    + '<button class="btn-task-edit-cancel" data-task-action="edit-cancel" data-task="'
    + esc(taskId) + '">取消</button>'
    + "</div></div>";
}

/** 草稿列表（工单 idea-suite/06）：逐条 = 文本（截 60 字展示 + title 全文）+
 * 「分析这条」（data-draft-action="analyze" + data-draft-text=全文）+
 * 「删除」（data-draft-action="delete" + data-draft-id）；底部「全部逐条
 * 分析」（data-draft-action="all"）；空列表 → 引导文案；opts.busy → 按钮
 * 全部禁用（防与一轮分析 / 删除并发）。纯函数 + esc：文本进 data 属性/
 * 文本节点一律转义。 */
export function ideaDraftListHTML(drafts, opts) {
  const o = opts || {};
  const list = drafts || [];
  if (!list.length) {
    return '<div class="muted">暂无草稿——现场想到什么先「存入草稿」，'
      + "回头逐条或批量分析。</div>";
  }
  const disabled = o.busy ? " disabled" : "";
  const items = list.map((d) => {
    const text = String(d.text || "");
    return '<div class="draft-item">'
      + '<span class="draft-text" title="' + esc(text) + '">' + esc(truncate(text, 60)) + "</span>"
      + ' <button class="btn-draft-analyze" data-draft-action="analyze"'
      + ' data-draft-text="' + esc(text) + '"' + disabled + ">分析这条</button>"
      + ' <button class="btn-draft-delete" data-draft-action="delete"'
      + ' data-draft-id="' + esc(d.id || "") + '"' + disabled + ">删除</button>"
      + "</div>";
  }).join("");
  return '<div class="muted" style="margin-bottom:4px">草稿（' + esc(String(list.length))
    + " 条）</div>" + items
    + '<div class="row" style="margin-top: var(--space-2)"><button class="btn-draft-all"'
    + ' data-draft-action="all"' + disabled + ">全部逐条分析</button></div>";
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    taskStatusLabel, taskStatusBadgeClass, taskVerifyLabel,
    taskScoreRefsText, taskCardHTML, tasksGridHTML, tasksProgressText,
    unresolvedPrereqs,
    tasksOverviewHTML, taskStepReportHTML, taskNextActionHTML,
    taskWiringRefs,
    verifyStatusMarkup, taskCanFeedback, taskIterationLabel,
    taskIterationsHTML, taskLatestFeedbackNote,
    taskOrderLabel, taskDialogAdoptHTML, taskDialogButtonHTML, taskDialogAreaHTML,
    nextTaskHint, taskNextHintHTML,
    ideaResultHTML, taskNeedsRedoBadge,
    taskStepReportBlocksHTML,
    globalChatHTML, globalNoteBadgeHTML,
    taskEditFormHTML, taskMoreMenuHTML,
    ideaDraftListHTML,
    taskResourcesHTML, resourceIsHardware, aggregateResourceGroups, resourcesOverviewHTML,
    scoreRefsOverviewHTML,
    checklistStateKey,
    taskErrorsHTML,
    taskChangesHTML,
    taskPhaseHTML,        // ux-polish-02/06：执行中阶段槽
    taskDetailsSnapshot,  // ux-polish-02/06：details 展开态快照/恢复
    taskDetailsRestore,
  });
}
