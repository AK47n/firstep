// fx/generate.js — 生成主流程纯函数（工单 frontend-es-modules/08，迁自
// index.html 生成域纯函数组：覆盖冲突识别 / 阶段播报文案 / 等待计时 /
// 输出目录载荷 / 绑定收集 / 产物摘要 / 庆祝动画 / 卡片折叠决策）。
// 域内常量 CONFLICT_MSG_PREFIX 随迁并 export（后端 webapp.py 锚定单源，
// tests/test_webapp.py::test_conflict_message_prefix_anchored_both_sides
// 已同步改读本文件）；无共享件依赖（本域函数不引用全局 esc / formatSize）。
// 模块约定见 fx/core.js 头部。
export const CONFLICT_MSG_PREFIX = "桌面上已有同名工程「";

// 生成前覆盖保护（工单 generate-overwrite/01）：冲突 400 识别 + 目录名提取。
// CONFLICT_MSG_PREFIX 与后端 GenerationConflictError 消息前缀单源锚定，
// 跨文件一致性由
// tests/test_webapp.py::test_conflict_message_prefix_anchored_both_sides 兜底。
export function isConflictError(message) {
  return typeof message === "string" && message.indexOf(CONFLICT_MSG_PREFIX) === 0;
}

export function conflictDirName(message) {
  const m = /「([^」]+)」/.exec(message || "");
  return m ? m[1] : "";
}

