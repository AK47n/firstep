// ui/generate-core.js — 生成页 · 生成执行 + 评分清单 + 交付 Handoff
//（阶段 2 工单 15，源自 index.html 生成页 8/9/11 三节）。
//
// DOM 胶水全量迁入：SKELETON_MODES + generateMain（骨架/自检冒烟共用） /
// renderGenerateSuccess（成功区：目录/包含路径/模块/评分清单/产物树/自动编译） /
// desktopTopicOutputEnabled（桌面输出开关） / renderArtifacts（自动附带产物） /
// 评分清单 5 函数（renderScoreChecklist / scoreChecklistIdsNow /
// scoreChecklistSyncCurrent / scoreChecklistExportNow / initScoreChecklist） /
// 交接 6 函数（handoffPlatformLabel / handoffPlatformIde / handoffModuleLines /
// handoffWarnings / handoffPinLines / handoffReferenceLines）+ 顶层监听器
//（btn-skeleton / btn-smoke / desktop-topic-output change / btn-pick-output-dir /
// btn-handoff / btn-handoff-copy / btn-copy-dir——import 时绑定：module 脚本
// 延迟执行，DOM 已就绪，同 generate-recommend 先例）。纯件在 fx/*.js
//（generate / module / score / draft，本模块 import 调用）。
// 状态读（只读，写经各 setter）：A 簇 generate-recommend 的 chosenPlatform /
// selectedSlugs / expanded / warnings / scorePoints / selectedReferenceIds /
// autoReferenceIds / currentTopicId（工单 15 起 export let——读取方 import）；
// B 簇 generate-pins 的 instances / pinBindings / pinUnbound / pinRoles()。
// 跨域调用：syncStep7（step-state）/ markStepDone（step-state）/
// syncMainCHighlight（generate-mainc）/ refreshRecent（recent）。
// 跨簇服务（修复中心）静态 import 自 ui/generate-fix.js（工单 16 迁出后由
// 工单 15 的接缝改为静态 import）；host 侧不再注册。
// 留 host：btn-generate 覆盖重发监听器（依赖 host 内联 readinessState 前置
// 校验；经顶部 import 调用本模块 renderGenerateSuccess）。
import { $, apiGet, apiPost, state, KIND_TEXT, toast } from "/js/app.js";
import { formatResModules } from "/js/fx/generate.js";
import { instancePayload } from "/js/fx/module.js";
import { scoreChecklistId, scoreChecklistKey, scoreChecklistLoad, scoreChecklistItemsHTML, scoreChecklistProgressHTML, scoreChecklistSave, scoreChecklistExportText, formatScorePoints } from "/js/fx/score.js";
import { syncStep7 } from "/js/ui/step-state.js";
import { chosenPlatform, selectedSlugs, expanded, warnings, scorePoints, selectedReferenceIds, autoReferenceIds, currentTopicId } from "/js/ui/generate-recommend.js";
import { instances, pinBindings, pinUnbound, pinRoles } from "/js/ui/generate-pins.js";
import { markStepDone } from "/js/ui/step-state.js";
import { syncMainCHighlight } from "/js/ui/generate-mainc.js";
import { refreshRecent } from "/js/ui/recent.js";
import { startFixCenter, compileBanner, toolchains } from "/js/ui/generate-fix.js";  // 修复中心（工单 16 迁出→静态 import，取代工单 15 接缝）

// ---------------------------------------------------------------------------
// 生成页：8. main.c 骨架 / 自检冒烟（工单 skeleton-smoke-refs/01）
// 共用校验 / 请求 / intercepted 渲染；差异 = 按钮 id、main_mode、占位文案。
// ---------------------------------------------------------------------------
const SKELETON_MODES = {
  skeleton: { btn: "btn-skeleton", doneLabel: "重新生成骨架", interceptHint: "骨架" },
  smoke: { btn: "btn-smoke", doneLabel: "重新生成自检骨架", interceptHint: "自检骨架" },
};

