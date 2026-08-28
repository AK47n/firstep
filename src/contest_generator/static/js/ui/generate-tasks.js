// ui/generate-tasks.js — 生成页 · 任务推进簇（工单 task-progress/01-03：
// 拆解任务 / 逐任务执行 / 状态管理）DOM 胶水。
//
// 任务推进 = 生成后的主推进入口：AI 把题面 + 功能需求 + 评分点 + 模块接口 +
// main.c 拆成有序任务清单（落盘 .contest_tasks.json）→ 任务卡逐张执行 →
// 每步备份 + 编译验证闭环 → 状态徽章实时更新。
//
// 本簇状态 = tasks（私有对象）；输出目录复用「修订与深化」卡的已加载上下文
// （reviseGetDir——跨簇只读 import，主写簇归 generate-revise.js）。
// 全局商量（工单 idea-suite/02）同簇：/api/tasks/idea/chat/read|send|adopt
// 三个同步端点，历史落盘 .contest_idea_chat.json。
// 赛道事件词表镜像 events.py：task_planning / task_executing / compile_start /
// fix_start / verify_result / task_reporting / idea_analyzing / idea_result /
// llm_telemetry / done / error。
// 纯件在 fx/task.js（taskStatusLabel / taskCardHTML / tasksGridHTML …）。
// 依赖：app.js（$ / apiPost / toast）+ fx/core.js（esc）+ fx/llm.js
//（parseSSE / formatLLMTelemetry）+ fx/task.js + fx/diff.js（效果 diff 渲染）
// + ui/usage.js（recordLLMUsage）
// + ui/step-state.js（markStepDone）+ ui/confirm.js（confirmModal）。
import { $, apiPost, toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { esc, truncate } from "/js/fx/core.js";
import { parseSSE, formatLLMTelemetry } from "/js/fx/llm.js";
import { taskCanFeedback, taskCardActions, tasksGridHTML, tasksProgressText, tasksOverviewHTML, resourcesOverviewHTML, scoreRefsOverviewHTML, taskStepReportHTML, taskStepReportBlocksHTML, verifyStatusMarkup, taskLatestFeedbackNote, taskDialogButtonHTML, taskDialogAreaHTML, nextTaskHint, taskNextHintHTML, ideaResultHTML, globalChatHTML, globalNoteBadgeHTML, ideaDraftListHTML, checklistStateKey, taskErrorsHTML, tasksDoneCount } from "/js/fx/task.js";
import { maincJumpToLine } from "/js/fx/code.js";  // 错误行跳转单源（error-jump-task/02）
import { flashPanelHTML, flashContainer } from "/js/fx/flash.js";
import { flashRunShared } from "/js/ui/flash.js";
import { recordLLMUsage } from "/js/ui/usage.js";
import { markStepDone } from "/js/ui/step-state.js";
import { scorePoints } from "./generate-recommend.js";  // 当前会话推荐评分点（历史目录为空）
import { reviseGetDir } from "./generate-revise.js";  // 已加载上下文（只读）
import { mainDiffHTML } from "/js/fx/diff.js";        // 效果 diff 渲染（diff-restyle/01）

let tasks = {
  outputDir: "",      // 拆解 / 执行针对的输出目录
  plan: null,         // /api/tasks/plan 的 done 载荷
  busy: false,        // 任一流程运行中（按钮置灰）
};

// 新想法 / 问题区状态（工单 idea-fix/02）：analysis = 最近一次 /api/tasks/idea/
// analyze 的 done 载荷（{kind, reply, new_task, fix_summary, affected_task_ids}）；
// ideaText = 提交的原文（直接修正端点 idea 字段用原文而非 AI 理解——分析只改
// 展示，落地按用户原话 + AI fix_summary 执行）；busy = 一轮分析/落地进行中。
// 会话级（刷新丢；落盘以 .contest_tasks.json 为准）。
let ideaState = {
  busy: false,
  analysis: null,
  ideaText: "",
};

// 全局商量区状态（工单 idea-suite/02）：chat = 后端 /chat/read|send|adopt 的
// 落盘真相 {messages:[{role,content,at}], note}——会话内缓存，刷新后 /chat/read
// 重读；open / busy / pending（发送中尚未确认的用户消息——乐观展示，成功后
// 被服务端 chat 替换）/ draft（输入未发内容——失败回填便于重试）。
let chatState = {
  busy: false,
  open: false,
  chat: null,
  pending: "",
  draft: "",
};

// 草稿箱状态（工单 idea-suite/06）：drafts = 后端 /drafts/read 的数组（落盘
// 真相，.contest_ideas.json），busy = 一轮分析/删除/批量进行中；会话内缓存，
// 目录变化时重读（跨簇重置清空）。
let draftState = {
  busy: false,
  drafts: null,
};

/** 想法区结果卡渲染：analysis 空 → 隐藏容器；landedNote 非空 → 按钮区替换为
 * 中性提示（防已落地功能被重复点击造重复产物）；idea 原文随结果卡回显
 *（故事 6——会话内保留展示）。 */
function renderIdeaResult(landedNote) {
  const box = $("tasks-idea-result");
  const analysis = ideaState.analysis;
  if (!analysis) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  box.innerHTML = ideaResultHTML(analysis, {
    idea: ideaState.ideaText,
    landedNote: landedNote || "",
  });
  box.classList.remove("hidden");
}

function ideaSetBusy(busy) {
  ideaState.busy = busy;
  tasksSetBusy(busy);
  const btn = $("btn-tasks-idea");
  if (btn) btn.disabled = busy;
}

/** 想法区重置（跨簇目录切换 / 清单作废）：清空输入与分析结果（会话级状态
 * 随目录生命周期走，防旧目录的分析卡串到新目录）。 */
function resetIdeaArea() {
  ideaState.busy = false;
  ideaState.analysis = null;
  ideaState.ideaText = "";
  const box = $("tasks-idea-result");
  if (box) { box.innerHTML = ""; box.classList.add("hidden"); }
  const input = $("tasks-idea-input");
  if (input) input.value = "";
  const msg = $("tasks-idea-msg");
  if (msg) msg.textContent = "";
}

// 每卡对话区状态（工单 task-chat/03）：key = task id；{open, busy, history,
// draft}——history = [{role, content}]（旧 → 新，含 AI 回复），draft = 输入框
// 未发送内容（重渲染不丢）；对话历史会话级（刷新丢，采纳结论落盘不丢）。
const taskDialogs = new Map();

function taskDialogState(taskId) {
  let st = taskDialogs.get(taskId);
  if (!st) {
    st = { open: false, busy: false, history: [], draft: "" };
    taskDialogs.set(taskId, st);
  }
  return st;
}

function tasksSetBusy(busy) {
  tasks.busy = busy;
  ["btn-tasks-plan", "btn-tasks-replan"].forEach((id) => { $(id).disabled = busy; });
}

/** 全局忙碌闸只读视图（工单 param-tune/02）：参数速调卡（ui/params.js）
 * 与任务执行/回滚/烧录共用同一闸——两个流程都在写 main.c，互斥防撞车。 */
function tasksIsBusy() {
  return tasks.busy;
}

/** 任务推进徽章快照（工单 step11-tabs-ui/02）：已做（verified|skipped）/ 总数；
 * 无清单 = 0/0（页签徽章不显示）。计数复用 fx/task.js tasksDoneCount（评审
 * 整改：与进度文本同口径单源）。 */
export function tasksSummary() {
  const planTasks = (tasks.plan || {}).tasks || [];
  return { done: tasksDoneCount(tasks.plan), total: planTasks.length };
}

/** 任务推进面板空态引导（工单 step11-tabs-ui/02 评审整改）：未加载输出目录时
 * 显示「先去修订页签加载目录」提示；目录就绪后隐藏。 */
function updateTasksEmptyHint() {
  const hint = $("tasks-empty-hint");
  if (hint) hint.classList.toggle("hidden", !!tasks.outputDir);
}
/** 乐观置卡状态（工单 05）：点击「做这一步」即刻把该卡在内存态置为 doing 并
 * 重渲染——卡片马上出现「进行中」徽章、执行按钮消失，不等 SSE 首帧。真实状态
 * 后续由 task_executing / done / 失败重读（tasksReload）回填，磁盘态才是真相。 */
function setTaskStatusLocal(taskId, status) {
  if (!tasks.plan || !tasks.plan.tasks) return;
  tasks.plan.tasks = tasks.plan.tasks.map((t) => t.id === taskId ? { ...t, status } : t);
}

function tasksRender() {
  const plan = tasks.plan;
  const grid = $("tasks-grid");
  // 结果面板随渲染清除（每次执行/拆解后重建，防陈旧结果残留；结果面板在
  // 网格容器内——beforeend 插入，innerHTML 清空即整体移除）
  if (!plan || !(plan.tasks || []).length) {
    grid.classList.add("hidden");
    grid.innerHTML = "";
  } else {
    // 评分点数据源统一（工单 score-coverage/02）：落盘值优先（plan.score_points
    // 拆解时同批写入——刷新 / 历史目录仍有全量定义），会话 scorePoints 仅作
    // 无落盘时的回退。任务卡标注与覆盖总览同源，历史目录不再只剩裸 id。
    const scorePointsForPlan = (plan.score_points && plan.score_points.length)
      ? plan.score_points : scorePoints;
    grid.innerHTML = tasksGridHTML(plan, {
      scorePoints: scorePointsForPlan,
      // outputDir（工单 flash-step-button/01）：任务卡烧录控制行需要输出目录
      //（卡内独立容器，uid = task.id）——透传给 taskCardHTML
      outputDir: tasks.outputDir,
      // 上板自检清单勾选桥（工单 task-insight/02）：任务卡常驻最新轮清单——
      // 刷新后卡随 tasksRender 重建，勾选态经本桥从 localStorage 回显
      checklistState: (taskId, seq) => checklistRead(taskId, seq),
      // 编辑态（工单 idea-suite/04）：taskEditOpen 含该卡 id = 表单已展开
      editing: (taskId) => taskEditOpen.has(taskId),
      actions: (task) => {
        // 操作显隐单源 = fx/task.js taskCardActions（与后端转移表镜像，
        // 同一状态机一份 JS 编码——曾内联 if/else 与转移表分叉风险）
        // recoverable（工单 stuck-doing-recover/01）：doing + 无活跃执行 =
        // 执行中断的僵尸卡 → 显示「恢复」；真实执行中的拦截由后端注册表兜底
        const actions = taskCardActions(task.status, {
          recoverable: task.status === "doing" && !tasks.busy,
        });
        const parts = [];
        if (actions.includes("recover")) {
          parts.push('<button class="btn-task-recover" data-task="' + esc(task.id)
            + '" title="该步显示进行中但没有任务在跑（上次执行可能中断）——恢复为待做后可重新点「做这一步」">已中断？恢复此步</button>');
        }
        if (actions.includes("run")) {
          parts.push('<input type="text" id="task-note-' + esc(task.id)
            + '" placeholder="补充说明（可选）…" style="flex:1">'
            + '<button class="btn-task-run" data-task="' + esc(task.id) + '">做这一步</button>');
        }
        if (actions.includes("skip")) {
          parts.push('<button class="btn-task-skip" data-task="' + esc(task.id) + '">跳过</button>');
        }
        if (actions.includes("revert")) {
          // needs_redo 卡不显示普通「重做 / 恢复」（评审整改：与「重做此步」
          // 重复且「重做」不清 needs_redo 标记——重做此步 = 重置 + 清标，
          // 语义超集，一个入口够）
          if (!task.needs_redo) {
            parts.push('<button class="btn-task-revert" data-task="' + esc(task.id) + '">'
              + (task.status === "skipped" ? "恢复" : "重做") + "</button>");
          }
        }
        if (actions.includes("mark")) {
          parts.push('<button class="btn-task-mark" data-task="' + esc(task.id) + '">确认通过</button>');
        }
        // 建议重做（工单 idea-fix/02）：灵活修正落地后受影响的卡——一键重置
        // 为 pending + 清 needs_redo（随后可点「做这一步」走既有闭环）
        if (task.needs_redo) {
          parts.push('<button class="btn-task-redo" data-task="' + esc(task.id) + '">重做此步</button>');
        }
        if (taskCanFeedback(task)) {
          parts.push('<button class="btn-task-feedback" data-task="' + esc(task.id) + '">上板反馈</button>'
            + '<div id="task-feedback-' + esc(task.id) + '" class="hidden" style="width:100%">'
            + '<textarea placeholder="描述上板实测现象（如：左轮不转 / 不沿线向右偏 / 灰度读不到）…" style="width:100%;min-height:56px"></textarea>'
            + '<button class="btn-task-feedback-send" data-task="' + esc(task.id) + '">按反馈修复</button>'
            + "</div>");
        }
        // 每卡「和 AI 商量」对话区（工单 task-chat/03）：doing 不显示（执行中
        // 不可操作）；对话历史 + 采纳徽标在纯函数侧渲染，本层只喂状态
        const dialogSt = taskDialogState(task.id);
        parts.push(taskDialogButtonHTML(task, dialogSt));
        parts.push(taskDialogAreaHTML(task, dialogSt));
        return parts.join("");
      },
    });
    grid.classList.remove("hidden");
  }
  $("tasks-progress").textContent = tasksProgressText(plan);
  // 进度总览（工单 stepwise-deepen/02）：分段进度条 + 状态汇总；空清单隐藏
  const overview = $("tasks-overview");
  const overviewHTML = tasksOverviewHTML(plan);
  overview.innerHTML = overviewHTML;
  overview.classList.toggle("hidden", !overviewHTML);
  // 资源总览（工单 task-insight/02）：资源 × 使用任务聚合表，冲突行标黄
  //（同一资源 ≥2 任务占用 = 联调冲突暗雷）；紧跟进度总览，空串隐藏
  const resBox = $("tasks-resources");
  const resHTML = resourcesOverviewHTML(plan);
  resBox.innerHTML = resHTML;
  resBox.classList.toggle("hidden", !resHTML);
  // 评分点覆盖总览（工单 score-coverage/02）：每个评分点 → 覆盖它的任务，
  // 无覆盖标红；数据源 = 落盘 plan.score_points（spec：空评分点容器隐藏；
  // 会话值仅作任务卡标注回退，覆盖总览直读落盘值——旧清单无落盘即隐藏）。
  // 紧跟在资源总览后（#tasks-scorepoints），空串隐藏
  const scoreBox = $("tasks-scorepoints");
  const scoreHTML = scoreRefsOverviewHTML(plan);
  scoreBox.innerHTML = scoreHTML;
  scoreBox.classList.toggle("hidden", !scoreHTML);
  $("btn-tasks-replan").classList.toggle("hidden", !(plan && (plan.tasks || []).length));
  updateTasksEmptyHint();
  // 状态徽章（step11-tabs-ui/02）：渲染后广播任务推进状态快照（页签徽章就地刷新）
  window.dispatchEvent(new CustomEvent("step11-state-changed"));
}

function tasksResetMessages() {
  $("tasks-msg").textContent = "";
  $("tasks-status").textContent = "";
  const tel = $("tasks-llm-telemetry");
  tel.classList.add("hidden");
  tel.textContent = "";
}

// ---------------------------------------------------------------------------
// 新想法 / 问题（工单 idea-fix/02）：全局输入区 + 分析（分类）→ 落地
//（生成任务卡 / 直接修正 / 讨论转换）。不绑定任务卡——想法不一定是清单里的
// 任务；直接修正落地后受影响任务由后端标记 needs_redo（前端徽章 + 重做按钮）。
// ---------------------------------------------------------------------------

/** 分析想法（SSE idea_analyzing → idea_result → done）；autoLand 非空 =
 * 讨论漏斗转换（把 AI 建议文本重新分析，结果与目标一致时自动落地）。
 * 入口（按钮 / 转换按钮）统一走本函数——busy 守卫 + 状态行 + 结果卡渲染。 */
async function tasksIdeaAnalyze(sourceText, autoLand) {
  if (tasks.busy || ideaState.busy) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return false;
  }
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  const input = $("tasks-idea-input");
  const text = (sourceText || (input && input.value) || "").trim();
  if (!text) { $("tasks-idea-msg").textContent = "请先说你的想法或发现的问题（如「进弯道前先减速」）；或到 AI 建议区把『讨论』的建议转成落地动作"; return; }
  ideaSetBusy(true);
  $("tasks-idea-msg").textContent = "";
  $("tasks-status").textContent = "AI 分析想法中…";
  try {
    const data = await tasksRunSSE("/api/tasks/idea/analyze", { output_dir: dir, idea: text }, {
      idea_analyzing: () => { $("tasks-status").textContent = "AI 正在理解你的想法…（分钟级调用，请等待）"; },
      idea_result: () => { $("tasks-status").textContent = "分析完成——按结果卡选择落地方式"; },
      llm_telemetry: (d) => {
        const tel = $("tasks-llm-telemetry");
        tel.textContent = formatLLMTelemetry(d);
        tel.classList.remove("hidden");
        recordLLMUsage(d);
      },
    });
    ideaState.analysis = data.analysis || null;
    ideaState.ideaText = text;
    renderIdeaResult();
    if (autoLand === "new_task" && ideaState.analysis && ideaState.analysis.kind === "new_task") {
      await ideaInsertCore();
    } else if (autoLand === "direct_fix" && ideaState.analysis && ideaState.analysis.kind === "direct_fix") {
      await ideaFixCore();
    } else if (autoLand) {
      toast("info", "重新分析后与目标不一致——请按结果卡选择落地方式");
    } else {
      toast("ok", "已分析——按结果卡选择落地方式");
    }
    return true;   // 成功信号（工单 idea-suite/06：批量循环据此停止/继续）
  } catch (e) {
    $("tasks-idea-msg").textContent = e.message;
    $("tasks-status").textContent = "";
    return false;
  } finally {
    ideaSetBusy(false);
  }
}

