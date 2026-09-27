// fx/hwcheck-plan.js — 硬件检测栏目的纯函数：**逐件小节 / 未专精点名 / 串口命令台 / 自建件的检测计划**。
//
// 由 `fx/hwcheck.js` 按职责整段搬来（工单 hwcheck-hygiene/09），**只搬不改**。
// 模块约定与六件的依赖方向见 `fx/hwcheck-state.js` 头部——那份是**单源**，
// 别在这里再抄一遍（抄六遍就是六份会各自漂移的散文）。

import { esc } from "./core.js";

// ===========================================================================
// 工单 module-hwcheck/04：这一趟**真测哪几件**（配方驱动的小节）+ 未专精点名
//
// 分工不变：配方与判据全在服务端（`GET/POST /api/hwcheck/*` 的 `sections` /
// `unspecialized`），本文件只把载荷渲染成 HTML。**不在这里判"这件测不测得了"**
// ——那会变成第二个判据来源，与后端的配方表迟早对不上。
// ===========================================================================

// hwcheckSectionsState(state, payload)：载荷里的"逐件小节 + 未专精点名"部分。
// 载荷缺键 = 保留当前状态（旧后端 / 出错响应不许把已有的检测计划抹掉）。
// 同样只返回自己的键（见 hwcheckBoardState 的 spread 说明）。
export function hwcheckSectionsState(state, payload) {
  const data = payload || {};
  return {
    sections: Array.isArray(data.sections)
      ? data.sections
      : ((state && Array.isArray(state.sections)) ? state.sections : []),
    unspecialized: Array.isArray(data.unspecialized)
      ? data.unspecialized
      : ((state && Array.isArray(state.unspecialized)) ? state.unspecialized : []),
  };
}

// hwcheckSectionPlanText(section)：一节"到底测什么"的一句话。
// 判定档位由服务端事实决定（有探头 / 只有初始化返回值 / 只做动作不判定）——
// 前端只选词，不改判：把"看着测了其实没测"如实说成"只看现象"。
export function hwcheckSectionPlanText(section) {
  const s = section || {};
  const probe = s.probe && typeof s.probe === "object" ? s.probe : null;
  const parts = [];
  if (probe && probe.expect) {
    parts.push(`通信探头带判定（期望 ${probe.expect}）`);
  } else if (probe) {
    parts.push("探头只做动作、板上不做判定");
  }
  if (s.init_expect) parts.push(`初始化返回值判定（期望 ${s.init_expect}）`);
  else if ((s.init || []).length) parts.push("初始化（不判返回值）");
  if ((s.read || []).length) parts.push(`${s.read.length} 项读数回显`);
  if (s.console) parts.push(`串口命令 ${s.console.command}`);
  return parts.length ? parts.join(" ｜ ") : "这一节没有实际动作";
}

// hwcheckSectionNoteHTML(section)：平台差异说明（直接印出来，不折叠）。
// 规格要求"平台不对称如实呈现"——地猛星没有浮点显示接口、通道被钳回 0 这类
// 事实写在配方的 note 里，学生看检测页就该看到，不该翻 manifest。
export function hwcheckSectionNoteHTML(section) {
  const notes = ((section && section.note) || []).filter(Boolean);
  if (!notes.length) return "";
  return notes.map((line) => `<div class="hwcheck-hint">▸ ${esc(line)}</div>`).join("");
}

// hwcheckSectionsHTML(sections)：逐件专精小节清单。
// **外观可区分**（票面验收线）：专精件带 [专精] 徽章（服务端给的 tag），
// 未专精件根本不在这里（由 hwcheckUnspecializedHTML 单独点名）。
export function hwcheckSectionsHTML(sections) {
  const list = Array.isArray(sections) ? sections : [];
  if (!list.length) return "";
  const rows = list.map((item) => {
    const s = item || {};
    const tag = esc(s.tag || "[专精]");
    const probeBadge = s.has_probe
      ? '<span class="badge ok">板上判定</span>'
      : '<span class="badge">只看现象</span>';
    return '<div class="hwcheck-section">'
      + '<div class="hwcheck-section-head">'
      + `<span class="hwcheck-section-tag">${tag}</span>`
      + `<span class="slug">${esc(s.slug || "")}</span>${probeBadge}</div>`
      + `<div class="hwcheck-hint">这一节：${esc(hwcheckSectionPlanText(s))}</div>`
      + hwcheckSectionNoteHTML(s)
      + "</div>";
  }).join("");
  return '<div class="hwcheck-hint">这一趟的检测程序会给下面这几件出专精小节'
    + "（配方来自库内数据，不是 AI 写的）：</div>" + rows;
}

