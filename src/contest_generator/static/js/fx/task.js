// fx/task.js — 任务推进纯函数（工单 task-progress/01）：任务卡渲染 / 状态徽章 /
// 验收方式标注 / 进度汇总。共享件用 esc（fx/core.js）。模块约定见 fx/core.js 头部。
import { esc, truncate } from "./core.js";
import { flashPanelHTML } from "./flash.js";  // 任务卡烧录控制行（flash-step-button/01；flash.js 仅依赖 core.js，无环）

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
  let html = '<div class="item idea-result" style="margin-top:8px">'
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
        + esc(a.affected_task_ids.join("、")) + "</div>";
    }
  } else {
    html += '<div class="reason muted">这是先讨论的建议——可以继续补充想法，'
      + "或把 AI 的建议直接落地：</div>";
  }
  if (o.landedNote) {
    html += '<div class="reason muted" style="margin-top:6px">' + esc(String(o.landedNote)) + "</div>";
  } else {
    const buttons = kind === "new_task"
      ? ideaActionButtonHTML("btn-idea-insert", "生成任务", kind)
      : kind === "direct_fix"
        ? ideaActionButtonHTML("btn-idea-fix", "改动预览并执行", kind)
        : ideaActionButtonHTML("btn-idea-to-task", "把建议变成任务", kind)
          + ideaActionButtonHTML("btn-idea-to-fix", "把建议变成修正", kind);
    html += '<div class="row" style="margin-top:8px">' + buttons + "</div>";
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

/** 当前卡内的「下一步 → tN：标题」提示行（工单 step-next-guide/01）：
 * 纯 HTML 串（title 经 esc 防注入）；无下一步 → 空串（调用方不渲染）。 */
export function taskNextHintHTML(plan, currentId) {
  const next = nextTaskHint(plan, currentId);
  if (!next) return "";
  return '<div class="task-next-hint">下一步 → ' + esc(next.id) + "："
    + esc(next.title) + "</div>";
}

export function taskCardHTML(task, index, opts) {
  const o = opts || {};
  const badge = '<span class="badge ' + taskStatusBadgeClass(task.status) + '">'
    + taskStatusLabel(task.status) + "</span>"
    // 待上板标注（工单 stepwise-deepen/02，spec「在总览与卡片上明确标注
    // 待上板」）：unverified = 结果已写入但未经编译验证 / 或需上板人工确认，
    // 下一步物理动作 = 上板（烧录观察）→ 卡上明示，与总览口径一致
    + (task.status === "unverified" ? ' <span class="badge unverified">待上板</span>' : "")
    // 建议重做徽章（工单 idea-fix/02）：灵活修正落地后受影响任务标记
    + taskNeedsRedoBadge(task);
  const refs = taskScoreRefsText(task.score_refs, o.scorePoints);
  const deps = (task.depends_on || []).length
    ? '<div class="muted" style="margin-top:4px">前置：' + esc(task.depends_on.join("、")) + "</div>"
    : "";
  const verifyNote = task.verify === "manual"
    ? '<span class="muted"> · ' + taskVerifyLabel(task.verify) + "</span>"
    : "";
  return '<div class="item" data-task-id="' + esc(task.id) + '">'
    + '<div class="head"><span class="slug">' + taskOrderLabel(index) + " · " + task.id
    + " · " + esc(task.title) + "</span>"
    + " " + badge + "</div>"
    + '<div class="reason">' + esc(task.description) + "</div>"
    // 资源徽标（工单 task-insight/02）：本任务占用的引脚/外设/中断（拆解时
    // AI 标注，顶部资源总览据此发现联调冲突）——非空才渲染
    + taskResourcesHTML(task)
    + (refs ? '<div class="muted" style="margin-top:4px">评分点：' + esc(refs) + verifyNote + "</div>" : (verifyNote ? '<div class="muted" style="margin-top:4px">' + verifyNote + "</div>" : ""))
    + deps
    + taskIterationsHTML(task)
    + taskDialogAdoptHTML(task)
    + taskNextActionHTML(task)
    // 上板自检清单常驻（工单 task-insight/02，spec 轴评审整改：结果面板只在
    // 执行时渲染一次，刷新后不重建——勾选态 localStorage 无处回显 = 故事 3
    // 「刷新勾选仍在」只写不可读。任务卡随 tasksRender 每次重建，最新轮
    // checklist 常驻卡上（结果面板副本并存），刷新后勾选立即回显）。
    // checklistState 由胶水层提供（读 localStorage 纯函数桥，fx 无副作用）。
    + taskCardChecklistHTML(task, o)
    // 微编辑 + 调序（工单 idea-suite/04）：编辑按钮 + ↑/↓（边界禁用）+ 编辑态
    // 表单（opts.editing(task.id) 为真 = 胶水层已展开该卡编辑表单）
    + '<div class="row" style="margin-top:6px;gap:6px">'
    + taskEditButtonHTML(task, !!(o.editing && o.editing(task.id)))
    + taskMoveButtonsHTML(task, index, Number(o.total) || 0)
    + "</div>"
    + (o.editing && o.editing(task.id) ? taskEditFormHTML(task, o) : "")
    // 任务卡烧录控制行（工单 flash-step-button/01）：已实现过的步骤（有迭代
    // 记录或已终态 = taskCanFeedback 判据）常驻「烧录到板子」——做完一步直接
    // 在卡上烧录上板检测；pending/skipped/doing 不显示（防烧旧固件 / 防并发）。
    // 卡内独立容器（uid = task.id），与执行结果面板的烧录行（uid = "result"）并存。
    // task.id 假值不渲染（评审整改：裸 id 传空 → flashContainer 缺省降成
    // "result" 撞结果面板容器；真实 id 由后端生成非空，此处防御）
    + (o.outputDir && task.id && taskCanFeedback(task) ? flashPanelHTML(o.outputDir, task.id) : "")
    + (o.actions ? '<div class="row" style="margin-top:8px">' + o.actions(task, index) + "</div>" : "")
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
    })).join("");
}

