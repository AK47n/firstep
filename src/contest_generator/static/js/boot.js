// js/boot.js — 前端**装载根**（工单 frontend-boot-module/02）：模块装载清单 + 接线 + 启动。
//
// 为什么有这个文件（原 index.html 末尾那个 <script type="module"> 整块搬来这里）：
//   1. **装载图不该住在 HTML 里**：清单里提到一个不存在的导出，浏览器解析 import 就抛
//      SyntaxError，整页脚本全灭，而服务端 /api/* 与静态资源全 200（2026-09-12 真机现场，
//      看起来像"卡住"，强刷也没用）。搬进模块图后，这件事归 tests/js 的静态守卫
//      （含全图 import↔export 对账）与真浏览器门禁管。
//   2. **"靠被加载才接线"的隐式边退场**：模块求值期不再绑监听器 / 写首帧 DOM，接线写成
//      显式的 init*() 调用（工单 03/04 起），读这一个文件就知道页面装了什么、按什么顺序装的。
//
// 分层规则（照 js/app.js 的禁环约定）：
//   · boot 可以 import ui/** 与 app.js；
//   · **任何 ui/** 或 app.js 都不得 import boot.js**（否则成环）；
//   · index.html 只留一条 <script type="module" src="/js/boot.js"> 装载标签。
//
// 顺序纪律：装载清单**逐字保序**（ESM 求值顺序 = import 书写顺序，排序 / 分组 / 合并
// 都会改变模块求值次序）；接线区的调用顺序 = 清单里的出现顺序。
//
// ---- 以下为原 index.html 宿主块逐字搬运（工单 02；迁移墓碑注释一并保留）----