// hwcheckUnspecializedHTML(items)：没配方的器件 → **通用降级小节**（工单 07）。
//
// 这一版它们真出小节了（只做初始化 +（I2C 类件）总线地址扫描），所以页面不能再
// 说"不会给它出检测小节"（04 那句已经过期）。三件事都**只渲染服务端给的字**：
// `label`（官方的「未专精：…」标注，单源）、`plan`（这一趟对它做什么）、
// `message`（点名那句完整话）——前端一个字都不另写，也不给缺字段编兜底句
// （缺 label 就不画那个徽章；编一句就是同一句话两处写、迟早两种措辞）。
//
// **外观可区分**（票面验收线）：专精件是实心 `[专精]` 徽章 + 判定档位，通用件是
// 描边 `◻` + 「不算通过」——学生一眼能看出哪些结论可信、哪些只是走了个过场
// （spec 用户故事 10）。
//
// ⚠ 容器类名**不是** `.hwcheck-section`：那个类是"专精小节"的选择器（页面、
// 浏览器验收与静态守卫都按它数"这一趟真测了几件"），通用件套上它会让那个数
// 数不清（真机验收当场抓到：`sectionCount` 从 1 变 2）。通用件用
// `.hwcheck-generic`，只复用结构性的 `.hwcheck-section-head` / `.hwcheck-section-tag`
// （那是"节的头 / 节的徽章"，与专精与否无关）。
export function hwcheckUnspecializedHTML(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return "";
  const rows = list.map((item) => {
    const one = item || {};
    const label = String(one.label || "");
    const plan = String(one.plan || "");
    const message = String(one.message || one.slug || "");
    const tag = label
      ? `<span class="hwcheck-section-tag generic">◻ ${esc(label)}</span>`
      : "";
    return '<div class="hwcheck-generic">'
      + '<div class="hwcheck-section-head">'
      + tag
      + `<span class="slug">${esc(one.slug || "")}</span>`
      + '<span class="badge">不算通过</span></div>'
      + (plan ? `<div class="hwcheck-hint">这一节：${esc(plan)}</div>` : "")
      + `<div class="hwcheck-hint">${esc(message)}</div>`
      + "</div>";
  }).join("");
  return '<div class="hwcheck-hint">下面这几件没有专精配方，走通用降级'
    + "——板上判不了通断，所以它们<strong>不算通过</strong>"
    + "（每件这一趟到底做了什么，逐条列在下面）：</div>" + rows;
}

// hwcheckSectionsEmptyHTML()：一件专精件都没有时的说明。
// **不是错误状态**：不选器件 = 「先确认板子活着」那条路（spec 用户故事 4）；
// 选了器件但都没配方时，它们由 hwcheckUnspecializedHTML 逐条点名**并且真的
// 出通用小节**（工单 07）——这里说清"为什么这条是空的"，不留一块沉默的空白。
export function hwcheckSectionsEmptyHTML() {
  return '<div class="muted">这一趟没有专精件：检测程序会跑 LED 心跳 + 通道自报，'
    + "选中的器件走通用降级（只验总线和初始化，见下一条）。"
    + "专精小节来自库内配方——服务端按库内配方给，页面不猜哪几件有。</div>";
}

// ===========================================================================
// 工单 module-hwcheck/06：串口命令台（复测不用重烧）
//
// 分工照旧：命令表由服务端从库内配方生成（`console_payload`），本文件只把
// 载荷渲染成 HTML。**不在这里判"哪个字符是谁的"**——判重与保留字都在服务端
// （两件抢字符 = 构建期 400），前端再判一次就是第二个判据来源。
// ===========================================================================

// hwcheckConsoleState(state, payload)：载荷里的"串口命令台"部分。
// 载荷缺键 = 保留当前状态（旧后端 / 出错响应不许把已有的命令表抹掉）。
// 同样只返回自己的键（见 hwcheckBoardState 的 spread 说明）。
export function hwcheckConsoleState(state, payload) {
  const data = payload || {};
  const next = data.console;
  return {
    console: (next && typeof next === "object")
      ? next
      : ((state && state.console) || null),
    // 复测字符余量提示（工单 hwcheck-hardening/05）：由服务端给（空串 = 不吭声）。
    // 判据不在这里——"还剩几个字符"是分配器的账，前端算不了也不该算。
    consoleNote: typeof data.console_note === "string"
      ? data.console_note
      : ((state && state.consoleNote) || ""),
  };
}