export function tasksProgressText(plan) {
  const tasks = (plan || {}).tasks || [];
  const done = tasks.filter((t) => t.status === "verified" || t.status === "skipped").length;
  return "进度 " + done + "/" + tasks.length;
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
    + seg(verified, "seg-ok", "已验证") + seg(doing, "seg-doing", "进行中")
    + seg(unverified, "seg-unverified", "待上板") + seg(failed, "seg-failed", "失败")
    + seg(pending, "seg-pending", "待做") + seg(skipped, "seg-skipped", "已跳过")
    + "</div>";
  const summary = "已完成 <b style=\"color:var(--ok-bright)\">" + verified + "</b>/" + total
    + (doing ? " · 进行中 " + doing : "")
    + (unverified ? " · 待上板 " + unverified : "")
    + (failed ? " · 失败 " + failed : "")
    + (pending ? " · 待做 " + pending : "")
    + (skipped ? " · <span class=\"muted\">已跳过 " + skipped + "（不计入完成）</span>" : "");
  return bar + '<div class="muted" style="margin-top:3px">' + summary + "</div>";
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
      ? '<span class="muted">「' + esc(truncate(it.feedback, 40)) + "」</span> "
      : "";
    const compile = it.compile_summary
      ? ' <span class="badge ' + iterationCompileBadgeClass(it.status) + '">编译：'
        + esc(truncate(it.compile_summary, 40)) + "</span>"
      : "";
    // 步骤报告摘要（工单 stepwise-deepen/02）：该轮「AI 做了什么」截 40 字；
    // 报告调用降级（空串）= 不显示（历史行保持干净）
    const changed = it.what_changed
      ? ' <span class="muted">「' + esc(truncate(it.what_changed, 40)) + "」</span>"
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
      + compile + changed + at
      + (it.backup_id ? ' 备份 <span class="slug">' + esc(String(it.backup_id)) + "</span>" : "")
      + " " + rollback + "</div>";
  }).join("");
  return '<div class="muted" style="margin-top:8px">历史记录（共 ' + esc(String(iterations.length))
    + " 轮）</div>" + rows;
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
  return '<div class="muted" style="margin-top:4px">'
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
  return '<div class="task-step-report" style="margin-top:8px;border-top:1px dashed var(--border);padding-top:6px">'
    + '<div class="muted" style="margin-bottom:2px">步骤报告（AI 本步总结）</div>'
    + taskStepReportBlocksHTML(last.what_changed || "", last.user_action || "")
    + taskChecklistHTML(last, o.checkKey || "", o.checkedMap || {})
    + "</div>";
}