async function generateMain(mode) {
  const cfg = SKELETON_MODES[mode];
  const btn = $(cfg.btn);
  $("skeleton-msg").textContent = "";
  const problem = $("problem").value.trim();
  if (!problem) { $("skeleton-msg").textContent = "请先填写赛题原文"; return; }
  if (!chosenPlatform) { $("skeleton-msg").textContent = "请先在步骤 3 选择目标平台"; return; }
  if (!selectedSlugs.length) { $("skeleton-msg").textContent = "请先选择模块"; return; }
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>生成中…';
  try {
    const payload = {
      problem_text: problem, slugs: selectedSlugs, platform: chosenPlatform,
      topic_id: currentTopicId || undefined,
    };
    if (mode === "smoke") payload.main_mode = "smoke";
    else payload.reference_ids = selectedReferenceIds;  // 参考实现进骨架（工单 02）
    const inst = instancePayload(expanded, instances);  // 多实例清单（工单 04）：空 = 不发（旧行为）
    if (Object.keys(inst).length) payload.instances = inst;
    const data = await apiPost("/api/skeleton", payload);
    $("main-c").value = data.main_c;
    syncMainCHighlight();
    markStepDone(8);
    const box = $("intercepted");
    if (data.intercepted.length) {
      box.classList.remove("hidden");
      box.textContent = "AI 调用以下函数在所选模块接口中不存在，已改写为注释占位，请在" + cfg.interceptHint
        + "里替换为真实接口：" + data.intercepted.join("、");
    } else { box.classList.add("hidden"); }
  } catch (e) { $("skeleton-msg").textContent = e.message; }
  finally {
    btn.disabled = false;
    btn.innerHTML = cfg.doneLabel;
  }
}

$("btn-skeleton").addEventListener("click", () => generateMain("skeleton"));
$("btn-smoke").addEventListener("click", () => generateMain("smoke"));

// ---------------------------------------------------------------------------
// 生成页：9. 输出目录并生成
// ---------------------------------------------------------------------------
// 生成中阶段播报（工单 ui-polish-8/04）：子阶段文案轮播 + 等待计时。
// genStageTexts / fmtWait 为自包含纯函数（tests/js 正则抽取）
// 已迁至 static/js/fx/generate.js（工单 08）：CONFLICT_MSG_PREFIX 常量 + isConflictError / conflictDirName。
// 生成成功渲染（工单 generate-overwrite/01 抽取，供主路径与覆盖重发共用）
function renderGenerateSuccess(data) {
  $("res-dir").textContent = data.output_dir;
  $("btn-copy-dir").classList.remove("hidden");
  $("res-includes").textContent = data.include_dirs.join("；");
  $("res-modules").textContent = formatResModules(data.modules, data.python_artifacts);
  renderScoreChecklist(data.score_points, data.output_dir);  // 评分点核对清单（工单 score-checklist/01）
  $("res-score-points").classList.toggle("hidden", !(data.score_points && data.score_points.length));
  // 构建脚本提示（工单 mspm0-build-makefiles/01）：非空时展示，空则隐藏
  $("res-build-hint").textContent = data.build_hint || "";
  $("res-build-hint").classList.toggle("hidden", !data.build_hint);
  $("res-structure").textContent = data.structure.join("\n");
  renderArtifacts(data.structure, data.output_dir);
  $("generate-result").classList.remove("hidden");
  $("gen-status").textContent = "";
  $("generate-msg").classList.add("ok");
  $("generate-msg").textContent = "生成完成！工程结构 / include path / main.c 已就位。";
  markStepDone(9);
  syncStep7({ platform: chosenPlatform, expanded, roles: pinRoles(), bindings: pinBindings, instances })  // 按默认布线生成成功 = 引脚步骤视为完成（工单 step7-done/01）
  refreshRecent();  // 生成成功 → 最近生成列表补一条（工单 recent-jobs/01）
  toast("ok", "工程生成完成");
  // 生成成功 → 自动触发编译修复（工单 autocompile-loop/01，决策记录 3：
  // 用户"懒得编译一遍"）；无工具链则横幅灰条提示（展示层工单
  // compile-experience-ui/01：无工具链也要显眼，不再静默跳过）
  if ((toolchains || {})[chosenPlatform]) {
    $("generate-msg").textContent += "已自动触发编译修复（见第 10 栏）…";
    $("card-fix-center").scrollIntoView({ block: "nearest" });
    setTimeout(() => startFixCenter(), 100);   // 等结果字段渲染完成再起流
  } else {
    compileBanner("notool", "未检测到工具链，跳过自动编译（可在设置页填 uv4_path / gmake_path）");
  }
}
// 已迁至 static/js/fx/generate.js（工单 08）：genStageTexts / fmtWait。
function desktopTopicOutputEnabled() {
  const checkbox = $("desktop-topic-output");
  return checkbox ? checkbox.checked : true;
}