/** 生成任务卡（前端按钮）：想法分析为 new_task → /api/tasks/idea/insert →
 * 清单整体替换重渲染（新卡出现在末尾）；落地后结果卡按钮区换「已生成」提示
 * 防重复插入（双点 = 两张重复卡）。 */
async function tasksIdeaInsert() {
  if (tasks.busy || ideaState.busy) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return;
  }
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-idea-msg").textContent = "";
  try {
    await ideaInsertCore();
  } finally {
    tasksSetBusy(false);
  }
}

async function ideaInsertCore() {
  const newTask = ideaState.analysis && ideaState.analysis.new_task;
  if (!newTask) {
    $("tasks-idea-msg").textContent = "当前分析没有可生成的任务卡——请重新分析";
    return;
  }
  const dir = tasks.outputDir || reviseGetDir();
  try {
    const data = await apiPost("/api/tasks/idea/insert", { output_dir: dir, new_task: newTask });
    tasks.outputDir = dir;
    tasks.plan = data.plan || tasks.plan;
    tasksRender();
    renderIdeaResult("已生成任务卡（新卡已在清单末尾）——可点「做这一步」执行");
    $("tasks-status").textContent = "已插入新任务卡——可点「做这一步」执行";
    toast("ok", "已生成任务卡");
  } catch (e) {
    $("tasks-idea-msg").textContent = e.message;
  }
}