// 前端纯函数模块（工单 frontend-es-modules/01）：静态 import 保证本模块执行前
// fx/*.js 已加载完毕——DOM 胶水里的裸引用即模块作用域绑定，时序零等待
import { $, apiGet, state, setState } from "/js/app.js";
import { renderUsageStats } from "/js/ui/usage.js";
import { loadMasters, loadChangelog, renderNewPlatformOptions, initMasterWorkflow } from "/js/ui/master.js";  // initMasterWorkflow = 母版页工具链接线（工单 frontend-boot-module/04）
import { loadPdfs, initPdfToolbar } from "/js/ui/pdf.js";
import { loadMds, initMdToolbar } from "/js/ui/md.js";
import { renderHwcheckPanel, initHwcheck } from "/js/ui/hwcheck.js";  // 硬件检测栏目（module-hwcheck/01）：选平台 + 预览检测程序（零 LLM）
import { renderPlatforms, renderModulePool, loadReferencePicker, setClusterDeps } from "/js/ui/generate-recommend.js";
import { stepDoneSet, initCardCollapse, setOnStepChange } from "/js/ui/step-state.js";
import { renderInstanceConfig, renderPinCard, loadPinBoard, resetPinState, resetInstances, clearInstanceTarget, backfillInstances, pinChangeCount, configuredInstanceCount } from "/js/ui/generate-pins.js";
import { initMainCTools } from "/js/ui/generate-mainc.js";
import { initScoreChecklist, initGenerateActions } from "/js/ui/generate-core.js";  // initGenerateActions = 生成页动作接线（工单 frontend-boot-module/04）
import { renderToolchainStatus, setToolchains, updateFixCenterAvailability } from "/js/ui/generate-fix.js";
import { initRevise } from "/js/ui/generate-revise.js";  // 修订工坊（工单 frontend-boot-module/03：接线改显式 init，见下面接线区）
import { initTaskProgress } from "/js/ui/generate-tasks.js";  // 任务推进（工单 frontend-boot-module/03：同上）
import { initParams } from "/js/ui/params.js";  // 参数速调（工单 frontend-boot-module/03：同上）
import { initParamsChat } from "/js/ui/params-chat.js";  // 参数速调 AI 咨询（工单 frontend-boot-module/03：同上）
import { initDelivery } from "/js/ui/delivery.js";  // 交付卡（工单 frontend-boot-module/03：同上）
import { initReviseTabs } from "/js/ui/revise-tabs.js";  // 第11步卡内页签（工单 step11-tabs-ui/01）
import { initResourceBoard } from "/js/ui/resource-board.js";  // 资源总览列表/板图切换（resource-overview-polish/02）
import { initWiringToggle } from "/js/ui/wiring.js";  // 接线图「显示全部接线」开关（task-wiring-diagram/04）：document 级 change 委托
import { initWelcome } from "/js/ui/welcome.js";  // 首次欢迎卡 + gen-banner 行动化（newcomer-onboarding/03）
import { initServiceStopped } from "/js/ui/service-stopped.js";  // 服务已停止的可见态（bfcache-return-register/01）：导航走后按后退回来、后端已退出那条路
import { initGlossary } from "/js/ui/glossary.js";  // 生成页底部新手词表（newcomer-glossary/01）
import { initGuide } from "/js/ui/guide.js";  // 新手指引页（beginner-guide/01）：四子页签切换
import { initHandoffNote } from "/js/ui/handoff.js";  // 交接提示词说明 + 去任务推进（newcomer-glossary/03）
import { restoreDraft, scheduleDraftSave, initGenOverview, refreshGenOverview } from "/js/ui/generate-steps.js";
import { refreshReadinessPanel, initReadinessCheck } from "/js/ui/generate-readiness.js";
import { loadLibrary, initLibraryToolbar, initAddSections, initLibraryAddForm } from "/js/ui/library.js";  // initLibraryAddForm = 新建模块表单接线（工单 frontend-boot-module/04）
import { loadReferences, loadKitVocabulary, loadTopicTypes, initReferenceToolbar, initReferenceAddForm } from "/js/ui/reference.js";  // initReferenceAddForm = 参考库录入表单接线（工单 frontend-boot-module/04）
import { loadTopics, loadTopicGroupVocabulary, initTopicPanel } from "/js/ui/topic.js";  // initTopicPanel = 赛题库工具栏 + 拆条/入库接线（工单 frontend-boot-module/04）
import { loadSettings, loadRecentWorkflows, initSettingsCollapse, setSettingsDeps } from "/js/ui/settings.js";
import { initUpdatePanel } from "/js/ui/update.js";  // 设置页「软件更新」区（工单 auto-update/06）
import { initMaterialsUpdate } from "/js/ui/materials-update.js";  // 设置页「资料库更新」区（工单 materials-update/06）
import { initFullUpdate } from "/js/ui/full-update.js";  // 设置页「完整包下载」区（工单 full-download/05）
import { initRecent } from "/js/ui/recent.js";
import { initCodeViewer, checkCodeDiskChanges } from "/js/ui/codeview.js";  // 代码查看器（code-viewer/04-06）：init 加载模块，openCodeViewer 由 recent.js 直接 import；checkCodeDiskChanges = 磁盘基线感知（code-ide-flow/02）
import { initCodeAiChat } from "/js/ui/code-ai-chat.js";  // AI 对话面板（code-ide-ai/03）：选中代码问 AI + 对话历史
import { initCodeFixPanel } from "/js/ui/code-fix-panel.js";  // 修复面板（code-ide-ai/06）：IDE 内跑修复循环（共享状态机双出口）
import { initCodeEditor } from "/js/ui/codeeditor.js";  // 代码编辑器（code-viewer-editor/02）：多标签 + 可编辑三明治 + 保存（/03）/冲突（/04）
import { initCodeCompile } from "/js/ui/code-compile.js";  // 代码栏编译（code-tab-compile/03）：编译按钮 + 底部错误面板 + 错误行跳转
import { initCodeFlash } from "/js/ui/code-flash.js";  // 代码栏烧录（code-editor-utilize/04）：状态栏烧录按钮 + 底部结果面板
import { initCodeTreeOps, initCodeSaveAll } from "/js/ui/code-tree-ops.js";  // 代码树操作（code-tree-ops/02-03）：新建/重命名/删除 + 保存全部
import { initQuickOpen } from "/js/ui/quick-open.js";  // Ctrl+P 快速打开（code-editor-refine/09）：浮层 + 树清单索引
import { initMainCDiskSync } from "/js/ui/generate-mainc-sync.js";  // main.c 磁盘同步（mainc-codeview-bridge/01）：状态行加载按钮委托
import { initSkeletonRefs } from "/js/ui/skeleton-refs.js";  // 骨架引用模块锚定（mainc-codeview-bridge/04）：编辑框下方 chips 委托
import { applyInputA11y } from "/js/ui/a11y.js";  // 裸输入 aria-label 补齐（工单 ux-walkthrough-02/19）
// ---------------------------------------------------------------------------
// 接线区（工单 frontend-boot-module/03-04）
// ---------------------------------------------------------------------------
// 这些模块原先靠"被装载"接线（模块求值期直接绑监听器 / 写首帧 DOM），宿主正文里一个调用点
// 都没有——"点了为什么会有人响应"这件事只写在 import 的副作用里。现在接线住在各模块导出的
// init*() 里，在这里**显式调用**：
//   · 调用顺序 = 上面装载清单里的出现顺序（与改动前"求值期接线"的相对顺序一致）；
//   · 位置在正文最前，等价于原来的"所有 import 求值完 → 才轮到宿主正文"。
// 原 `"use strict";` 一并删掉：ESM 恒严格模式，该指令冗余（评审指出它还会被"列 0 副作用"
// 口径算成一条接线）。
initMasterWorkflow();  // 母版页工具链：选目录 / 扫描 / 提炼 / 确认 / 直接导入（8 条绑定）
initGenerateActions(); // 生成页动作：骨架 / 冒烟 / 恢复备份 / 输出目录 / 交接 / 复制 / 烧录 / 生成（17 条）
initRevise();        // 修订工坊：影响分析 / 执行修订 / 深化 / 回滚（11 条绑定）
initTaskProgress();  // 任务推进：计划 / 重排 / 想法 / 全局商量 / 草稿箱 / 任务卡（24 条绑定）
initParams();        // 参数速调：扫描 / 应用 / 回滚 + 2 条跨簇重置
initParamsChat();    // 参数速调 AI 咨询：开区 / 发送 / 回车 + 3 条跨簇重置
initDelivery();      // 交付卡：首帧渲染 + 2 条跨簇重置 + window 兼容桥
initLibraryAddForm();   // 模块库：新建模块表单 + 文件选择（6 条绑定）
initReferenceAddForm(); // 参考文件库：录入表单 + 文件选择（7 条绑定）
initTopicPanel();       // 赛题库：工具栏 + 拆条 / 确认入库（3 条绑定）
// 注：code-fix-panel 的接线仍旧在文末**启动区**调用（原来就在那里）——它现在顺带承担
// 原先在模块求值期做的 `subscribeFixCenter(fixCb)`，见 ui/code-fix-panel.js。