// 已迁至 static/js/fx/generate.js（工单 08）：generationOutputDirPayload。

$("desktop-topic-output").addEventListener("change", () => {
  const manual = !desktopTopicOutputEnabled();
  $("output-dir").disabled = !manual;
  $("btn-pick-output-dir").disabled = !manual;
});
$("output-dir").disabled = desktopTopicOutputEnabled();
$("btn-pick-output-dir").disabled = desktopTopicOutputEnabled();

$("btn-pick-output-dir").addEventListener("click", async () => {
  try {
    const data = await apiPost("/api/pick-directory", {});
    if (data.path) $("output-dir").value = data.path;  // 取消 = null，不覆盖手输
  } catch (e) { $("generate-msg").textContent = e.message; }
});


// ---------------------------------------------------------------------------
// （btn-generate 覆盖重发监听器与其 readiness 前置校验留 index.html——依赖
// host 内联 readinessState；renderGenerateSuccess 经 host 顶部 import 调用）
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 生成页：11. 交接提示词（Handoff）——把本次生成的全部上下文打包成一段
// 提示词，用户直接复制粘贴给下一个 AI 做精准打磨（本工具只搭基础，
// 精打磨在下一个会话完成）。交接永远在最后一步：修复中心跑完后，把编译/
// 修复状态一起装进提示词再交给下一个会话。
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// 自动附带产物（工单 report-draft-demo/04）：设计报告草稿.md / 演示脚本.md
// 随生成自动落盘工程根——structure 含文件名 = 已生成；badge 标注 + 点击复制
// 文件路径（打开 = 复制后在资源管理器 / 编辑器打开，本地应用不引后端打开
// 接口——安全面最小）。演示脚本恒在（模块兜底），报告仅在 LLM 文本非空时在。
// ---------------------------------------------------------------------------
function renderArtifacts(structure, outputDir) {
  const box = $("res-artifacts");
  box.textContent = "";
  const artifacts = (structure || []).filter(
    (f) => f === "设计报告草稿.md" || f === "演示脚本.md"
  );
  if (!artifacts.length) { box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  const head = document.createElement("span");
  head.className = "muted";
  head.textContent = "自动附带：";
  box.appendChild(head);
  artifacts.forEach((f) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "badge";
    chip.style.cssText = "margin-left:6px;padding:2px 8px;font-size:12px;cursor:pointer";
    chip.textContent = f;
    chip.title = "点击复制文件路径（在资源管理器 / 编辑器中打开）";
    chip.setAttribute("data-ico", "copy");
    chip.addEventListener("click", async () => {
      const full = outputDir.replace(/\\/g, "/") + "/" + f;
      try {
        await navigator.clipboard.writeText(full);
        toast("ok", "已复制文件路径：" + full);
      } catch {
        toast("error", "复制失败");
      }
    });
    box.appendChild(chip);
  });
}