/** 改动预览并执行（直接修正）：/api/tasks/idea/fix SSE（复用编译/报告词表）
 * → 结果面板（diff + 编译状态 + 回滚按钮）+ 受影响任务 needs_redo 徽章刷新
 *（重读磁盘清单——后端已落盘标记）。 */
async function tasksIdeaFix() {
  if (tasks.busy || ideaState.busy) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return;
  }
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-idea-msg").textContent = "";
  try {
    await ideaFixCore();
  } finally {
    tasksSetBusy(false);
  }
}

async function ideaFixCore() {
  const analysis = ideaState.analysis;
  if (!analysis) { $("tasks-idea-msg").textContent = "请先分析想法——结果卡出现后再点「改动预览并执行」"; return; }
  const dir = tasks.outputDir || reviseGetDir();
  $("tasks-status").textContent = "已开始修正：AI 修改 main.c 中…";
  try {
    const data = await tasksRunSSE("/api/tasks/idea/fix", {
      output_dir: dir,
      idea: ideaState.ideaText,
      fix_summary: analysis.fix_summary || "",
      affected_task_ids: analysis.affected_task_ids || [],
    }, {
      compile_start: () => { $("tasks-status").textContent = "编译中…"; },
      fix_start: () => { $("tasks-status").textContent = "AI 修复中…（首轮编译未过，自动修复一轮）"; },
      verify_result: () => { $("tasks-status").textContent = "验证结果收集中…"; },
      task_reporting: () => { $("tasks-status").textContent = "AI 正在总结本步（做了什么 / 接下来做什么）…"; },
      llm_telemetry: (d) => {
        const tel = $("tasks-llm-telemetry");
        tel.textContent = formatLLMTelemetry(d);
        tel.classList.remove("hidden");
        recordLLMUsage(d);
      },
    });
    // 修正成功：受影响任务 needs_redo 已由后端落盘——重读磁盘刷新徽章
    //（tasksReload → tasksRender 会清空网格，结果面板随后重建）
    await tasksReload();
    // 无任务清单的工程也能直接修正：网格容器默认隐藏（tasksRender 对空清单
    // 置 hidden）——结果面板要可见，故放开容器
    if (!tasks.plan) $("tasks-grid").classList.remove("hidden");
    renderIdeaFixResult(data);
    // 三态分流（spec 故事 4 / 验收 4：绿=已验证 / 无工具链=未验证 / 仍红=
    // failed——绿 toast + 红徽章自相矛盾是评审缺陷，按 status 给不同文案）
    if (data.status === "failed") {
      // 失败：不消费结果卡（按钮保留——可直接再点「改动预览并执行」重试），
      // 失败说明走错误消息区（error 色）
      renderIdeaResult();
      $("tasks-idea-msg").textContent = "修正未通过（编译仍红）——结果已写入 main.c（已备份，可回滚后重试）";
      $("tasks-status").textContent = "修正失败（编译仍红）——结果已写入 main.c，可回滚或重试";
      toast("error", "修正未通过（编译仍红）——已备份，可回滚或重试");
    } else if (data.status === "unverified") {
      renderIdeaResult("修正已落地（无工具链降级：未经编译验证）——受影响任务已标记「建议重做」");
      $("tasks-status").textContent = "修正完成（未经编译验证）——请配置工具链或上板人工确认";
      toast("info", "修正已落地——未经编译验证（无工具链降级）");
    } else {
      renderIdeaResult("修正已落地——受影响任务已标记「建议重做」，可逐卡重做");
      $("tasks-status").textContent = "修正完成——请查看结果面板（可回滚）与受影响任务";
      toast("ok", "修正已完成");
    }
  } catch (e) {
    $("tasks-idea-msg").textContent = e.message;
    $("tasks-status").textContent = "";
  }
}

/** 直接修正结果面板（对照任务执行结果面板；无 task 字段——修正不绑定任务
 * 卡，diff / 编译状态 / 备份回滚 / 步骤报告同形状）。 */
function renderIdeaFixResult(data) {
  const markup = verifyStatusMarkup(data, {
    unverified: "未检测到编译工具链：修正已写入 main.c，但未经编译验证——请配置工具链后手动编译，或上板后人工确认。",
    failed: "编译验证未通过，修正已写入 main.c（已备份，可回滚）。",
  });
  const sr = data.step_report || {};
  const backupId = data.backup_id || "";
  $("tasks-grid").insertAdjacentHTML("beforeend",
    '<div class="item" id="tasks-result" style="margin-top:10px">'
    + '<div class="head"><span class="slug">💡 直接修正结果</span> ' + markup.badge + "</div>"
    // 步骤报告：任务结果面板与直接修正结果面板共用同一纯函数（防两处各抄
    // 一份措辞漂移——评审整改 taskStepReportBlocksHTML 单源）
    + taskStepReportBlocksHTML(sr.what_changed || "", sr.user_action || "")
    + '<div class="reason">' + markup.detail + "</div>"
    + '<div class="reason">备份：<span class="slug">' + esc(backupId || "—") + "</span>"
    + (backupId ? ' · <button class="btn-task-rollback danger" data-backup="' + esc(backupId) + '">回滚本次修正</button>' : "")
    + "</div>"
    + mainDiffHTML(data.main_diff, "修正")
    + "</div>");
}

/** 讨论漏斗转换（工单 idea-fix/02）：把 AI 建议文本（analysis.reply）作为新
 * 想法重新分析——建议成形为可落地动作（new_task / direct_fix）后自动落地；
 * 结果仍为讨论 / 与目标不符 → 显示新结果卡让用户继续。 */
async function tasksIdeaConvert(target) {
  const analysis = ideaState.analysis;
  if (!analysis) return;
  const suggestion = (analysis.reply || "").trim();
  if (!suggestion) { $("tasks-idea-msg").textContent = "AI 建议为空——无法转换"; return; }
  if (target === "new_task" && analysis.kind === "new_task") { await tasksIdeaAnalyze(suggestion, "new_task"); return; }
  if (target === "direct_fix" && analysis.kind === "direct_fix") { await tasksIdeaAnalyze(suggestion, "direct_fix"); return; }
  await tasksIdeaAnalyze(suggestion, target);
}