// hwcheckConsoleNoteHTML(text)：复测字符余量的事前提示（工单 hwcheck-hardening/05）。
// 空串 = 不渲染任何东西（平时别把一句警告常驻在页面上）。
export function hwcheckConsoleNoteHTML(text) {
  const message = String(text || "");
  if (!message) return "";
  return `<div class="hwcheck-warn">${esc(message)}</div>`;
}

// hwcheckConsoleHTML(console)：命令台面板。
// 有串口：命令逐条列出（敲什么 / 哪一件 / 测什么）+ 既有 r/y/g/o/b 单列
// + 帮助字符。**没有串口就不摆那张表**——摆出来像"敲了就行"，而这一趟根本
// 没有命令循环（服务端那句 hint 会明说不能交互式复测，票面要求）。
//
// 自建件那几行（工单 hwcheck-unknown-device/06）：字符是服务端分配的，页面
// **只渲染**；多出来的两个键（`tag` 标注词 / `name` 人读名）判据全在服务端，
// 这里按"有没有 `tag`"分两种画法——缺字段 = 库内件（与 fx/module.js 那处
// "旧载荷无字段 = 保守按库内件"同一条口径）。前端不判"哪个字符是谁的"。
export function hwcheckConsoleHTML(console) {
  const data = (console && typeof console === "object") ? console : null;
  if (!data) return "";
  const hint = String(data.hint || "");
  const help = String(data.help_command || "?");
  const commands = Array.isArray(data.commands) ? data.commands : [];
  const legacy = Array.isArray(data.legacy) ? data.legacy : [];
  if (!hint && !commands.length && !legacy.length) return "";
  if (data.available === false) {
    return hint ? `<div class="hwcheck-hint">${esc(hint)}</div>` : "";
  }
  const rows = commands.map((item) => {
    const one = item || {};
    const name = String(one.name || "");
    const tag = String(one.tag || "");
    // 「哪一件」那一格：自建件带名称与标注词——名字与后端 `ConsoleEntry.label`
    // 同一个意思（跨语言读同一个词），库内件就是 slug。
    const label = tag
      ? `<span class="slug">${esc(one.slug || "")}</span>`
        + (name ? ` <span class="hwcheck-custom-name">${esc(name)}</span>` : "")
        + ` <span class="badge custom">${esc(tag)}</span>`
      : esc(one.slug || "");
    return '<tr><td class="hwcheck-pin">' + esc(one.command || "") + "</td>"
      + `<td>${label}</td>`
      // 说明由服务端恒填（缺省句的后端单源是 ConsoleEntry.detail）：前端不另写
      // 一句兜底，否则同一句文案两处写、迟早两种措辞。
      + `<td>${esc(one.description || "")}</td></tr>`;
  }).join("");
  const table = rows
    ? '<table class="hwcheck-table"><thead><tr><th>敲这个</th><th>哪一件</th>'
      + "<th>复测什么</th></tr></thead><tbody>" + rows + "</tbody></table>"
    : "";
  const legacyLine = legacy.length
    ? '<div class="hwcheck-hint">既有命令（库内 debug_cmd_poll 执行，'
      + "语义没变）："
      + legacy.map((item) => esc((item || {}).command || "") + " "
        + esc((item || {}).description || "")).join(" / ")
      + "</div>"
    : "";
  return '<div class="hwcheck-console">'
    + (hint ? `<div class="hwcheck-hint">${esc(hint)}</div>` : "")
    + table + legacyLine
    + `<div class="hwcheck-hint">帮助：敲 `
    + `<span class="hwcheck-pin">${esc(help)}</span> 列出全部命令。</div>`
    + "</div>";
}

// ===========================================================================
// 工单 hwcheck-unknown-device/05：自建件的**检测计划**（接线行 / 标注 / 为什么
// 没有它的探测小节）
//
// 分工不变：标注词（「自建件：按你确认的事实探测」）、接线那一行（名称 + 地址 +
// 支点那对脚）、"这一趟对它做什么"——**全部来自服务端载荷**（`hwcheck_custom`
// 单源），本文件一个字都不另写。尤其**不在这里判"这件的总线是不是 I2C"**：
// 那是"出不出探测小节"的判据，服务端已经判过一次（`probes`），前端再判一次就是
// 两处各说各话——页面上说会测、产物里没有它。
// ===========================================================================