// 评分点核对清单（工单 score-checklist/01）：评分点可勾选清单——逐条核对 +
// 进度 + 复制核对表（☑/□），勾选进度按工程目录持久化 localStorage
// （key = score-checklist:<output_dir>）。纯函数已迁至 static/js/fx/score.js
// （工单 10）：formatScorePoints / scoreChecklistPartLabel /
// scoreChecklistScoreText / scoreChecklistRefsText / scoreChecklistId /
// scoreChecklistChecked / scoreChecklistLineText / scoreChecklistKey /
// scoreChecklistItemsHTML / scoreChecklistProgressHTML / scoreChecklistExportText /
// scoreChecklistParse / scoreChecklistLoad / scoreChecklistSave。渲染 / 事件委托留内联。
// 渲染 + 交互（DOM 部分）：生成成功回调调用；勾选/复制走 #res-score-points 委托。
// box._scorePoints/_scoreIds 在 render 时挂载（同步当前勾选 id 与导出文本用）。
function renderScoreChecklist(points, outputDir) {
  const box = $("res-score-points");
  if (!box) return;
  const list = $("sp-list");
  const progress = $("sp-progress");
  if (!list || !progress) return;
  box._scorePoints = points || [];
  box._scoreIds = box._scorePoints.map((p, i) => scoreChecklistId(p, i));
  const storage = (typeof localStorage !== "undefined") ? localStorage : null;
  const saved = scoreChecklistLoad(scoreChecklistKey(outputDir), storage);
  list.innerHTML = scoreChecklistItemsHTML(box._scorePoints, saved);
  progress.textContent = scoreChecklistProgressHTML(
    list.querySelectorAll('input[type="checkbox"]:checked').length, box._scorePoints.length);
}
function scoreChecklistIdsNow(box) {
  if (!box || !box._scoreIds) return [];
  return Array.from(box.querySelectorAll('input[type="checkbox"]:checked'))
    .map((c) => box._scoreIds[parseInt(c.dataset.idx, 10)])
    .filter((id) => id != null);
}
function scoreChecklistSyncCurrent(box) {
  const list = $("sp-list");
  const progress = $("sp-progress");
  if (!box || !list || !progress) return;
  progress.textContent = scoreChecklistProgressHTML(
    list.querySelectorAll('input[type="checkbox"]:checked').length,
    list.querySelectorAll('input[type="checkbox"]').length);
  const storage = (typeof localStorage !== "undefined") ? localStorage : null;
  const dirBox = $("res-dir");
  scoreChecklistSave(scoreChecklistKey(dirBox ? dirBox.textContent : ""),
    scoreChecklistIdsNow(box), storage);
}
function scoreChecklistExportNow(box) {
  if (!box || !box._scorePoints || !box._scorePoints.length) return "";
  return scoreChecklistExportText(box._scorePoints, scoreChecklistIdsNow(box));
}
function initScoreChecklist() {
  const box = $("res-score-points");
  if (!box) return;
  box.addEventListener("change", (e) => {
    if (!(e.target && e.target.matches('input[type="checkbox"]'))) return;
    const item = e.target.closest(".sp-item");
    if (item) item.classList.toggle("done", e.target.checked);
    scoreChecklistSyncCurrent(box);
  });
  const btn = $("btn-score-export");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const text = scoreChecklistExportNow(box);
    if (!text) { toast("info", "还没有评分点可复制"); return; }
    const done = () => toast("ok", "核对表已复制");
    const fallback = () => {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        if (document.execCommand && document.execCommand("copy")) { toast("ok", "核对表已复制"); return; }
        toast("error", "复制失败：请手动复制");
      } catch (err) { toast("error", "复制失败：" + err.message); }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(fallback);
    } else fallback();
  });
}