/** 任务卡资源徽标行（工单 task-insight/02）：本任务占用的互斥资源（拆解时
 * AI 标注 resources——引脚/外设/中断真实名；与其它任务共用也列出）。空 = 空串
 *（旧清单无该字段 / 本任务不新增占用）。 */
export function taskResourcesHTML(task) {
  const resources = (task && task.resources) || [];
  if (!resources.length) return "";
  return '<div class="muted" style="margin-top:4px">资源：'
    + resources.map((r) => '<span class="res-chip">' + esc(String(r)) + "</span>")
      .join(" ")
    + "</div>";
}

/** 资源总览表（工单 task-insight/02，纯前端聚合零后端）：从 plan.tasks[].resources
 * 聚合「资源名 → 用到的任务」。同一资源被 ≥2 任务占用 → .res-conflict 行标黄
 * 「⚠ 多任务使用，上板前确认」（重复不一定是错——可能是先后复用，提示学生
 * 联调前确认）。全部任务无资源标注 = 空串（容器隐藏）。 */
export function resourcesOverviewHTML(plan) {
  const tasks = (plan || {}).tasks || [];
  const byResource = new Map();
  tasks.forEach((task, index) => {
    const resources = (task && task.resources) || [];
    resources.forEach((r) => {
      const name = String(r);
      if (!byResource.has(name)) byResource.set(name, []);
      byResource.get(name).push({ id: (task && task.id) || "t" + (index + 1), title: (task && task.title) || "" });
    });
  });
  if (!byResource.size) return "";
  const rows = Array.from(byResource.entries()).map(([name, users]) => {
    const conflict = users.length >= 2;
    const userText = users.map((u) => esc(u.id + "：" + (u.title || ""))).join(" · ");
    return '<div class="res-row' + (conflict ? " res-conflict" : "") + '">'
      + '<span class="res-chip">' + esc(name) + "</span>"
      + '<span class="res-users">' + userText + "</span>"
      + (conflict ? '<span class="res-conflict-note">⚠ 多任务使用，上板前确认</span>' : "")
      + "</div>";
  }).join("");
  return '<div class="muted" style="margin-bottom:2px">资源总览（同一资源被多个任务占用 = 联调冲突暗雷，标黄提示）</div>'
    + '<div class="res-table">' + rows + "</div>";
}

/** 上板自检清单（工单 task-insight/02）：最新一轮的 checklist 渲染为可勾选
 * 列表——checkbox 勾选态存 localStorage（firstep.checklist.v1.<key>，key =
 * taskId+"/"+seq），纯备忘不影响状态机；勾选态由胶水层读盘后以 checkedMap
 * 传入（{序号: true}），纯函数不碰 localStorage（fx 约定无副作用）。空 = ""。 */
export function taskChecklistHTML(iteration, key, checkedMap) {
  const items = (iteration && iteration.checklist) || [];
  // key 缺失 = 勾选无处持久化（无 taskId/seq 的调用点）：不渲染无用勾选
  if (!items.length || !key) return "";
  const checked = checkedMap || {};
  const rows = items.map((item, index) => {
    const isChecked = !!checked[index];
    return '<label class="task-check-item"><input type="checkbox" class="task-check-input"'
      + ' data-check-key="' + esc(String(key || "")) + '" data-check-idx="' + esc(String(index)) + '"'
      + (isChecked ? " checked" : "") + "> " + esc(String(item)) + "</label>";
  }).join("");
  return '<div class="task-check-list" style="margin-top:6px">'
    + '<div class="muted" style="margin-bottom:2px">上板自检清单（勾选为个人备忘，不改变任务状态）</div>'
    + rows + "</div>";
}

/** 任务卡「下一步要做」粘性摘要（工单 stepwise-deepen/02 + 04 修正）：最新一轮
 * 报告的 user_action 非空 → 显示；唯一隐藏条件 = 该步已真正闭环（doing 执行
 * 中旧指引过期；verify=manual 且 verified = 用户已上板人工确认）。**compile 任务
 * 的 verified 只代表编译通过，仍需烧录上板**——指引必须常驻到用户实测（实测
 * 不符会走「上板反馈」自动重开，指引随新轮次更新）。让用户随时知道当前卡在
 * 哪个物理动作（接线 / 烧录 / 观察）。 */