// 输出目录路径 → 末段目录名（工单 ux-walkthrough-02/03）：恢复备份按钮的
// 探测名（.bak 存在性按目录名查桌面）；空/异常路径 → ""。
export function dirBasename(path) {
  const parts = String(path || "").split(/[\\/]/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
}

// 生成中阶段播报（工单 ui-polish-8/04）：子阶段文案轮播 + 等待计时。
// genStageTexts / fmtWait 为自包含纯函数（tests/js 正则抽取）
export function genStageTexts(i) {
  const texts = ["正在选配模块…", "正在定位母版…", "正在生成工程骨架…",
                 "正在写入工程文件…", "正在生成摘要…"];
  const n = Number.isFinite(i) ? Math.floor(i) : 0;
  return texts[((n % texts.length) + texts.length) % texts.length];
}

export function fmtWait(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  if (s < 60) return s + " 秒";
  return Math.floor(s / 60) + " 分 " + (s % 60) + " 秒";
}

export function generationOutputDirPayload(manualOutputDir, desktopOutput) {
  if (desktopOutput) return manualOutputDir || ".";
  return manualOutputDir;
}

export function collectBindings(selectedSlugs, bindings, instanceMap) {
  // bindings 载荷单源（工单 pin-verdict-seam/01 抽纯函数）：只带仍在选择集内的
  // 用户绑定（模块移除后不残留 400），已配多实例的模块（instanceMap[slug] 存在）
  // 不再发其角色绑定（工单 03 判据⑦「只发其一」）。validate 与 generate 必须发
  // 同一份 bindings——否则校验通过但生成拿到不同绑定会撞 400，故抽成单源。
  const slugs = new Set(selectedSlugs);
  const out = {};
  for (const [key, pin] of Object.entries(bindings)) {
    const slug = key.split(".")[0];
    if (slugs.has(slug) && !instanceMap[slug]) out[key] = pin;
  }
  return out;
}

// ---------------------------------------------------------------------------
// 同脚多角色 共享/冲突 判据（工单 pin-share-rule/01）：与后端
// pin_bindings._role_resource_keys / _shared_groups 同口径——同一 I2C 总线、
// 同一 UART 实例、同一 syscfg 器件实例 = 合法共享；其余同脚 = 物理冲突。
// 数据源：pinBoard.pins[].capabilities（uart/i2c 实例 token）+ state.module_instances
// （gpio 的 syscfg 实例映射，来自 /api/state）。前端镜像此规则，判定结论与
// /api/bindings/auto 的 shared[].kind 保持一致。
// ---------------------------------------------------------------------------

/** 角色在指定引脚上的「物理资源键」集（无键 = 无法与任何角色合法共用）。 */
export function pinRoleResourceKeys(role, pinName, pinBoard, instanceMap) {
  const t = role && role.decl && role.decl.type;
  if (!t) return [];
  if (["uart_tx", "uart_rx", "i2c_scl", "i2c_sda"].includes(t)) {
    const pin = (pinBoard && pinBoard.pins || []).find((p) => p.name === pinName);
    if (!pin) return [];
    const prefix = t + ":";
    return (pin.capabilities || [])
      .filter((c) => c.startsWith(prefix))
      .map((c) => c.slice(prefix.length));
  }
  if (t === "gpio_out" || t === "gpio_in") {
    return (instanceMap && instanceMap[role.slug]) || [];
  }
  return [];  // pwm / enc / adc / spi …：同脚即冲突（两路输出/两通道不可并）
}

/** 同脚多角色组分类：{kind: "share"|"conflict"|"none", reason}。 */
export function pinShareClass(roles, pinName, pinBoard, instanceMap) {
  const list = (roles || []).filter(Boolean);
  if (list.length < 2) return { kind: "none", reason: "" };
  const types = list.map((r) => r.decl.type);
  if (types.every((t) => t === "i2c_scl" || t === "i2c_sda")) {
    return {
      kind: "share",
      reason: "I2C 总线共享（HMC5883L / MPU6050 等可同挂 SCL/SDA，协议允许）",
    };
  }
  const keysets = list.map((r) => pinRoleResourceKeys(r, pinName, pinBoard, instanceMap));
  const common = keysets.length
    ? keysets.reduce((acc, s) => acc.filter((k) => s.includes(k)))
    : [];
  if (common.length) {
    if (types.some((t) => t === "uart_tx" || t === "uart_rx")) {
      return { kind: "share", reason: "同一串口链路共享（共用同一 UART 实例）" };
    }
    return { kind: "share", reason: "共用同一器件/总线（同一实例，共享合法）" };
  }
  return { kind: "conflict", reason: "同引脚但分属不同外设（物理不通）——请改线" };
}

export function formatResModules(modules, pythonArtifacts) {
  // 产物摘要「模块文件」行（工单 k230-vision-copilot/04 抽纯函数，node:test
  // 直测）：C 模块文件 + Python 副产物同列——k230 这类纯副产物模块（files
  // 空）也能在摘要里看见 main.py；不带副产物的空 files 模块只显示 slug。
  const pyBySlug = new Map((pythonArtifacts || []).map((a) => [a.slug, a]));
  // 模板名回显（工单 k230-multi-template/04）：done 载荷优先，页面状态兜底
  const pyTemplateName = (slug, artifact) => {
    if (artifact && (artifact.template_name || artifact.template_id)) {
      const name = artifact.template_name || (artifact.template_id === "default" ? "" : artifact.template_id);
      return name ? "（模板：" + name + "）" : "";
    }
    // node:test 直抽纯函数时没有页面全局状态；缺省按旧摘要格式处理。
    const expandedList = typeof expanded === "undefined" ? [] : (expanded || []);
    const templates = typeof pythonTemplates === "undefined" ? {} : pythonTemplates;
    const m = expandedList.find((x) => x.slug === slug);
    const pa = m && m.python_artifact;
    if (!pa || !pa.templates || pa.templates.length < 2) return "";
    const id = templates[slug] || pa.default;
    const t = pa.templates.find((x) => x.id === id);
    return t && (t.name || t.id) ? "（模板：" + (t.name || t.id) + "）" : "";
  };
  return (modules || []).map((m) => {
    const parts = [...(m.files || [])];
    const artifact = pyBySlug.get(m.slug);
    if (artifact && artifact.output) {
      parts.push("副产物 " + artifact.output + pyTemplateName(m.slug, artifact));
    }
    // 静态资产（工单 k230-digit-vision/03）：随模板复制的文件（如 AI 模型
    // kmodel + deploy_config.json）同列显示——用户知道 SD 卡要拷什么。
    for (const asset of (artifact && artifact.asset_paths) || []) {
      parts.push("资产 " + asset);
    }
    return m.slug + (parts.length ? "(" + parts.join(", ") + ")" : "");
  }).join("、");
}

// 步骤完成庆祝动画（工单 ui-polish-8/02）：一次性徽章弹跳 + 顶部光带，
// animationend 后自清理。接收类 DOM 对象（classList / addEventListener），
// tests/js 可抽取自包含测试
export function attachCelebrate(card) {
  if (!card || !card.classList) return;
  card.classList.add("celebrate");
  const done = () => {
    card.classList.remove("celebrate");
    card.removeEventListener("animationend", done);
  };
  if (card.addEventListener) card.addEventListener("animationend", done);
}

// ---------------------------------------------------------------------------
// 生成页卡片折叠（工单 ui-polish-4/01）：标题行按钮 / 点击 toggle /
// 导航底部「收起已完成」一键；折叠不持久化（刷新恢复展开）
// ---------------------------------------------------------------------------
// 折叠按钮读屏文案（工单 ui-polish-11/05）：title 保留「折叠/展开」，
// aria-label 用完整语义，随状态切换
export function collapseBtnLabel(collapsed) {
  return collapsed ? "展开该卡片" : "折叠该卡片";
}

// title + aria-label 同步（三处共用，避免重复块）
export function syncCollapseBtn(btn, collapsed) {
  btn.title = collapsed ? "展开" : "折叠";
  btn.setAttribute("aria-label", collapseBtnLabel(collapsed));
}

export function collapseToggleAll(cards, doneSet, collapse) {
  const done = new Set(doneSet || []);
  return Array.from(cards).map((c) => {
    // 步骤号（工单 ux-walkthrough-02/02）：data-step 优先（6.5 子步骤显式标注），
    // 子步骤不参与折叠/记忆（无折叠按钮，防 parseInt 撞号污染整数步记忆）
    const no = c.querySelector(".step-no");
    let n = NaN;
    if (no) {
      const raw = no.dataset && no.dataset.step !== undefined ? no.dataset.step : no.textContent;
      const v = Number(raw);
      if (Number.isFinite(v)) n = v;
    }
    if (!Number.isInteger(n)) return { n: NaN, collapsed: false };
    const isDone = done.has(n);
    const shouldCollapse = collapse ? isDone : false;
    c.classList.toggle("collapsed", shouldCollapse);
    const btn = c.querySelector(".card-collapse");
    if (btn) syncCollapseBtn(btn, shouldCollapse);
    return { n, collapsed: shouldCollapse };
  });
}

// ---------------------------------------------------------------------------
// 生成页卡片折叠初始态与记忆（工单 ux-polish-02/02）：默认「已完成且非当前步」
// 折叠（首屏更清爽），用户手动调整按步骤号持久化（localStorage 单键 JSON）。
// 纯函数三件 + 常量供胶水层取用：解析 / 初始判定 / 写入（异常静默降级）。
// ---------------------------------------------------------------------------
export const GEN_CARD_COLLAPSE_KEY = "firstep.genCardCollapse.v1";

export function parseGenCardCollapse(raw) {
  if (!raw) return {};
  try {
    const v = JSON.parse(raw);
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch { return {}; }
}

/** 单卡初始折叠判定：state = {no, done, current, stored}；无步骤号恒展开；
 * 记忆优先（用户选择覆盖默认规则）；无记忆 = 已完成且非当前步折叠。 */
export function genCardInitialCollapsed(state) {
  if (state.no == null || Number.isNaN(state.no)) return false;
  const stored = state.stored || {};
  if (state.no in stored) return !!stored[state.no];
  return !!(state.done && !state.current);
}

export function saveGenCardCollapse(storage, state) {
  try { storage.setItem(GEN_CARD_COLLAPSE_KEY, JSON.stringify(state)); return true; }
  catch (e) { return false; }
}

export function fmtSeconds(s) {   // 耗时展示：1 位小数（如 12.3）
  const n = Number(s);
  return Number.isFinite(n) && n >= 0 ? n.toFixed(1) : "0.0";
}

// compileSummaryText(done)：编译 done 载荷 → 终态文案**单源**（工单
// code-tab-compile/03 评审整改——生成页修复中心横幅与代码栏编译面板原先各写
// 一份「同口径」文案，实际措辞分叉）。timed_out / passed / summary /
// duration 均按 events.py done 契约字段；done 为空 → 空串（运行中状态由
// 调用方填）。
export function compileSummaryText(done) {
  if (!done) return "";
  const dur = fmtSeconds(typeof done.duration === "number" ? done.duration : 0);
  const sum = done.summary || { errors: 0, warnings: 0 };
  if (done.timed_out) return "编译超时（工具链 180s 未返回）";
  if (done.passed) {
    return "编译成功 · " + (sum.errors || 0) + " Error "
      + (sum.warnings || 0) + " Warning · 耗时 " + dur + "s";
  }
  return "编译失败 · " + (sum.errors || 0) + " 个错误 · 耗时 " + dur + "s";
}

export function fixLogGroupHidden(text) {   // 修复中心「编译输出」分组显隐：无输出即隐藏（避免空文本框占位）
  return !String(text ?? "").trim();
}

// frameworkNoteHTML(data)：题型框架注入提示（工单 topic-framework/04）。
// /api/skeleton 返回 topic_framework {injected, topic_type?, source?}；
// injected=false / 数据缺失 → ""（不渲染提示行）。文案带题型与来源条目。
export function frameworkNoteHTML(data) {
  const fw = data && data.topic_framework;
  if (!fw || !fw.injected) return "";
  return `已注入题型框架：「${fw.topic_type || "题型"}」（来源参考条目 ${fw.source || "?"}）—— main.c 已按该框架生成，请在其 TODO 位继续实现。`;
}

if (typeof window !== "undefined") {
  Object.assign(window, { CONFLICT_MSG_PREFIX, isConflictError, conflictDirName, genStageTexts, fmtWait, generationOutputDirPayload, collectBindings, pinRoleResourceKeys, pinShareClass, formatResModules, attachCelebrate, collapseBtnLabel, syncCollapseBtn, collapseToggleAll, GEN_CARD_COLLAPSE_KEY, parseGenCardCollapse, genCardInitialCollapsed, saveGenCardCollapse, fmtSeconds, frameworkNoteHTML, fixLogGroupHidden });
}
