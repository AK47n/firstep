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
    const no = c.querySelector(".step-no");
    const n = no ? parseInt(no.textContent, 10) : NaN;
    const isDone = done.has(n);
    const shouldCollapse = collapse ? isDone : false;
    c.classList.toggle("collapsed", shouldCollapse);
    const btn = c.querySelector(".card-collapse");
    if (btn) syncCollapseBtn(btn, shouldCollapse);
    return { n, collapsed: shouldCollapse };
  });
}

if (typeof window !== "undefined") {
  Object.assign(window, { CONFLICT_MSG_PREFIX, isConflictError, conflictDirName, genStageTexts, fmtWait, generationOutputDirPayload, collectBindings, formatResModules, attachCelebrate, collapseBtnLabel, syncCollapseBtn, collapseToggleAll });
}