// 主题切换（工单 ui-polish-5/01）：currentTheme / applyTheme / initTheme 及
// initTheme() 启动调用已迁至 static/js/app.js（阶段 2 工单 02）。

// API 辅助（统一错误提取，detail 是后端的中文 message）：handle / apiGet /
// apiPost / apiPut / apiDelete 已迁至 static/js/app.js（阶段 2 工单 02）。
// KIND_TEXT（平台警告文案映射）已迁至 static/js/app.js（阶段 2 工单 02）。

// 标签会话（启动器模式）：TAB_ID_KEY / tabId 登记与 pagehide sendBeacon 已迁至
// static/js/app.js（阶段 2 工单 02）。**登记（register）后于工单 launcher-exit-race/01
// 又从 app.js 迁到 index.html head 的内联脚本**——它必须早于模块图（服务端见注册表空
// 只等 1.5 秒就停服务，登记迟到会把应用自己的服务关掉）；app.js 只剩注销一半。

// ---------------------------------------------------------------------------
// 页签
// ---------------------------------------------------------------------------
// 页签按钮选择器限定 [data-tab]（bug 修复：裸 nav button 会把生成页
// #step-nav 里的 step-dot 泡泡 / 收起按钮一起绑进页签切换——点击泡泡时
// btn.dataset.tab 为 undefined，section.page 全被剥掉 active → 整页黑屏）
document.querySelectorAll("nav button[data-tab]").forEach((btn) => {
  btn.setAttribute("role", "tab");
  btn.setAttribute("aria-controls", "tab-" + btn.dataset.tab);
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button[data-tab]").forEach((b) => {
      const on = b === btn;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    // roving tabindex 只在按钮所属组内生效（评审整改：全局置 -1 会让其它组
    // Tab 不可达——每个角色 tablist 各自持有一个 tabindex=0）
    const group = btn.closest(".tab-group");
    if (group) {
      group.querySelectorAll("button[data-tab]").forEach((b) => {
        b.tabIndex = b === btn ? 0 : -1;
      });
    }
    document.querySelectorAll("section.page").forEach((s) =>
      s.classList.toggle("active", s.id === "tab-" + btn.dataset.tab));
    // 切页回顶（工单 pdf-layout-flicker/01）：从深滚动位置切到短页时浏览器
    // 会把 scrollY 钳到 0（内容瞬时不足一屏），若内容随后撑高页面视觉就会
    // 「跳一下」；显式回顶消除中间帧差异（IDE 式页签切换惯例）。
    window.scrollTo({ top: 0, behavior: "instant" });
    // 进度条只属于生成流程：切出隐藏，切回按完成数恢复显示
    const gp = $("gen-progress");
    if (gp) gp.classList.toggle("hidden", btn.dataset.tab !== "generate" || stepDoneSet.size === 0);
    if (btn.dataset.tab === "library") loadLibrary();
    if (btn.dataset.tab === "reference") { loadReferences(); loadKitVocabulary(); loadTopicTypes(); }
    if (btn.dataset.tab === "pdf") loadPdfs();
    if (btn.dataset.tab === "md") loadMds();
    if (btn.dataset.tab === "hwcheck") renderHwcheckPanel();  // 硬件检测：进栏目按全局状态渲染平台卡（选过则保留本栏目自己的选择）
    if (btn.dataset.tab === "topic") { loadTopics(); loadTopicGroupVocabulary(); }
    if (btn.dataset.tab === "master") loadMasters();
    if (btn.dataset.tab === "changelog") loadChangelog();
    if (btn.dataset.tab === "settings") { loadSettings(); loadRecentWorkflows(); renderUsageStats(); }
    if (btn.dataset.tab === "code") checkCodeDiskChanges();  // 磁盘基线感知（code-ide-flow/02）：切回代码 tab 重扫磁盘对比基线（干净标签自动重载/脏标签徽章/树徽章）
  });
});
// 顶栏页签键盘导航（工单 ux-walkthrough-02/19）：每个 tab-group 内
// ←/→ 循环、Home/End 首尾（与页内 revise-tabs 行为一致）；激活后焦点
// 跟随切换（点击式 activate——reload 页面即激活）
document.querySelectorAll("nav .tab-group").forEach((group) => {
  group.addEventListener("keydown", (e) => {
    const tabs = Array.from(group.querySelectorAll("button[data-tab]"));
    if (!tabs.length) return;
    const cur = tabs.findIndex((t) => t.classList.contains("active"));
    let next = -1;
    if (e.key === "ArrowRight") next = (cur + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (cur - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    if (cur === -1) next = (e.key === "ArrowLeft" || e.key === "End") ? tabs.length - 1 : 0;  // 组内无激活：方向键从首/尾进入
    tabs[next].click();
    tabs[next].focus();
  });
});

// ---------------------------------------------------------------------------
// 全局状态
// ---------------------------------------------------------------------------
// 生成页推荐簇状态（selectedSlugs / expanded / pythonTemplates / warnings /
// scorePoints / chosenPlatform / currentTopicId / topicPdfTextVisible /
// lastRecommend / recProblem / recommendClarifications / selectedReferenceIds /
// autoReferenceIds / referenceEntries）已随簇迁至 static/js/ui/generate-recommend.js
// （阶段 2 工单 12）：host 经顶部 import 活绑定只读，写入经各 setter
// （setChosenPlatform / setSelectedSlugs / setCurrentTopicId /
// setRecommendClarifications）。instances / instancePinTarget 属引脚-多实例簇，
// 已随工单 13 迁至 static/js/ui/generate-pins.js（host 经 import 活绑定读、经导出函数写）。

// 保存设置后的状态重载（refreshState）已随其唯一调用点（btn-save-settings）
// 迁至 static/js/ui/settings.js（阶段 2 工单 10）：state / modules 重拉 +
// 工具链重算（经 setSettingsDeps 接缝写 generate-fix 的 toolchains（setToolchains） +
// renderToolchainStatus——工单 16 迁出后改静态 import）+ 平台卡 / 模块池重渲染。


// ---------------------------------------------------------------------------
// 生成页：1-3 题面 / 推荐 / 参考选择 + 5 模块池 / 选中 / 警告（推荐簇 A）
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-recommend.js（阶段 2 工单 12）：题面 PDF viewer /
// 上传抽取 / 历史赛题取题面 useTopic / AI 推荐 SSE 流（recPanel / 进度 / 澄清）/
// 参考文件选择器 / 模块池与推荐结果 / 已选清单与副产物模板 / 平台警告与功能组
// 冲突 / 平台卡 renderPlatforms。状态随簇（chosenPlatform / selectedSlugs 等，
// host 经 import 活绑定读、经 setter 写）；host 侧跨簇服务（引脚-多实例 /
// 修复中心 / 草稿）经 setClusterDeps 接缝注册（见启动区），工单 13 / 16 / 18
// 迁出后改静态 import。

// ---------------------------------------------------------------------------
// 生成页：6.5 多实例配置 + 7. 引脚配置（引脚-多实例簇 B）
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-pins.js（阶段 2 工单 13）：实例增删 / 显示名 /
// 颜色 / 板图选脚 / 引脚板图 SVG / 角色清单与锚定菜单 / 总览着色 / 自动配置
// （instList / renderInstanceConfig / renderPinCard / loadPinBoard /
// renderPinBoard / svgPin / renderPinRoles / bindRole / unbindRole /
// showPinMenu 等，共 35 函数 + 4 接缝函数）。状态随簇（instances /
// instancePinTarget / pinBoard / pinBindings / pinUnbound / pinHighlight /
// pinRotation / pinOverview 等——host 经顶部 import 活绑定读；写经导出函数
// resetPinState / resetInstances / clearInstanceTarget / backfillInstances，
// 推荐簇 A 的跨簇服务经 setClusterDeps 注册调用，见启动区）。

// ---------------------------------------------------------------------------
// 生成页：main.c 预览工具（高亮同步 / 字号缩放 / 复制 / 下载 / 全屏）
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-mainc.js（阶段 2 工单 14）：syncMainCHighlight /
// initMainCHighlight / currentCodeZoomPct / applyCodeZoom / initCodeZoom /
// initMainCTools（4 函数 + 2 IIFE）+ 常量 CODE_ZOOM_STEP / CODE_ZOOM_BASE /
// CODE_ZOOM_KEY。host 经顶部 import 活绑定调用 syncMainCHighlight
// （generateMain / restoreDraft 写入后重同步）与 initMainCTools（启动区初始化）。

// ---------------------------------------------------------------------------
// 生成页：8. main.c 骨架 / 自检冒烟 + 生成页：9. 输出目录并生成（成功区 / 桌面输出开关）
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-core.js（阶段 2 工单 15）：SKELETON_MODES +
// generateMain / renderGenerateSuccess + 骨架与
// 冒烟按钮 / 桌面输出开关 / 选目录监听器。host 经顶部 import 调用
// initScoreChecklist；btn-generate
// 覆盖重发监听器亦随迁（工单 20——readinessState 已随工单 19 迁出）。

// 已迁至 static/js/fx/generate.js（工单 08）：collectBindings。

// 已迁至 static/js/fx/generate.js（工单 08）：formatResModules。

// btn-generate 覆盖重发监听器（readiness 前置校验 / payload 组装 / 覆盖确认）已迁至
// static/js/ui/generate-core.js（阶段 2 工单 20 补迁）——现由 initGenerateActions()
// 绑定（工单 frontend-boot-module/04）。

// ---------------------------------------------------------------------------
// 生成页：11. 交接提示词（Handoff）+ 自动附带产物 / 评分点核对清单
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-core.js（阶段 2 工单 15）：renderArtifacts /
// renderScoreChecklist / scoreChecklistIdsNow / scoreChecklistSyncCurrent /
// scoreChecklistExportNow / initScoreChecklist / handoffPlatformLabel /
// handoffPlatformIde / handoffModuleLines / handoffWarnings / handoffPinLines /
// handoffReferenceLines + 交接 / 复制路径 / 复制核对表监听器（由 initGenerateActions()
// 绑定，工单 frontend-boot-module/04）。
// host 启动区只调 initScoreChecklist()。

// ---------------------------------------------------------------------------
// 生成页：10. 修复中心（工单 autocompile-loop/01）——编译修复循环 / 横幅 /
// 结果表 / telemetry / 就绪度
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-fix.js（阶段 2 工单 16）：FIX_MAX_ROUNDS /
// toolchains（export let + setToolchains——主写簇）/ fixLoop / lastFix* /
// fixSourceCache + 25 函数 + 4 监听器（btn-fix-center / btn-fix-continue /
// btn-fix-errors / btn-fix-rollback）。fmtSeconds 已迁 fx/generate.js（工单 16）。
// 更正（工单 export-surface-guard/02）：FIX_MAX_ROUNDS 与 fixLoop 自工单 code-ide-ai/05 起
// 归 static/js/ui/fix-center-core.js（generate-fix.js 只 re-export 过它们）；那条 re-export
// 是零消费者导出，本轮已删。
// host 经顶部 import 调用 renderToolchainStatus / setToolchains /
// updateFixCenterAvailability（启动区与 setSettingsDeps 回调）；generate-core
// 静态 import startFixCenter / compileBanner / toolchains（取代工单 15 的
// 修复中心接缝）。读写迁移组：A 簇仍经 setClusterDeps 闭包调用
// updateFixCenterAvailability（与工单 13 pins 同构）。

// ---------------------------------------------------------------------------
// 修订与深化阶段卡（工单 revise-deepen/05）：影响分析 → 确认修订 → 可选深化
// + 编译验证 → 回滚
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-revise.js（阶段 2 工单 17）：revise 状态对象 +
// 21 函数 + 8 监听器（btn-revise-session / btn-revise-load-dir /
// revise-dir-input Enter / btn-revise-analyze / btn-revise-discard /
// btn-revise-apply / btn-revise-deepen / btn-revise-rollback /
// revise-problem-text input）。host 对本簇零调用点（监听器随簇迁入）。

// ---------------------------------------------------------------------------
// 模块库页
// ---------------------------------------------------------------------------
// 行渲染（library-table-polish/01）：纯函数（喂 tests/js node:test）——
// 简介列单行截断 + title 全文（配合 .desc-cell 样式）；后续工单（详情 /
// 编辑 / 悬空警示）在此扩展行内容。
// —— 模块库工具栏（library-toolbar/02）：过滤 / 排序 / 统计 / chips 纯函数 ——
// 均为顶层纯函数（tests/js 可注入）；DOM 层只做转发，交互逻辑不散落事件里。
// 已迁至 static/js/fx/module.js（工单 06）：模块库工具栏纯函数组——libFilterModules / libSortModules /
// danglingDependencies / libStats / libStatsText / libChipRowHTML / moduleRowHTML。

// ===== 模块库 tab：过滤 / 排序 / 表格 / 加载 / 简介与平台级编辑 / 新建入库 =====
// 已迁至 static/js/ui/library.js（阶段 2 工单 07）：libUI 状态 + renderLibraryChips /
// renderLibraryStats / renderLibraryTable / clearLibraryFilter / initAddSections /
// initLibraryToolbar / loadLibrary / editDescription / editModule / deleteModule /
// newModulePayload + 添加模块表单行监听（btn-add-file-row / btn-draft-desc /
// btn-add-module-submit / 两个 mod 文件选择绑定）。跨簇硬边 openModuleInfo /
// renderModulePool 从 ui/generate-recommend.js import（12 交付后成立）；
// host 页签分发器 / 启动区经顶部 import 调 loadLibrary / initLibraryToolbar /
// initAddSections（见 import 行与启动区）。

// 模块库两个文件选择绑定已随簇迁至 ui/library.js（阶段 2 工单 07）；
// ---------------------------------------------------------------------------
// 参考文件库页：浏览 / 搜索 / AI 简介草稿 / 入库 / 删除（全部已迁 ui/reference.js）
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/reference.js（阶段 2 工单 08）：refUI / refFilterContext /
// refSearchTimer / kitVocabulary / refEntryCache / refTopicKeys 状态 +
// renderReferenceChips / renderReferenceStats / renderReferences /
// clearReferenceFilter / initReferenceToolbar / loadKitVocabulary /
// loadReferences / deleteReference / editReference / referenceFileUrl /
// openReferenceFile / viewReferenceDetail / showReferenceDetail /
// refCollectFiles + 录入表单监听（ref-anchor-kind / btn-ref-add-file-row /
// btn-ref-draft-desc / btn-ref-add / 两个 ref 文件选择绑定）。纯件在
// fx/reference.js（工单 03 迁）；文件行件在 ui/files.js（06 迁）。
// host 页签分发器 / 启动区经顶部 import 调 loadReferences /
// loadKitVocabulary / initReferenceToolbar（见 import 行与启动区）。


// ---------------------------------------------------------------------------
// PDF 资料库页：全部胶水已迁至 static/js/ui/pdf.js（阶段 2 工单 05）；
// 纯件（过滤/排序/统计/健康/行渲染/详情/回收 URL）在 static/js/fx/pdf.js。
// host 只经 tab 分发器调 loadPdfs、经启动 init 调 initPdfToolbar（顶部 import）。
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 赛题库页：浏览 / 过滤 / 拆条录入（逐条校对）/ 删除（已迁 ui/topic.js）
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/topic.js（阶段 2 工单 09）：topicRows / topicPdfFile /
// topicArchiveLoaded / topicUI / topicEntries / topicGroupVocab /
// topicSearchTimer / topicLoading / topicPageCache 状态 + loadTopicArchiveLink /
// topicFilterContext / renderTopicYearChips / renderTopicStats / renderTopics /
// loadTopicPageState / renderTopicPages / viewTopicDetail / viewTopicEdit /
// clearTopicFilter / initTopicToolbar / loadTopicGroupVocabulary / loadTopics /
// deleteTopic / renderProofreadRows + 拆条录入监听（btn-topic-split /
// btn-topic-confirm）。纯件在 fx/topic.js（工单 04 迁）；「用此题生成」
// useTopic 归 ui/generate-recommend.js（工单 12 迁），本模块 import 调用
// （卡片与详情弹窗两处）。host 页签分发器经顶部 import 调 loadTopics /
// loadTopicGroupVocabulary（见 import 行）。


// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// 母版页（扫描 / 整夹暂存 / 提炼 / 报告 / 母版库 / 更新记录）：全部胶水已迁至
// static/js/ui/master.js（阶段 2 工单 04）；纯件（表格行 / 判定行 / 归档行 /
// 详情 / 文件 URL）在 static/js/fx/master.js。host 只经 tab 分发器调
// loadMasters / loadChangelog（顶部 import）。
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 设置页：配置加载 / 保存 / 视觉预设 / 环境体检 / 价格参考 / 单价收集 / 折叠
// 与最近工作流（全部已迁 ui/settings.js）
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/settings.js（阶段 2 工单 10）：loadSettings /
// syncVisionProviderFromFields / applyVisionPreset / envCheckRun /
// renderPriceReference / periodPlaceholders / collectLlmPrices /
// renderRecentWorkflows / loadRecentWorkflows / refreshState + 视觉预设与
// 全部按钮监听（set-vision-provider / btn-vision-selfcheck / btn-env-check /
// price-period / set-local-llm-model / btn-save-settings /
// btn-refresh-recent-wf）。单价表（llmPricesDefaults / setLlmPricesDefaults）
// 属 ui/usage.js（工单 04 前置拆分），本模块经 import 读写活绑定；
// 纯件在 fx/settings.js / fx/workflow.js / fx/env.js。
// host 页签分发器 / 启动区经顶部 import 调 loadSettings / loadRecentWorkflows /
// initSettingsCollapse（见 import 行与启动区）。


// ---------------------------------------------------------------------------
// 生成页步骤导航 / 完成态核心（工单 ui-polish/02）：已迁至
// static/js/ui/step-state.js（阶段 2 工单 12）——STEP_NAV_CARD_SELECTOR /
// stepCard / markStepDone / markStepUndone / unmarkSteps / syncStep7 /
// initStepNav IIFE；host 经顶部 import 调用（syncStep7 已参数化，调用点传
// {platform, expanded, roles, bindings, instances}）与读 stepDoneSet。

// ---------------------------------------------------------------------------
// 生成页草稿自动记忆（工单 ui-polish-3/01）：localStorage 防误刷新丢失
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-steps.js（阶段 2 工单 18）：DRAFT_KEY /
// DRAFT_FIELDS / collectDraftState / draftTimer / scheduleDraftSave /
// clearDraft / restoreDraft + 清除按钮 / 4 输入监听（仍在 import 时绑定——该模块本轮不在
// "显式 init" 范围内，因为它另有 importer，见 spec「实现决策」）。
// host 启动区经顶部 import 调 restoreDraft；A 簇 clusterDeps 注册闭包用
// scheduleDraftSave（host 启动区注册行不变）。

// ---------------------------------------------------------------------------
// 步骤完成集合与顶部进度条（工单 ui-polish-3/02）：STEP_TOTAL / stepDoneSet /
// syncStepDone / renderStepProgress 已迁至 static/js/ui/step-state.js（阶段 2
// 工单 12）；host 经 import 读 stepDoneSet（页签切换 / 总览 / 就绪面板），
// 步骤变化联动总览 / 就绪面板经 setOnStepChange 注册（见启动区）。

// ---------------------------------------------------------------------------
// 生成页就绪总览（工单 gen-overview/01）：顶部步骤 chips + 摘要 + 一键补齐
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-steps.js（阶段 2 工单 18）：GEN_CRITICAL_STEPS /
// GEN_RECOMMENDED_STEPS / genOverviewTitles / genOverviewBadges /
// overviewPlanNow / genOverviewWarn / refreshGenOverview / FOCUS_TARGETS /
// runOverviewFill / initGenOverview（host 启动区经 import 调）。
// refreshGenOverview 对 readinessState 的调用为静态 import（工单 18 接缝已由
// 工单 19 改静态 import）；变化联动经 setOnStepChange 注册。

// ---------------------------------------------------------------------------
// 最近生成（工单 recent-jobs/01）：renderRecentList / refreshRecent /
// reportRecentStatus / initRecent 已迁至 static/js/ui/recent.js（阶段 2
// 工单 11）；纯件在 fx/recent.js（工单 08 迁：recentStatusMeta /
// recentTimeLabel / recentPlatformLabel / recentChipHTML / recentListHTML /
// recentStatusNow）。host 侧调用点：renderGenerateSuccess@3394 refreshRecent、
// fixHandleEvent@4159 reportRecentStatus、启动区 initRecent——均经顶部 import。

// ---------------------------------------------------------------------------
// 检查能否生成（工单 a3-readiness-check/01-02）：判据与 btn-generate 前置校验同源
// ---------------------------------------------------------------------------
// 已迁至 static/js/ui/generate-readiness.js（阶段 2 工单 19）：readinessState /
// renderReadinessPanel / refreshReadinessPanel / initReadinessCheck。host 经
// 顶部 import 调 readinessState（btn-generate 监听器）/ refreshReadinessPanel
//（setOnStepChange 回调）/ initReadinessCheck（启动区）；generate-steps 静态
// import readinessState（工单 18 接缝已删除）。

// ---------------------------------------------------------------------------
// Toast 轻通知（工单 ui-polish-3/03）：toast / TOAST_ICON 已迁至
// static/js/app.js（阶段 2 工单 02）；右上角堆叠 2.5s 自动消失，最多同屏 3 条。
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 生成页卡片折叠（工单 ui-polish-4/01）：CARD_COLLAPSE_SELECTOR / initCardCollapse
// 已迁至 static/js/ui/step-state.js（阶段 2 工单 12）；host 启动区 7935 经 import 调用。

// ---------------------------------------------------------------------------
// 设置页折叠（工单 settings-infoarch/01-03）：saveSettingsCollapse /
// initSettingsCollapse 已迁至 static/js/ui/settings.js（阶段 2 工单 10）；
// 纯件在 fx/settings.js（SETTINGS_COLLAPSE_KEY / parseSettingsCollapse /
// effectiveCollapsed / settingsMasterLabel / settingsSectionHead /
// applySettingsCollapseState 等）。host 启动区 5821 经 import 调用。

// ---------------------------------------------------------------------------
// LLM 用量统计（工单 ui-polish-5/02）：记录服务（recordLLMUsage / 单价表 /
// 会话累计与持久化 / reset）已迁至 static/js/ui/usage.js（阶段 2 工单 04）；
// 纯计算在 fx/llm.js。host 经顶部 import 调 recordLLMUsage（推荐 / 修复 / 修订流）
// 与 renderUsageStats（设置 tab 分发器）。
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 跨簇接缝注册（阶段 2 工单 12）：推荐簇 A 迁出后，模块内对 host 侧跨簇服务的
// 调用经 setClusterDeps / setOnStepChange 注册进来（模块无法 import host 作用域）：
//   - setClusterDeps：引脚-多实例（renderPinCard / renderInstanceConfig /
//     loadPinBoard / resetPinState / resetInstances / clearInstanceTarget /
//     backfillInstances——工单 13 已迁 ui/generate-pins.js，注册改挂静态 import）、修复中心
//     （updateFixCenterAvailability——工单 16 迁）、草稿（scheduleDraftSave——
//     工单 18 迁）。
//   - setOnStepChange：步骤完成态变化 → 总览（refreshGenOverview——工单 18 迁）/
//     就绪面板（refreshReadinessPanel——工单 19 迁）；注册模式避免
//     step-state → generate-steps 环。
setClusterDeps({
  scheduleDraftSave: () => scheduleDraftSave(),
  updateFixCenterAvailability: () => updateFixCenterAvailability(),
  resetPinState,
  resetInstances,
  clearInstanceTarget,
  renderPinCard,
  renderInstanceConfig,
  loadPinBoard,
  backfillInstances,
  pinChangeCount,
  configuredInstanceCount,
});
setOnStepChange(() => { refreshGenOverview(); refreshReadinessPanel(); });
setSettingsDeps({ applyToolchains: (ts) => { setToolchains(ts); renderToolchainStatus(); } });

// ---------------------------------------------------------------------------
// 启动
// ---------------------------------------------------------------------------
(async function init() {
  try {
    setState(await apiGet("/api/state"));
  } catch (e) {
    $("gen-banner").textContent = "加载失败：" + e.message;
    $("gen-banner").classList.remove("hidden");
    return;
  }
  // 未配置 AI API 时模块库读不到（400 提示去设置）——平台卡片必须照常渲染，
  // 首次使用流程（设置 → 导入母版 → 生成）不能死在启动上
  try { state.modules = await apiGet("/api/modules"); }
  catch (e) { state.modules = []; }
  // 工具链可用性（工单 autocompile-loop/01）：一键编译修复按钮的置灰依据
  setToolchains(state.toolchains || { stm32: false, mspm0: false });
  renderToolchainStatus();
  renderPlatforms();
  renderHwcheckPanel();  // 硬件检测栏目平台卡（工单 module-hwcheck/01）：全局状态到达后重渲染一次；之后以本栏目自己的选择为准
  renderModulePool();
  renderPinCard();  // 引脚配置卡（工单 03）：初始占位文案
  renderNewPlatformOptions(state.platforms);
  loadReferencePicker();
  restoreDraft();  // 草稿恢复放最后：依赖上面全部渲染（平台列表 / 模块池）
  initWelcome();  // 首次欢迎卡（newcomer-onboarding/03）：依赖 state / 草稿已就绪
  initGlossary();  // 新手词表（newcomer-glossary/01）：纯静态渲染，DOM 已就绪
  initGuide();  // 新手指引子页签切换（beginner-guide/01）：DOM 已就绪，纯本地交互
  initHandoffNote();  // 交接提示词说明（newcomer-glossary/03）：按钮绑定依赖 DOM 已就绪
  // 首次上手（工单 ux-polish/01）：赛题原文为空（草稿未回填）时自动聚焦，
  // 打开页面即可直接粘贴赛题正文，少一次点击
  if (!$("problem").value.trim()) $("problem").focus();
})();

initGenOverview();  // 生成页就绪总览：依赖 stepDoneSet / step-nav current 已就绪（const TDZ）
applyInputA11y();  // 裸输入 aria-label 补齐（工单 ux-walkthrough-02/19）：DOM 已就绪，幂等
initReadinessCheck();  // 检查能否生成：按钮 + 检查单面板（事件委托）
initMainCTools();  // main.c 工具栏（复制/下载/全屏）：DOM 已就绪，纯本地交互
initMainCDiskSync();  // main.c 磁盘同步状态行（mainc-codeview-bridge/01）：加载按钮委托（DOM 已就绪）
initSkeletonRefs();  // 骨架引用模块锚定（mainc-codeview-bridge/04）：input 防抖 + chips 委托 + 首帧渲染
initRecent();  // 最近生成列表：拉取历史 + 事件委托（复制路径/删除/刷新）
initServiceStopped();  // 服务已停止的可见态（工单 bfcache-return-register/01）：只装监听，不主动显示
initCodeViewer();  // 代码查看器（工单 code-viewer/04）：选择文件夹 / 树 / 视图 / 侧栏接线（DOM 已就绪）
initCodeAiChat();  // AI 对话面板（工单 code-ide-ai/03）：选中代码问 AI + 对话收发接线
initCodeFixPanel();  // 修复面板（工单 code-ide-ai/06）：「在此修复」入口 + 回滚/继续/收起接线
initCodeEditor();  // 代码编辑器（工单 code-viewer-editor/02）：多标签条 / 编辑三明治 / 跳行 / 关闭确认接线
initCodeCompile();  // 代码栏编译（工单 code-tab-compile/03）：编译按钮 / 底部错误面板 / 错误行跳转接线
initCodeFlash();  // 代码栏烧录（工单 code-editor-utilize/04）：烧录按钮 / 底部结果面板接线
initCodeTreeOps();  // 代码树操作（工单 code-tree-ops/02）：新建/重命名/删除按钮与树内委托接线
initCodeSaveAll();  // 保存全部（工单 code-tree-ops/03）：状态栏按钮 + Ctrl+Shift+S
initQuickOpen();  // Ctrl+P 快速打开（工单 code-editor-refine/09）：浮层 + 树清单索引
initScoreChecklist();  // 评分点核对清单：勾选持久化 + 复制核对表（事件委托）
initCardCollapse();  // 放末尾：依赖 CARD_COLLAPSE_SELECTOR / stepDoneSet 已初始化（const TDZ）
initReviseTabs();  // 第11步卡内页签（工单 step11-tabs-ui/01）：DOM 已就绪，纯本地交互
initResourceBoard();  // 资源总览视图切换（resource-overview-polish/02）：document 级委托
initWiringToggle();  // 接线图「显示全部接线」开关（task-wiring-diagram/04）：document 级 change 委托
initSettingsCollapse();  // 设置页折叠：DOM 已就绪，读盘应用默认/记忆状态（首帧前同步执行）
initUpdatePanel();  // 设置页「软件更新」区（工单 auto-update/06）：当前版本 + 检查更新按钮接线
initMaterialsUpdate();  // 设置页「资料库更新」区（工单 materials-update/06）：检查 + 选择弹窗 + 进度
initFullUpdate();  // 设置页「完整包下载」区（工单 full-download/05）：检查 + 确认弹窗 + 进度（无基线时的双轨入口）
initLibraryToolbar();  // 模块库工具栏（工单 02）：搜索 / 排序 / 过滤 chips 事件绑定（DOM 已就绪）
initAddSections();  // 添加模块分区折叠（工单 07）：分区头点击切换（DOM 已就绪）
initReferenceToolbar();  // 参考库工具栏（工单 02）：防抖搜索 / 排序 / chips 事件绑定（DOM 已就绪）
initPdfToolbar();  // PDF 资料库工具栏（工单 02）：防抖搜索 / 排序 / 批次 chips 事件绑定（DOM 已就绪）
initMdToolbar();  // Markdown 资料工具栏（工单 wiki-materials/02）：防抖搜索 / 排序 / 批次 chips 事件绑定（DOM 已就绪）
initHwcheck();  // 硬件检测栏目（工单 module-hwcheck/01）：平台卡 / 通道勾选 / 预览按钮接线（平台卡要等 /api/state → 见启动区 renderHwcheckPanel）