/** 重做此步（工单 idea-fix/02）：受影响任务一键重做 = 重置 pending（转移表
 * 内合法转移）+ 清除 needs_redo 标记；随后可点「做这一步」走既有闭环。
 * pending 任务无需状态调用（只清标记）。 */
async function tasksRedoTask(taskId) {
  if (tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-msg").textContent = "";
  try {
    const task = ((tasks.plan || {}).tasks || []).find((t) => t.id === taskId);
    if (task && task.status !== "pending") {
      await apiPost("/api/tasks/status", { output_dir: dir, task_id: taskId, status: "pending" });
    }
    await apiPost("/api/tasks/idea/mark-redo", {
      output_dir: dir, task_ids: [taskId], needs_redo: false,
    });
    await tasksReload();
    toast("ok", "已重置为待做——点「做这一步」重新实现");
  } catch (e) {
    $("tasks-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
  }
}

// ---------------------------------------------------------------------------
// 全局工程级商量（工单 idea-suite/02）：多轮对话（不绑任务卡）——历史落盘
// /chat/read 加载、/chat/send 发送（成功才追加落盘）、/chat/adopt 采纳为
// 全局结论（后续每一步执行注入）；每条 AI 回复可「转成任务 / 转成修正」
//（复用 idea 漏斗通道 tasksIdeaAnalyze + autoLand）。纯函数渲染在 fx/task.js
//（globalChatHTML / globalNoteBadgeHTML），本层只喂状态 + 委托 + 跨簇重置。
// ---------------------------------------------------------------------------

/** 聊天区 / 徽标区渲染：开放时渲染聊天区（历史 + 输入行），关闭清空隐藏；
 * 徽标区按 chat.note 独立渲染（常驻聊天区外——收合时也能看到当前全局结论）；
 * 开关按钮文案随 open 切换。 */
function tasksGlobalRender() {
  const area = $("tasks-global-chat");
  if (area) {
    const html = globalChatHTML(chatState);
    area.innerHTML = html;
    area.classList.toggle("hidden", !chatState.open);
  }
  const note = $("tasks-global-note");
  if (note) {
    const noteHTML = globalNoteBadgeHTML((chatState.chat && chatState.chat.note) || "");
    note.innerHTML = noteHTML;
    note.classList.toggle("hidden", !noteHTML);
  }
  const btn = $("btn-tasks-global-chat");
  if (btn) btn.textContent = chatState.open ? "收起全局商量" : "全局商量（工程级）";
}

/** 读盘加载全局商量历史（chat 为空时展开调用）；无文件 = 空聊天（不 400）。 */
async function tasksChatLoad() {
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) throw new Error("请先在「修订」页签加载当前会话或历史目录");
  const data = await apiPost("/api/tasks/idea/chat/read", { output_dir: dir });
  chatState.chat = data.chat || { messages: [], note: "" };
}

/** 展开 / 收起全局商量区；首次展开读盘加载历史（失败回卷为收起 + 错误提示，
 * 防「空区展开」误导）。 */
async function tasksChatToggle() {
  if (chatState.busy || tasks.busy) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return;
  }
  const dir = tasks.outputDir || reviseGetDir();
  if (!chatState.open && !dir) {
    $("tasks-global-msg").textContent = "请先在「修订」页签加载当前会话或历史目录";
    return;
  }
  chatState.open = !chatState.open;
  if (chatState.open && !chatState.chat) {
    $("tasks-global-msg").textContent = "";
    try {
      await tasksChatLoad();
    } catch (e) {
      chatState.open = false;
      $("tasks-global-msg").textContent = e.message;
    }
  }
  tasksGlobalRender();
}

/** 发送一轮全局商量：历史单通道（history 含本轮 user 末条——与 /api/tasks/
 * discuss 同契约）；成功服务端落 user+assistant 两条并返回全量 chat → 替换
 * 本地缓存；失败 pending 撤出、draft 回填（用户可重试），历史不动。 */