export function taskNextActionHTML(task) {
  if (!task || task.status === "doing") return "";
  if (task.verify === "manual" && task.status === "verified") return "";
  const last = lastIteration(task);
  const action = (last && last.user_action) || "";
  if (!String(action).trim()) return "";
  return '<div class="task-next-action" style="margin-top:6px;padding:4px 8px;'
    + 'border:1px solid var(--border);border-radius:8px;background:var(--panel-2)">'
    + '<span class="badge out">下一步要做</span> '
    + esc(String(action)) + "</div>";
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
  return '<div class="muted" style="margin-top:4px">'
    + '<span class="badge ok">工程级全局结论</span> '
    + '<span title="' + esc(text) + '">' + esc(truncate(text, 30)) + "</span>"
    + ' <button class="btn-global-chat-action" data-global-action="clear">清除</button>'
    + "</div>";
}

/** 任务卡上移 / 下移按钮（工单 idea-suite/04）：↑/↓ 相邻换序（数组顺序 =
 * 展示顺序；id 不变，依赖引用稳定——spec「排序后 id 不变」）。边界禁用：
 * 首卡 ↑ 禁用 / 末卡 ↓ 禁用（视觉 + disabled 双保险）。data-task-action =
 * move-up|move-down + data-task（委托需要任务上下文）；
 * index = 0 起序号，total = 任务总数。
 * 注：工单签名 (index, total) 无法携带任务 id，实现为 (task, index, total)
 * ——委托必须知道换的是哪张卡（与既有 .btn-task-* 均带 data-task 同构）。 */
export function taskMoveButtonsHTML(task, index, total) {
  const taskId = (task && task.id) || "";
  const n = Number(index), m = Number(total);
  const up = '<button class="btn-task-move" data-task-action="move-up" data-task="'
    + esc(taskId) + '"' + (n <= 0 ? " disabled" : "") + ' title="上移（换序）">↑</button>';
  const down = '<button class="btn-task-move" data-task-action="move-down" data-task="'
    + esc(taskId) + '"' + (n >= m - 1 ? " disabled" : "") + ' title="下移（换序）">↓</button>';
  return '<span class="task-move">' + up + down + "</span>";
}

/** 任务卡编辑按钮（工单 idea-suite/04）：点开卡内表单（胶水层切 editing 态
 * 重渲染把 taskEditFormHTML 插进卡内）；editing = 表单已展开（文案「收起」）。 */
function taskEditButtonHTML(task, editing) {
  return '<button class="btn-task-edit" data-task-action="edit" data-task="'
    + esc((task && task.id) || "") + '"'
    + (editing ? ' title="收起编辑" >收起' : ' title="编辑标题/描述/依赖/验收方式" >✏️ 编辑')
    + "</button>";
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
  return '<div class="task-edit-form" style="margin-top:6px">'
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
    + '<div class="row" style="margin-top:6px">'
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
    + '<div class="row" style="margin-top:6px"><button class="btn-draft-all"'
    + ' data-draft-action="all"' + disabled + ">全部逐条分析</button></div>";
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    taskStatusLabel, taskStatusBadgeClass, taskVerifyLabel,
    taskScoreRefsText, taskCardHTML, tasksGridHTML, tasksProgressText,
    tasksOverviewHTML, taskStepReportHTML, taskNextActionHTML,
    verifyStatusMarkup, taskCanFeedback, taskIterationLabel,
    taskIterationsHTML, taskLatestFeedbackNote,
    taskOrderLabel, taskDialogAdoptHTML, taskDialogButtonHTML, taskDialogAreaHTML,
    nextTaskHint, taskNextHintHTML,
    ideaResultHTML, taskNeedsRedoBadge,
    taskStepReportBlocksHTML,
    globalChatHTML, globalNoteBadgeHTML,
    taskEditFormHTML, taskMoveButtonsHTML,
    ideaDraftListHTML,
    taskResourcesHTML, resourcesOverviewHTML, taskChecklistHTML,
    checklistStateKey,
  });
}