// hwcheckCustomState(state, payload)：载荷里的"自建件计划"部分。
// 载荷缺键 = 保留当前状态（旧后端 / 出错响应不许把已有的计划抹掉）。
// 同样只返回自己的键（见 hwcheckBoardState 的 spread 说明）。
export function hwcheckCustomState(state, payload) {
  const data = payload || {};
  return {
    custom: Array.isArray(data.custom)
      ? data.custom
      : ((state && Array.isArray(state.custom)) ? state.custom : []),
  };
}

// hwcheckCustomPlanHTML(items)：自建件的检测计划面板。
//
// **空 = 空串**：一件自建件都没有时检测页逐字与改动前一致（票面第 6 条）。
// 出小节的件与不出小节的件**都画**（后者把"为什么没有它的探测程序"原样带出来）
// ——只画前者就是一次悄无声息的少测。
//
// 外观与库内 `.hwcheck-section` 刻意不同（自己的类名 + 服务端给的标注词）：
// 学生要一眼看出哪些结论是库内验证过的、哪些只是"按我给的地址试了一下"。
export function hwcheckCustomPlanHTML(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return "";
  const rows = list.map((item) => {
    const one = item || {};
    const facts = [
      one.address_text ? `地址 ${esc(one.address_text)}` : "",
      one.register_text ? `身份寄存器 ${esc(one.register_text)}` : "",
      one.expect_text ? `期望值 ${esc(one.expect_text)}` : "",
    ].filter(Boolean).join(" ｜ ");
    const tag = one.tag_text
      ? `<span class="hwcheck-section-tag custom">${esc(one.tag_text)}</span>`
      : "";
    const badge = one.probes
      ? '<span class="badge ok">板上判定</span>'
      : '<span class="badge">这一趟没有它的探测小节</span>';
    // 快照出处（工单 hwcheck-unknown-device/08）：回读以工程内快照为准——
    // 行上如实标"来自我的器件 <id>"；那条已被删掉时再补一句（不静默、不报错）。
    // 现读行（预览 / 08 之前的工程）不画标记。
    const source = one.snapshot
      ? `<div class="hwcheck-hint hwcheck-custom-snapshot">来自我的器件 ${esc(one.slug || "")} `
        + (one.stored
          ? "</div>"
          : "（这一条已从「我的器件」删除——这里显示的是工程内快照）</div>")
      : "";
    return `<div class="hwcheck-custom-plan" data-custom-plan="${esc(one.slug || "")}">`
      + '<div class="hwcheck-section-head">'
      + tag
      + `<span class="slug">${esc(one.slug || "")}</span>`
      + `<span class="hwcheck-custom-name">${esc(one.name || "")}</span>${badge}</div>`
      + (facts ? `<div class="hwcheck-hint">${facts}</div>` : "")
      + `<div class="hwcheck-hint">这一趟对它做什么：${esc(one.plan || "")}</div>`
      + (one.notes ? `<div class="hwcheck-hint">你填的备注：${esc(one.notes)}</div>` : "")
      + source
      + "</div>";
  }).join("");
  return rows;
}

// hwcheckCustomWiringHTML(items)：接线区里自建件那一行（服务端算好的整句）。
//
// 只画**有接线说明**的那几件（`wiring_text` 非空 = 这一趟真借了支点那条总线）：
// 没有它就没有线可接，编一行出来等于让学生去找一根不存在的线。
export function hwcheckCustomWiringHTML(items) {
  const list = (Array.isArray(items) ? items : []).filter(
    (item) => item && item.wiring_text);
  if (!list.length) return "";
  return list.map((item) =>
    `<div class="hwcheck-custom-wiring" data-custom-wiring="${esc(item.slug || "")}">`
    + `<span class="hwcheck-section-tag custom">${esc(item.tag_text || "")}</span>`
    + esc(item.wiring_text) + "</div>").join("");
}

// —— 探针桥（CDP / devtools 与页面内联脚本的既有出口）——
if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckSectionsState, hwcheckSectionsHTML, hwcheckUnspecializedHTML,
    hwcheckSectionsEmptyHTML, hwcheckSectionPlanText, hwcheckSectionNoteHTML,
    hwcheckConsoleState, hwcheckConsoleHTML, hwcheckConsoleNoteHTML,
    hwcheckCustomState, hwcheckCustomPlanHTML, hwcheckCustomWiringHTML,
  });
}