async function tasksChatSend() {
  if (chatState.busy || tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-global-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  const input = $("tasks-global-chat-input");
  const message = ((input && input.value) || "").trim();
  if (!message) {
    $("tasks-global-msg").textContent = "请先说你的问题（如「整体架构要不要加滤波？」）";
    return;
  }
  const history = ((chatState.chat && chatState.chat.messages) || [])
    .map((m) => ({ role: m.role, content: m.content }));
  history.push({ role: "user", content: message });
  chatState.pending = message;
  chatState.draft = "";
  chatState.busy = true;
  $("tasks-global-msg").textContent = "";
  $("tasks-status").textContent = "全局商量：AI 回应中…（分钟级调用，请等待）";
  tasksGlobalRender();
  try {
    const data = await apiPost("/api/tasks/idea/chat/send", { output_dir: dir, history });
    chatState.chat = data.chat || chatState.chat;
    $("tasks-status").textContent = "";
    toast("ok", "已回应——可继续聊，或把回复转成任务/修正、采纳为全局结论");
  } catch (e) {
    chatState.draft = message;   // 失败回填：历史不动（后端原子轮次），重试免重打
    $("tasks-status").textContent = "";
    $("tasks-global-msg").textContent = e.message;
  } finally {
    chatState.pending = "";
    chatState.busy = false;
    tasksGlobalRender();
  }
}

/** 采纳 / 清除全局结论（/chat/adopt：text 空串 = 清除）→ 徽标区更新。
 * chatState.busy 守卫：发送轮进行中禁用（防与 send 读写同一文件的竞态——
 * 两侧都做读改写的 lost update）。 */
async function tasksChatAdopt(text) {
  if (chatState.busy || tasks.busy) {
    toast("info", "全局商量回应中，请等当前一轮完成后再操作");
    return;
  }
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-global-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-global-msg").textContent = "";
  try {
    const data = await apiPost("/api/tasks/idea/chat/adopt", {
      output_dir: dir, text: text || "",
    });
    if (data.chat) chatState.chat = data.chat;
    tasksGlobalRender();
    toast("ok", text ? "已采纳为全局结论——后续每一步执行都会注入该结论"
      : "已清除全局结论");
  } catch (e) {
    $("tasks-global-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
  }
}

/** 把某条 AI 回复转成落地动作（讨论漏斗同款）：回复文本作为新想法重新分析，
 * 结果与目标一致时自动落地（生成任务卡 / 直接修正）。chatState.busy 守卫同
 * adopt——发送轮进行中不另起分析（两条 LLM 流并行易混淆，且落地基于的语境
 * 可能还没落盘）。 */
function tasksChatConvert(action, text) {
  if (chatState.busy) {
    toast("info", "全局商量回应中，请等当前一轮完成后再操作");
    return;
  }
  if (action === "task") { tasksIdeaAnalyze(text, "new_task"); return; }
  tasksIdeaAnalyze(text, "direct_fix");
}

/** 全局商量区重置（跨簇目录切换 / 清单作废）：关区清状态 + 清容器 +
 * 按钮文案回默认。 */
function resetGlobalChatArea() {
  chatState.busy = false;
  chatState.open = false;
  chatState.chat = null;
  chatState.pending = "";
  chatState.draft = "";
  const area = $("tasks-global-chat");
  if (area) { area.innerHTML = ""; area.classList.add("hidden"); }
  const note = $("tasks-global-note");
  if (note) { note.innerHTML = ""; note.classList.add("hidden"); }
  const msg = $("tasks-global-msg");
  if (msg) msg.textContent = "";
  const btn = $("btn-tasks-global-chat");
  if (btn) btn.textContent = "全局商量（工程级）";
}

// ---------------------------------------------------------------------------
// 想法草稿箱（工单 idea-suite/06）：输入区「存入草稿」→ /drafts/add；
// 列表 = /drafts/read（随 tasksReload 的目录加载一起读回）；「分析这条」=
// tasksIdeaAnalyze（复用想法漏斗）；「删除」= /drafts/delete；「全部逐条
// 分析」= 顺序串行循环 + 状态行进度（第 N/总）。纯函数渲染 fx/task.js
// ideaDraftListHTML，本层做状态 / 委托 / 跨簇重置。
// ---------------------------------------------------------------------------

function tasksDraftsRender() {
  const box = $("tasks-drafts");
  if (!box) return;
  box.innerHTML = ideaDraftListHTML(draftState.drafts || [], { busy: draftState.busy });
}

/** 读盘加载草稿（目录加载 / 增删后刷新）；失败静默（不清旧展示，错误留给
 * 下一次操作提示——照 tasksReload 哲学）。 */
async function tasksDraftsLoad() {
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) return;
  try {
    const data = await apiPost("/api/tasks/idea/drafts/read", { output_dir: dir });
    draftState.drafts = data.drafts || [];
    tasksDraftsRender();
  } catch (e) {
    // 读取失败（目录没了 / 坏 JSON）：保留旧展示，不打断当前流程
  }
}

/** 存入草稿：idea 输入框原文 → POST add（去重由后端——同文本不重复插入）
 * → 成功后清空输入框（内容已进草稿，不占输入区）。 */
async function tasksDraftAdd() {
  if (draftState.busy || tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-drafts-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  const input = $("tasks-idea-input");
  const text = ((input && input.value) || "").trim();
  if (!text) {
    $("tasks-drafts-msg").textContent = "先在上方输入框写下想法，再点「存入草稿」";
    return;
  }
  draftState.busy = true;
  tasksDraftsRender();
  $("tasks-drafts-msg").textContent = "";
  tasksSetBusy(true);   // 与想法分析共用 tasks.busy 闸（增删进行中禁并发分析）
  try {
    const data = await apiPost("/api/tasks/idea/drafts/add", {
      output_dir: dir, text,
    });
    draftState.drafts = data.drafts || [];
    if (input) input.value = "";
    tasksDraftsRender();
    toast("ok", "已存入草稿——可继续输入下一条，回头再分析");
  } catch (e) {
    $("tasks-drafts-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
    draftState.busy = false;
    tasksDraftsRender();
  }
}

/** 删除一条草稿（后端未知 id 幂等；删除后即时刷新列表）。 */
async function tasksDraftDelete(id) {
  if (draftState.busy || tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-drafts-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  draftState.busy = true;
  tasksDraftsRender();
  tasksSetBusy(true);   // 与想法分析共用 tasks.busy 闸（删除进行中禁并发分析）
  try {
    const data = await apiPost("/api/tasks/idea/drafts/delete", {
      output_dir: dir, id,
    });
    draftState.drafts = data.drafts || [];
    tasksDraftsRender();
    toast("ok", "已删除草稿");
  } catch (e) {
    $("tasks-drafts-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
    draftState.busy = false;
    tasksDraftsRender();
  }
}

/** 分析一条草稿（复用想法漏斗：结果卡在想法区出现，可落地 / 继续讨论）。
 * 异步包装：期间 draftState.busy = true → 删除/全部按钮禁用（防并发——
 * 否则批处理会被 ideaState.busy 守卫空转还误报成功）。 */
async function tasksDraftAnalyze(text) {
  if (draftState.busy) {
    toast("info", "有草稿操作进行中，请等当前操作完成后再试");
    return;
  }
  draftState.busy = true;
  tasksDraftsRender();
  try {
    await tasksIdeaAnalyze(text);
  } finally {
    draftState.busy = false;
    tasksDraftsRender();
  }
}

/** 全部逐条分析：快照当前列表 → 顺序串行（每条 = 一轮 LLM 分析，分钟级——
 * 逐条才有进度意义）；状态行「分析中 第 N/总：<前 20 字>」；某条失败即停
 * （剩余草稿可再点「全部逐条分析」重试——按钮在 finally 恢复）。 */
async function tasksDraftAnalyzeAll() {
  if (draftState.busy || tasks.busy) {
    toast("info", "有流程正在进行，请等当前操作完成后再试");
    return;
  }
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-idea-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  const list = (draftState.drafts || []).slice();
  if (!list.length) {
    $("tasks-drafts-msg").textContent = "没有草稿可分析——先「存入草稿」";
    return;
  }
  draftState.busy = true;
  tasksDraftsRender();
  const statusEl = $("tasks-drafts-status");
  try {
    for (let i = 0; i < list.length; i++) {
      const item = list[i];
      if (!item || !item.text) continue;
      if (statusEl) {
        statusEl.textContent = "分析中 第 " + (i + 1) + "/" + list.length
          + "：" + truncate(item.text, 20);
      }
      const ok = await tasksIdeaAnalyze(item.text);
      if (!ok) {
        // 本轮分析失败或未真正开始（tasksIdeaAnalyze 早已把原因写进
        // tasks-idea-msg）：停止批量——剩余草稿可再点「全部逐条分析」重试
        throw new Error("第 " + (i + 1) + " 条分析失败（详见上方想法区提示）");
      }
    }
    if (statusEl) statusEl.textContent = "全部草稿已分析完（结果卡为最后一条）——可按结果卡落地";
    toast("ok", "全部草稿已分析");
  } catch (e) {
    if (statusEl) statusEl.textContent = "";
    $("tasks-drafts-msg").textContent = "分析中断：" + e.message
      + "——可再点「全部逐条分析」继续剩余草稿";
    toast("error", "分析中断（详见下方提示）");
  } finally {
    draftState.busy = false;
    tasksDraftsRender();
  }
}

/** 草稿区重置（跨簇目录切换 / 清单作废）：清状态与容器（目录变了，草稿是
 * 另一个工程的）。 */
function resetDraftsArea() {
  draftState.busy = false;
  draftState.drafts = null;
  const box = $("tasks-drafts");
  if (box) box.innerHTML = "";
  const msg = $("tasks-drafts-msg");
  if (msg) msg.textContent = "";
  const status = $("tasks-drafts-status");
  if (status) status.textContent = "";
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
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
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
    taskEditOpen.clear();   // 新清单 = 新任务集：旧编辑态（按 id 记忆）全部作废
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

/** 下一步引导（工单 step-next-guide/01）：执行成功（done）后——当前卡内插入
 * 「下一步 → tN：标题」提示行（fx/task.js 纯函数生成，含转义）；下一张待执行卡
 * （清单顺序上当前卡之后第一个 pending/failed）滚动到视口中央 + 描边高亮 2.4s
 * （2.6s 后移除类）。瞬态：grid 下一次重渲染 / 清单重载时提示自然消失，不落盘。
 * 无剩余待执行 = 不提示不滚动。 */
function guideNextTask(taskId) {
  const next = nextTaskHint(tasks.plan, taskId);
  if (!next) return;
  const grid = $("tasks-grid");
  // taskId 为后端生成 id（实测 t1/t4 形式），仍按 CSS.escape 收敛——评审整改：
  // 直接拼接未转义 id 进 attr 选择器，id 含引号/反斜杠会抛 SyntaxError
  const sel = (id) => '[data-task-id="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]';
  const card = grid && grid.querySelector(sel(taskId));
  if (card) card.insertAdjacentHTML("beforeend", taskNextHintHTML(tasks.plan, taskId));
  const nextCard = grid && grid.querySelector(sel(next.id));
  if (!nextCard) return;
  nextCard.scrollIntoView({ behavior: "smooth", block: "center" });
  nextCard.classList.add("task-card-highlight");
  // 瞬态高亮：2.6s 后移除（节点已分离时 classList.remove 为无害 no-op）
  setTimeout(() => { if (nextCard.isConnected) nextCard.classList.remove("task-card-highlight"); }, 2600);
}

/** 单任务执行（工单 02 + task-feedback/02）：读补充框 → SSE（feedback 非空 =
 * 上板反馈轮）→ 状态回填渲染 + 结果面板。 */
async function tasksExecute(taskId, feedback) {
  if (tasks.busy) {
    // 工单 05：busy 静默吞点击 = 用户以为没反应——给显式提示
    toast("info", "有任务正在执行中，请等当前任务完成后再操作");
    return;
  }
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  const note = ($("task-note-" + taskId) || {}).value || "";
  tasksSetBusy(true);
  tasksResetMessages();
  // 即时可见反馈（工单 05）：点击即置「进行中」并重渲染，卡片立刻有反应
  setTaskStatusLocal(taskId, "doing");
  tasksRender();
  const noteEl = $("task-note-" + taskId);   // 重渲染会清掉补充框，回填已读取的内容
  if (noteEl && note) noteEl.value = note;
  $("tasks-status").textContent = "已开始执行：AI 实现本任务中…";
  try {
    const body = { output_dir: dir, task_id: taskId, note: note };
    if (feedback) body.feedback = feedback;
    const data = await tasksRunSSE("/api/tasks/execute", body, {
      task_executing: () => { $("tasks-status").textContent = "AI 实现本任务中…（分钟级调用，请等待）"; },
      compile_start: () => { $("tasks-status").textContent = "编译中…"; },
      fix_start: () => { $("tasks-status").textContent = "AI 修复中…（首轮编译未过，自动修复一轮）"; },
      verify_result: () => { $("tasks-status").textContent = "验证结果收集中…"; },
      task_reporting: () => { $("tasks-status").textContent = "AI 正在总结本步（做了什么 / 接下来做什么）…"; },
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
    // 下一步引导（工单 step-next-guide/01）：做完一步 → 当前卡提示「下一步 →
    // tN：标题」+ 滚动高亮下一张待执行卡（瞬态；失败轮不引导——还在本卡）
    if (data.status !== "failed") guideNextTask(taskId);
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
    // 工单 05：失败路径后端会恢复 previous 状态落盘——重读磁盘刷新卡（乐观 doing
    // 与磁盘不一致会误导用户）
    await tasksReload();
  } finally {
    tasksSetBusy(false);
  }
}

/** 上板自检清单勾选态（工单 task-insight/02）：localStorage 备忘（key 单源
 * = fx/task.js checklistStateKey——firstep.checklist.v1.<taskId>/<seq>，值
 * = {序号: true} JSON）——纯前端个人备忘，不落 .contest_tasks.json、不影响
 * 状态机（spec 决策）。读失败降级空对象（私密模式等）。 */
function checklistRead(taskId, seq) {
  try {
    const raw = localStorage.getItem(checklistStateKey(taskId, seq));
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (e) {
    return {};
  }
}

function checklistWrite(taskId, seq, checkedMap) {
  try {
    localStorage.setItem(checklistStateKey(taskId, seq), JSON.stringify(checkedMap));
  } catch (e) {
    // 写失败（配额 / 私密模式）：备忘录降级为会话内——不阻断任务流程
  }
}

/** 任务执行结果面板（照深化结果卡先例）：状态徽章 + 编译摘要 + diff + 备份 +
 * 回滚按钮（复用 /api/revise/rollback，同备份族——backup_tree 同盘）。
 * 插入位置 = tasks-grid 容器内（beforeend）而非 afterend：结果面板的操作按钮
 * （回滚 / 烧录）必须落在网格的点击委托覆盖范围内——afterend 是网格的兄弟
 * 节点，冒泡不过网格，回滚按钮点击将无人处理（工单 flash-deploy/02 修）。
 * 徽章 + 摘要文案单源 = fx/task.js verifyStatusMarkup（与深化面板共用）。 */
function tasksRenderResult(taskId, data) {
  const markup = verifyStatusMarkup(data, {
    unverified: "未检测到编译工具链：任务结果已写入 main.c，但未经编译验证——请配置工具链后手动编译，或上板后人工标记为已验证。",
    failed: "编译验证未通过，任务结果已写入 main.c（已备份，可回滚）。",
  });
  const task = data.task || {};
  const backupId = data.backup_id || "";
  const dir = tasks.outputDir || "";
  // 反馈轮提示：最近一轮若是上板反馈，把用户反馈原文展示在结果面板（追溯）
  // ——纯函数单源 fx/task.js taskLatestFeedbackNote（评审整改：胶水层不拼 HTML）
  const feedbackNote = taskLatestFeedbackNote(task);
  // 步骤报告（工单 stepwise-deepen/02 + task-insight/02）：AI 本步「做了什么 +
  // 接下来你要做什么」（含接线/上板指引）+ 上板自检清单（最新轮 checklist，
  // 勾选态 localStorage 备忘——key = taskId+"/"+seq）；降级空串由纯函数侧渲染
  // 中文兜底。checklist 勾选变化经 change 委托写盘（本函数只读盘渲染快照）。
  const iterations = task.iterations || [];
  const lastIter = iterations.length ? iterations[iterations.length - 1] : null;
  const checkKey = (task.id && lastIter && lastIter.seq !== undefined)
    ? task.id + "/" + lastIter.seq : "";
  const stepReport = taskStepReportHTML(task, {
    checkKey,
    checkedMap: checkKey ? checklistRead(task.id, lastIter.seq) : {},
  });
  $("tasks-grid").insertAdjacentHTML("beforeend",
    '<div class="item" id="tasks-result" style="margin-top:10px">'
    + '<div class="head"><span class="slug">' + esc(task.id || taskId) + " · " + esc(task.title || "") + " 执行结果</span> " + markup.badge + "</div>"
    + feedbackNote
    + '<div class="reason">' + markup.detail + "</div>"
    + taskErrorsHTML((data.compile && data.compile.parsed_errors) || [])  // 编译错误行跳转（error-jump-task/02）：main.c 行可点高亮
    + stepReport
    + '<div class="reason">备份：<span class="slug">' + esc(backupId || "—") + "</span>"
    + (backupId ? ' · <button class="btn-task-rollback danger" data-backup="' + esc(backupId) + '" data-task="' + esc(task.id || taskId) + '">回滚到本任务执行前</button>' : "")
    + "</div>"
    + flashPanelHTML(dir)  // uid 缺省 "result"——结果面板烧录行；任务卡另有 task.id 容器（flash-step-button/01），并存互不干扰
    + mainDiffHTML(data.main_diff, "任务")
    + "</div>");
}

/** 烧录到板子（工单 flash-deploy/02 + flash-step-button/01）：结果面板一键
 * 烧录——执行体共享 ui/flash.js flashRunShared（POST /api/flash →
 * flashResultHTML / 400 → flashGuideHTML）；本簇只做 busy 守卫（tasks.busy
 * 全局闸，防与任务执行/回滚并发）。uid = 容器标识（缺省 "result" = 执行结果
 * 面板；任务卡传 task.id → 卡内独立状态/结果位）；dir 优先取按钮 data-dir
 *（渲染时快照），空则回退 tasks.outputDir（同目录真相）。 */
async function tasksFlash(uid, dir) {
  if (tasks.busy) {
    toast("info", "有任务正在执行中，请等当前任务完成后再操作");
    return;
  }
  // 容器 id 单源 = fx/flash.js flashContainer（评审整改：与 flashPanelHTML
  // 共用契约，防两端手写 id 形态漂移后被下面 !statusEl 静默吞掉；缺省 uid
  // "result" 也在单源内）
  const ids = flashContainer(uid);
  const statusEl = $(ids.statusId);
  const resultEl = $(ids.resultId);
  if (!statusEl || !resultEl) return;  // 容器已随渲染清除：无处渲染，静默退出
  await flashRunShared({
    dir: dir || tasks.outputDir || "",
    statusEl,
    resultEl,
    setBusy: tasksSetBusy,
  });
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
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
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
    tasksDraftsLoad();   // 目录加载 → 草稿随读（后端无文件 = []，静默）
  } catch (e) {
    // 读取失败（清单损坏 / 目录没了）：不清空旧展示，错误留给下一次操作提示
  }
}

/** 人工改标（工单 03）：跳过 / 恢复 / 重做 / 上板改标 → 落盘 + 单卡重渲染。
 * okMessage = 成功 toast 文案（缺省「状态已更新」；工单 stuck-doing-recover/01
 * 恢复入口传专属文案）。 */
async function tasksSetStatus(taskId, status, okMessage = "状态已更新") {
  if (tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
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
    toast("ok", okMessage);
  } catch (e) {
    // 后端中文（含非法转移提示 / 正在执行中拒绝）——task-msg 常驻 + toast
    // 双通道；tasksReload 回填磁盘真相（恢复失败时磁盘状态才是权威——防
    // 客户端内存态与磁盘分叉，spec 轴评审整改：恢复失败路径同回填）
    $("tasks-msg").textContent = e.message;
    toast("error", e.message);
    await tasksReload();
  } finally {
    tasksSetBusy(false);
  }
}

/** 执行中断恢复（工单 stuck-doing-recover/01）：僵尸 doing 卡 → 恢复为待做
 * （走既有 /api/tasks/status 转移校验；真实执行中的拦截 = 后端注册表 400，
 * 错误 message 落 tasks-msg 提示等待完成）。恢复只改状态——main.c / 备份 /
 * 轮次全保留，重做走既有闭环。 */
function tasksRecover(taskId) {
  tasksSetStatus(taskId, "pending", "已恢复为待做——可重新点「做这一步」");
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
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
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

// ---------------------------------------------------------------------------
// 每卡「和 AI 商量」对话区（工单 task-chat/03）：展开/收起 → 发消息 →
// /api/tasks/discuss 一轮回应 → 采纳某条 AI 回复（/api/tasks/dialog-adopt）
// → 任务卡徽标 + 下次执行注入。
// ---------------------------------------------------------------------------

function tasksDialogToggle(taskId) {
  const st = taskDialogState(taskId);
  st.open = !st.open;
  tasksRender();
}

async function tasksDialogSend(taskId) {
  const st = taskDialogState(taskId);
  if (st.busy || tasks.busy) return;
  const input = $("task-dialog-input-" + taskId);
  const message = (input && input.value || "").trim();
  if (!message) { $("tasks-msg").textContent = "请先说你的想法或纠正（如「左轮不转，改成脉冲式」）"; return; }
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  // 用户消息入历史后再发（历史含本条——后端 prompt 以 history[-1] 为最新消息，
  // 单通道：无独立 message 参数，评审整改——分离 message 与 history 会丢消息）
  st.history.push({ role: "user", content: message });
  st.draft = "";
  st.busy = true;
  $("tasks-msg").textContent = "";
  tasksRender();
  try {
    const data = await apiPost("/api/tasks/discuss", {
      output_dir: dir,
      task_id: taskId,
      history: st.history.map((m) => ({ role: m.role, content: m.content })),
    });
    st.history.push({ role: "assistant", content: data.reply || "" });
    $("tasks-status").textContent = "";
    toast("ok", "已回应——可继续聊，或点「采纳这条结论」");
  } catch (e) {
    // 失败：用户消息撤出历史（本轮未成功对话，留一条孤消息误导后续轮次）
    st.history.pop();
    $("tasks-status").textContent = "";
    $("tasks-msg").textContent = e.message;
  } finally {
    st.busy = false;
    tasksRender();
  }
}

/** 采纳某条 AI 回复为对话结论（idx = 该条在历史中的下标；非 assistant 行
 * 拒绝——采纳语义 = 采纳 AI 的确认/修正结论）。 */
async function tasksDialogAdopt(taskId, idx) {
  if (tasks.busy) return;
  const st = taskDialogState(taskId);
  const entry = st.history[Number(idx)];
  if (!entry || entry.role !== "assistant" || !entry.content) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-msg").textContent = "";
  try {
    const data = await apiPost("/api/tasks/dialog-adopt", {
      output_dir: dir, task_id: taskId, text: entry.content,
    });
    if (tasks.plan && tasks.plan.tasks) {
      tasks.plan.tasks = tasks.plan.tasks.map((t) => t.id === taskId ? data.task : t);
    }
    tasksRender();
    toast("ok", "已采纳——「做这一步」时将按此结论实现");
  } catch (e) {
    $("tasks-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
  }
}

async function tasksDialogClear(taskId) {
  if (tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-msg").textContent = "";
  try {
    const data = await apiPost("/api/tasks/dialog-adopt", {
      output_dir: dir, task_id: taskId, text: "",
    });
    if (tasks.plan && tasks.plan.tasks) {
      tasks.plan.tasks = tasks.plan.tasks.map((t) => t.id === taskId ? data.task : t);
    }
    tasksRender();
    toast("ok", "已取消采纳");
  } catch (e) {
    $("tasks-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
  }
}

// ---------------------------------------------------------------------------
// 任务卡微编辑 + 调序（工单 idea-suite/04，收编为「⋯ 更多」下拉）：
// 菜单项「编辑任务信息」（卡内表单，当前值回填 → /api/tasks/idea/edit）+
// 「上移/下移」（→ /api/tasks/idea/move，换序即时生效，id 不变）。
// 编辑态 = taskEditOpen（会话级 Set，跨簇重置清空）；表单纯函数在
// fx/task.js（taskEditFormHTML / taskMoreMenuHTML），本层只做收集 + 委托。
// ---------------------------------------------------------------------------

const taskEditOpen = new Set();

function tasksEditToggle(taskId) {
  if (tasks.busy) {
    toast("info", "有任务正在进行，请等当前操作完成后再试");
    return;
  }
  if (taskEditOpen.has(taskId)) taskEditOpen.delete(taskId);
  else taskEditOpen.add(taskId);
  tasksRender();
}

function tasksEditCancel(taskId) {
  taskEditOpen.delete(taskId);
  tasksRender();
}

/** 保存编辑：收集表单字段 → 后端校验（非法 400 中文原样展示）→ 整清单替换
 * 重渲染（状态/轮次历史由后端保留——微编辑不动进度）。依赖文本 = 逗号分隔
 * 序号 → 数组；本地先验非法（非正整数）拦截，少一次往返。 */
async function tasksEditSave(taskId) {
  if (tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  const title = (($("task-edit-title-" + taskId) || {}).value || "").trim();
  const description = (($("task-edit-desc-" + taskId) || {}).value || "").trim();
  const depsText = (($("task-edit-deps-" + taskId) || {}).value || "").trim();
  const verify = (($("task-edit-verify-" + taskId) || {}).value || "");
  const refsText = (($("task-edit-refs-" + taskId) || {}).value || "").trim();
  if (!title) { $("tasks-msg").textContent = "标题不能为空"; return; }
  if (!description) { $("tasks-msg").textContent = "描述不能为空"; return; }
  const depsParts = depsText ? depsText.split(/[,，、]+/).map((s) => s.trim()).filter(Boolean) : [];
  if (depsParts.some((s) => !/^\d+$/.test(s) || Number(s) < 1)) {
    $("tasks-msg").textContent = "依赖必须是正整数序号（1 起，逗号分隔）——如「1, 3」";
    return;
  }
  const totalSteps = ((tasks.plan || {}).tasks || []).length;
  if (depsParts.some((s) => Number(s) > totalSteps)) {
    $("tasks-msg").textContent = "依赖序号越界（清单只有 " + totalSteps + " 步）";
    return;
  }
  const scoreRefs = refsText ? refsText.split(/[,，、]+/).map((s) => s.trim()).filter(Boolean) : [];
  const fields = {
    title,
    description,
    depends_on: depsParts.map(Number),
    verify,
    score_refs: scoreRefs,
  };
  tasksSetBusy(true);
  $("tasks-msg").textContent = "";
  try {
    const data = await apiPost("/api/tasks/idea/edit", {
      output_dir: dir, task_id: taskId, fields,
    });
    taskEditOpen.delete(taskId);
    tasks.plan = data.plan || tasks.plan;
    tasksRender();
    toast("ok", "已保存任务卡");
  } catch (e) {
    $("tasks-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
  }
}

/** 上移 / 下移换序（后端相邻换位，id 不变——依赖引用与 needs_redo 不受影响）；
 * 边界双保险：前端按钮 disabled（纯函数侧渲染）+ 后端 400（纯函数也拒）。 */
async function tasksMove(taskId, direction) {
  if (tasks.busy) return;
  const dir = tasks.outputDir || reviseGetDir();
  if (!dir) { $("tasks-msg").textContent = "请先在「修订」页签加载当前会话或历史目录"; return; }
  tasksSetBusy(true);
  $("tasks-msg").textContent = "";
  try {
    const data = await apiPost("/api/tasks/idea/move", {
      output_dir: dir, task_id: taskId, direction,
    });
    tasks.plan = data.plan || tasks.plan;
    tasksRender();
    toast("ok", direction === "up" ? "已上移（顺序已更新）" : "已下移（顺序已更新）");
  } catch (e) {
    $("tasks-msg").textContent = e.message;
  } finally {
    tasksSetBusy(false);
  }
}

$("btn-tasks-plan").addEventListener("click", () => tasksPlan(false));
$("btn-tasks-replan").addEventListener("click", () => tasksPlan(true));
// 新想法 / 问题（工单 idea-fix/02）：分析按钮 + 结果卡落地按钮委托
$("btn-tasks-idea").addEventListener("click", () => tasksIdeaAnalyze());
// 全局商量（工单 idea-suite/02）：开关按钮 + 区内委托（发送 / 转任务 / 转修正 /
// 采纳——采纳与清除按钮在聊天区与徽标区两处，委托挂 tasks-box 一并覆盖）
$("btn-tasks-global-chat").addEventListener("click", () => tasksChatToggle());
$("tasks-box").addEventListener("click", (event) => {
  const send = event.target.closest(".btn-global-chat-send");
  if (send) { tasksChatSend(); return; }
  const action = event.target.closest(".btn-global-chat-action");
  if (!action) return;
  const kind = action.dataset.globalAction;
  if (kind === "clear") { tasksChatAdopt(""); return; }
  if (kind === "adopt") { tasksChatAdopt(action.dataset.globalText); return; }
  tasksChatConvert(kind, action.dataset.globalText);
});
// 草稿箱（工单 idea-suite/06）：存入草稿按钮 + 区内委托（分析这条 / 删除 /
// 全部逐条分析——同样挂 tasks-box，只认 .btn-draft-*）
$("btn-tasks-draft-add").addEventListener("click", () => tasksDraftAdd());
$("tasks-box").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-draft-analyze, .btn-draft-delete, .btn-draft-all");
  if (!btn) return;
  const action = btn.dataset.draftAction;
  if (action === "analyze") { tasksDraftAnalyze(btn.dataset.draftText); return; }
  if (action === "delete") { tasksDraftDelete(btn.dataset.draftId); return; }
  tasksDraftAnalyzeAll();
});
$("tasks-idea-result").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-idea-insert, .btn-idea-fix, .btn-idea-to-task, .btn-idea-to-fix");
  if (!btn) return;
  const kind = btn.dataset.ideaKind;
  if (kind === "new_task") { tasksIdeaInsert(); return; }
  if (kind === "direct_fix") { tasksIdeaFix(); return; }
  if (btn.classList.contains("btn-idea-to-task")) { tasksIdeaConvert("new_task"); return; }
  tasksIdeaConvert("direct_fix");
});
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
// 任务卡状态按钮（跳过 / 恢复 / 重做 / 上板改标 / 执行中断恢复）
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-skip, .btn-task-revert, .btn-task-mark, .btn-task-redo, .btn-task-recover");
  if (!btn) return;
  if (btn.classList.contains("btn-task-redo")) {
    tasksRedoTask(btn.dataset.task);
    return;
  }
  if (btn.classList.contains("btn-task-recover")) {
    tasksRecover(btn.dataset.task);
    return;
  }
  const status = btn.classList.contains("btn-task-skip") ? "skipped"
    : btn.classList.contains("btn-task-mark") ? "verified" : "pending";
  tasksSetStatus(btn.dataset.task, status);
});
// 任务卡微编辑 + 调序（工单 idea-suite/04，收编为「⋯ 更多」下拉）：菜单项
// 点击先收起 details（open=false）再派发动作——动作成功后 tasksRender 重建
// 网格本就默认收起，此收尾管 busy 拦截（toast）等不重渲染的路径。
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-edit, .btn-task-edit-save, .btn-task-edit-cancel, .btn-task-move");
  if (!btn) return;
  const menu = btn.closest(".task-more-details");
  if (menu) menu.open = false;
  const taskId = btn.dataset.task;
  const action = btn.dataset.taskAction;
  if (action === "edit") { tasksEditToggle(taskId); return; }
  if (action === "edit-save") { tasksEditSave(taskId); return; }
  if (action === "edit-cancel") { tasksEditCancel(taskId); return; }
  tasksMove(taskId, action === "move-up" ? "up" : "down");
});
// 「⋯ 更多」菜单（收编 idea-suite/04）：点击菜单外任意处收起；summary 原生
// toggle 不受影响（目标在任一 details 内则跳过——同开一菜单、点外部全收）。
document.addEventListener("click", (event) => {
  const wins = document.querySelectorAll(".task-more-details[open]");
  if (!wins.length) return;
  wins.forEach((d) => {
    if (!d.contains(event.target)) d.open = false;
  });
});
// 结果面板「回滚到本任务执行前」（同备份族，复用 /api/revise/rollback）
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-rollback");
  if (!btn) return;
  tasksRollback(btn.dataset.backup, btn.dataset.task);
});
// 编译错误行跳转 main.c（工单 error-jump-task/02）：跳转单源 = fx/code.js
// maincJumpToLine（返回错误码，toast 在本层——原修复中心三条消息逐字保留）
$("tasks-grid").addEventListener("click", (event) => {
  const span = event.target.closest(".task-err-jump");
  if (!span) return;
  const reason = maincJumpToLine(Number(span.dataset.line));
  if (reason === "empty") toast("info", "main.c 还没有内容，先「生成骨架」再跳转");
  else if (reason === "out-of-range") toast("info", "行号超出 main.c 范围：" + span.dataset.line);
});
// 任务卡 / 结果面板「烧录到板子」（工单 flash-deploy/02 + flash-step-button/01）：
// 两类入口同域委托——按钮 data-task-flash = 容器 uid（任务卡 = task.id，结果
// 面板 = "result"——缺省兼容），data-dir = 渲染时目录快照（任务卡 = tasksRender
// 抓取 tasks.outputDir，结果面板 = 结果面板渲染时快照，两者同为快照语义）；
// click 后各自写入自己的状态/结果容器，互不干扰
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-flash");
  if (!btn) return;
  tasksFlash(btn.dataset.taskFlash, btn.dataset.dir);
});
// 轮次历史「回到这轮之前」（工单 task-feedback/03：撤销语义）
$("tasks-grid").addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-task-iteration-rollback");
  if (!btn) return;
  tasksRollbackIteration(btn.dataset.task, btn.dataset.seq);
});
// 每卡对话（工单 task-chat/03）：展开/收起 → 发送 → 采纳 → 取消采纳
$("tasks-grid").addEventListener("click", (event) => {
  const toggle = event.target.closest(".btn-task-dialog");
  if (toggle) { tasksDialogToggle(toggle.dataset.task); return; }
  const send = event.target.closest(".btn-task-dialog-send");
  if (send) { tasksDialogSend(send.dataset.task); return; }
  const adopt = event.target.closest(".btn-task-dialog-adopt");
  if (adopt) { tasksDialogAdopt(adopt.dataset.task, adopt.dataset.idx); return; }
  const clear = event.target.closest(".btn-task-dialog-clear");
  if (clear) tasksDialogClear(clear.dataset.task);
});
// 上板自检清单勾选（工单 task-insight/02）：change 委托（checkbox 勾选不触发
// click 委托分支）——写 localStorage 备忘，不重渲染（DOM 态已由浏览器更新）
$("tasks-grid").addEventListener("change", (event) => {
  const input = event.target.closest ? event.target.closest(".task-check-input") : null;
  if (!input) return;
  const key = input.dataset.checkKey;
  const idx = Number(input.dataset.checkIdx);
  if (!key || Number.isNaN(idx)) return;
  const parts = key.split("/");
  if (parts.length !== 2) return;
  const [taskId, seq] = parts;
  const map = checklistRead(taskId, seq);
  if (input.checked) map[idx] = true;
  else delete map[idx];
  checklistWrite(taskId, seq, map);
});
// 清空任务面板（保留类名容器状态；评审整改：两处跨簇重置与 tasksRender 的
// 隐藏逻辑收敛——曾三处手写相同的 overview/resources 清空块，漂移即漏清）
function clearTasksPanel() {
  $("tasks-grid").classList.add("hidden");
  $("tasks-grid").innerHTML = "";
  const overview = $("tasks-overview");
  if (overview) { overview.innerHTML = ""; overview.classList.add("hidden"); }
  const resBox = $("tasks-resources");
  if (resBox) { resBox.innerHTML = ""; resBox.classList.add("hidden"); }
  $("tasks-progress").textContent = "";
  $("btn-tasks-replan").classList.add("hidden");
  updateTasksEmptyHint();
  // 状态徽章（step11-tabs-ui/02）：清空路径未走 tasksRender，也要广播重置快照
  window.dispatchEvent(new CustomEvent("step11-state-changed"));
}