function handoffPlatformLabel() {
  const pf = (state.platforms || []).find((p) => p.id === chosenPlatform);
  return pf ? pf.name : (chosenPlatform || "未选择");
}
function handoffPlatformIde() {
  return chosenPlatform === "stm32" ? "Keil5" : chosenPlatform === "mspm0" ? "CCS" : "";
}
function handoffModuleLines() {
  // 展开过依赖用展开结果（含简介/依赖/平台徽标），否则从模块库详情拼
  const src = expanded.length
    ? expanded
    : selectedSlugs.map((slug) => (state.modules || []).find((m) => m.slug === slug)).filter(Boolean);
  if (!src.length) return "（未选模块）";
  return src.map((m) => {
    const deps = (m.dependencies || []).length ? "，依赖：" + m.dependencies.join("、") : "";
    return "- " + m.slug + "：" + (m.description || "") + deps;
  }).join("\n");
}
function handoffWarnings() {
  if (!warnings.length) return "（所选模块在该平台均可直接使用）";
  return warnings.map((w) => "- [" + (KIND_TEXT[w.kind] || w.kind) + "] " + w.message).join("\n");
}
function handoffPinLines() {
  const bindings = Object.entries(pinBindings);
  const unbound = [...pinUnbound];
  if (!bindings.length && !unbound.length) {
    return "（未手动改线；全部按默认布局生成。引脚单源：stm32 = pin_config.h / mspm0 = mspm0.syscfg；mspm0 已按选中模块裁剪 syscfg，未选模块引脚空出）";
  }
  const lines = [];
  for (const [key, pin] of bindings) lines.push("- " + key + " → " + pin);
  for (const key of unbound) lines.push("- " + key + "（显式解除，生成仍按默认）");
  return lines.join("\n") + "\n\n引脚单源：stm32 = pin_config.h / mspm0 = mspm0.syscfg；mspm0 已按选中模块裁剪 syscfg，未选模块引脚空出。";
}
async function handoffReferenceLines() {
  if (!selectedReferenceIds.length && !autoReferenceIds.length) {
    return "（未手动勾选；赛题 / 套件自动锚定的资料已按平台注入工程）";
  }
  try {
    const entries = await apiGet("/api/references");
    const byId = new Map(entries.map((e) => [e.id, e]));
    const lines = [];
    for (const id of selectedReferenceIds) {
      const e = byId.get(id);
      lines.push("- [手动] " + (e ? e.title : id));
    }
    for (const id of autoReferenceIds) {
      if (selectedReferenceIds.includes(id)) continue;
      const e = byId.get(id);
      lines.push("- [自动] " + (e ? e.title : id));
    }
    return lines.join("\n") || "（参考资料读取为空）";
  } catch { return "（参考资料读取失败，可忽略）"; }
}