// 跨簇通知（revise 上下文入口加载后广播）：目录不同 = 旧清单与当前目录无关，
// 清空本簇状态（显示占位，等用户拆解）——revise 簇负责状态生命周期与广播时机，
// 本簇只消费事件（零模块耦合：跨簇取值走 reviseGetDir 单点已够）。
window.addEventListener("revise-context-loaded", (event) => {
  const dir = event.detail && event.detail.output_dir;
  if (dir !== tasks.outputDir) {
    tasks.outputDir = "";
    tasks.plan = null;
    taskDialogs.clear();
    taskEditOpen.clear();
    clearTasksPanel();
    $("tasks-status").textContent = "";
    $("tasks-msg").textContent = "";
    resetIdeaArea();
    resetGlobalChatArea();
    resetDraftsArea();
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
  taskDialogs.clear();
  taskEditOpen.clear();
  const stale = $("tasks-result");
  if (stale) stale.remove();
  clearTasksPanel();
  $("tasks-status").textContent = "";
  $("tasks-msg").textContent = "任务清单已作废（修订重生成）：请点「拆解任务」按新工程重新拆解";
  resetIdeaArea();
  resetGlobalChatArea();
  resetDraftsArea();
});

export { tasksPlan, tasksRender, tasksResetMessages, tasksIsBusy, tasksSetBusy };