$("btn-handoff").addEventListener("click", async () => {
  const msg = $("handoff-msg");
  msg.textContent = "";
  const problem = $("problem").value.trim();
  if (!problem) { msg.textContent = "请先填写赛题原文"; return; }
  if (!chosenPlatform) { msg.textContent = "请先选择目标平台"; return; }
  $("btn-handoff").disabled = true;
  try {
    const platform = handoffPlatformLabel();
    const ide = handoffPlatformIde();
    const summary = $("topic-summary-box").textContent.trim();
    const mainC = $("main-c").value.trim();
    const dir = $("res-dir").textContent.trim();   // 生成成功后才非空
    const structure = $("res-structure").textContent.trim();
    const fixRound = $("fix-center-round").textContent.trim();
    const fixStatus = $("fix-status").textContent.trim();
    const fixLog = $("fix-center-log").value.trim();
    const refs = await handoffReferenceLines();
    const warns = handoffWarnings();
    const pins = handoffPinLines();
    const hasScores = scorePoints.length > 0;
    const scores = formatScorePoints(scorePoints);
    const scoreSection = hasScores ? ["", "## 五、评分点验收清单", "", scores] : [];
    const lines = [
      "# 电赛工程交接提示词（Handoff）",
      "",
      "你是嵌入式开发工程师，接手一个由「电赛工程生成器」搭好的基础工程。平台 / 模块 / 骨架已就绪，你的任务是精准打磨，最终交付一份功能完整、编译零错误、可直接参赛提交的工程。",
      "",
      "## 一、赛题原文",
      "",
      problem,
      "",
      "## 二、功能要点（AI 预读整理）",
      "",
      summary || "（未生成，可在打磨时自行通读题面整理）",
      "",
      "## 三、目标平台",
      "",
      platform + (ide ? "（IDE：" + ide + "）" : ""),
      "",
      "## 四、模块清单",
      "",
      handoffModuleLines(),
      ...scoreSection,
      "",
      "## 五、平台警告",
      "",
      warns,
      "",
      "## 六、引脚绑定配置",
      "",
      pins,
      "",
      "## 七、main.c 骨架",
      "",
      "```c",
      mainC || "（未生成骨架）",
      "```",
      "",
      "## 八、工程位置",
      "",
      dir ? "- 输出目录：" + dir : "（工程尚未生成；可先以 1~5 项上下文开始打磨，或先在本工具生成）",
      ...(dir && structure ? ["", "工程结构：", "", "```", structure, "```"] : []),
      "",
      "## 九、编译与修复状态",
      "",
      ...(fixRound ? [fixRound] : []),
      fixStatus || "（未运行修复中心）",
      ...(fixLog ? ["", "编译输出：", "", "```", fixLog, "```"] : []),
      "",
      "## 十、参考资料",
      "",
      refs,
      "",
      "## 十一、打磨要求",
      "",
      "1. 通读 main.c，把注释占位 / 未实现的调用全部按模块真实接口补齐；",
      "2. 逐模块核对与题面要求的符合度，缺的功能先落到骨架与工程内；",
      "3. 用 " + ide + " 编译至 0 error 0 warning；",
      "4. 按题面评分点逐条自检，确认每个要求都有对应实现；",
      "5. 只修改生成工程目录内的文件，不要改动模块库 / 参考库等仓库内容。",
    ];
    $("handoff-text").value = lines.join("\n");
    $("btn-handoff-copy").classList.remove("hidden");
    markStepDone(12);
  } catch (e) {
    msg.textContent = e.message;
  } finally { $("btn-handoff").disabled = false; }
});

$("btn-handoff-copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("handoff-text").value);
    const btn = $("btn-handoff-copy");
    btn.textContent = "已复制";
    toast("ok", "已复制到剪贴板");
    setTimeout(() => { btn.textContent = "复制"; }, 1500);
  } catch {
    $("handoff-text").select();
    document.execCommand("copy");
    $("handoff-text").blur();
  }
});

$("btn-copy-dir").addEventListener("click", async () => {
  const dir = $("res-dir").textContent.trim();
  if (!dir) return;
  try {
    await navigator.clipboard.writeText(dir);
    toast("ok", "已复制输出路径");
  } catch (e) {
    toast("error", "复制失败");
  }
});


// ---- 本簇导出面（host 顶部 import 活绑定调用点） ----
// 说明（工单 15 记录，工单 16 修订）：generateMain / renderScoreChecklist /
// scoreChecklistSyncCurrent / scoreChecklistExportNow 当前无 host 调用点
//（监听器随簇迁入），按检查表导出为模块 API；host 实际使用
// renderGenerateSuccess / desktopTopicOutputEnabled / initScoreChecklist /
// 修复中心服务已随工单 16 改静态 import（startFixCenter / compileBanner / toolchains）。
export { generateMain, renderGenerateSuccess, desktopTopicOutputEnabled,
  renderScoreChecklist, scoreChecklistSyncCurrent, scoreChecklistExportNow,
  initScoreChecklist };
