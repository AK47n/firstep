// fx-guard.test.mjs — 前端纯函数模块化结构护栏（工单 frontend-es-modules/11）：
// 全部已搬名称（工单 01-10 累计）必须仍在 fx 模块导出，且 index.html 不得再出现
// 其 function/const 定义（双源回退即漂移——防回退语义同 v5 结构测试「not hasattr」）。
// 后续迁移批次把新名称登记进 DOMAINS 表即可；建议新域文件命名照规范
// fx/<domain>.js（模块约定见 fx/core.js 头部）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 全部已搬名称 + 期望形态：fn = 函数（含 async）；否则为期望 typeof 字符串
const DOMAINS = {
  "core.js": {
    esc: "fn", formatSize: "fn", fmtClock: "fn", fmtDuration: "fn", truncate: "fn",
  },
  "env.js": {
    ENV_BADGE_GLYPH: "object",
    envRowHTML: "fn", envChannelHTML: "fn", envCheckStatusHTML: "fn",
  },
  "btn-icon.js": { btnIcon: "fn" },
  "platform.js": { platformClickAction: "fn" },
  "code.js": {
    cHighlight: "fn", cLineCount: "fn", codeZoomClamp: "fn", parseZoomStored: "fn",
    maincLineOffsetRange: "fn", isMainCPath: "fn", maincContentEmpty: "fn",
    maincFullscreenLabel: "fn", maincScrollToRange: "fn", maincJumpToLine: "fn",
  },
  "pdf.js": {
    pdfEncodedPath: "fn", pdfSubdir: "fn", formatMtime: "fn", pdfBroken: "fn",
    pdfBadgeTags: "fn", pdfDupGroups: "fn", pdfHealth: "fn",
    pdfFilterEntries: "fn", pdfSortEntries: "fn", pdfStats: "fn",
    pdfStatsText: "fn", pdfChipRowHTML: "fn", pdfRowHTML: "fn",
    pdfPagesUrl: "fn", pdfPagesText: "fn", pdfDetailHTML: "fn",
    pdfTrashUrl: "fn", pdfDupRemainText: "fn", pdfTrashConfirmHTML: "fn",
    pdfFileUrl: "fn",
  },
  "reference.js": {
    referencePlatformChip: "fn",
    referenceTopicTypeChip: "fn",
    refFilterEntries: "fn", refDanglingAnchors: "fn", refSortEntries: "fn",
    refStats: "fn", refStatsText: "fn", refMatchFiles: "fn", refAnchorBadge: "fn",
    refChipRowHTML: "fn", refRowHTML: "fn", refDetailHTML: "fn",
    refEditState: "fn", refEditValidate: "fn", refEditFilePlan: "fn",
    refEditPayload: "fn",
  },
  "topic.js": {
    topicHasNotes: "fn", topicGroupVocabulary: "fn", topicDanglingGroups: "fn",
    topicHealthText: "fn", topicFilterEntries: "fn", topicSortEntries: "fn",
    topicStats: "fn", topicStatsText: "fn", topicChipRowHTML: "fn",
    topicDetailHTML: "fn", topicPagesHTML: "fn", topicPagesErrorHTML: "fn",
    topicEditHTML: "fn", topicEditValidate: "fn", topicEditPayload: "fn",
    topicCardHTML: "fn",
  },
  "master.js": {
    masterTableRowHTML: "fn", masterDeleteConfirmHTML: "fn", masterFileURL: "fn",
    masterKeyFileRowHTML: "fn", masterDetailHTML: "fn", decisionItem: "fn",
    archiveItem: "fn",
  },
  "module.js": {
    moduleBadges: "fn", pythonArtifactSummary: "fn", groupOfSlug: "fn",
    applyGroupRadio: "fn", autoAddDedup: "fn", groupConflicts: "fn",
    renderGroupCards: "fn", groupRequirementNote: "fn",
    moduleGridPlatformLabel: "fn", moduleGridStatusText: "fn",
    moduleGridBadgeClass: "fn", moduleGridFilter: "fn", moduleGridCountText: "fn",
    moduleGridHTML: "fn", moduleInfoHTML: "fn", multiInstanceModules: "fn",
    instancePayload: "fn", ensureDefaultInstances: "fn",
    libFilterModules: "fn", libSortModules: "fn", danglingDependencies: "fn",
    libStats: "fn", libStatsText: "fn", libChipRowHTML: "fn",
    moduleRowHTML: "fn", editDescStatus: "fn", libIsValidHttpUrl: "fn",
    libPlatformKits: "fn",
  },
  "overview.js": {
    genOverviewChipsHTML: "fn", genOverviewSummaryHTML: "fn", overviewFillPlan: "fn",
    overviewReadyToGenerate: "fn", cardStepStatusHTML: "fn", hasWarnContent: "fn",
  },
  "draft.js": {
    stepNavTitles: "fn", stepNavItemsHTML: "fn", stepNavCurrent: "fn",
    draftState: "fn", draftSave: "fn", draftLoad: "fn", draftRestoreMeta: "fn",
    stepProgress: "fn", step7DoneState: "fn", syncStep4: "fn",
  },
  "generate.js": {
    CONFLICT_MSG_PREFIX: "string",
    isConflictError: "fn", conflictDirName: "fn", genStageTexts: "fn",
    fmtWait: "fn", generationOutputDirPayload: "fn", collectBindings: "fn",
    formatResModules: "fn", attachCelebrate: "fn", collapseBtnLabel: "fn",
    syncCollapseBtn: "fn", collapseToggleAll: "fn", fmtSeconds: "fn",
    frameworkNoteHTML: "fn",
  },
  "recommend.js": {
    suggestionSolutionBadges: "fn", suggestionOptionRowHTML: "fn",
    suggestionOptionsHTML: "fn", suggestionChipHTML: "fn",
    BUY_DECISIONS_KEY: "string", decisionBadgeHTML: "fn", reviewBadgeHTML: "fn",
    decisionPayload: "fn", suggestionKey: "fn", loadBuyDecisions: "fn",
    saveBuyDecisions: "fn", matchBuyDecision: "fn", discussionAreaHTML: "fn",
  },
  "recent.js": {
    recentStatusMeta: "fn", recentTimeLabel: "fn", recentPlatformLabel: "fn",
    recentChipHTML: "fn", recentListHTML: "fn", recentStatusNow: "fn",
  },
  "readiness.js": {
    generateReadinessChecks: "fn", readinessSoftChecks: "fn",
    readinessRowHTML: "fn", readinessRowsHTML: "fn",
  },
  "llm.js": {
    formatLLMTelemetry: "fn", parseSSE: "fn", usageDelta: "fn",
    usageAccumulate: "fn", llmCostEstimate: "fn", usageDisplay: "fn",
  },
  "score.js": {
    formatScorePoints: "fn", renderScorePointPanel: "fn",
    scoreChecklistPartLabel: "fn", scoreChecklistScoreText: "fn",
    scoreChecklistRefsText: "fn", scoreChecklistId: "fn",
    scoreChecklistChecked: "fn", scoreChecklistLineText: "fn",
    scoreChecklistKey: "fn", scoreChecklistItemsHTML: "fn",
    scoreChecklistProgressHTML: "fn", scoreChecklistExportText: "fn",
    scoreChecklistParse: "fn", scoreChecklistLoad: "fn",
    scoreChecklistSave: "fn",
  },
  "task.js": {
    taskStatusLabel: "fn", taskStatusBadgeClass: "fn", taskVerifyLabel: "fn",
    taskScoreRefsText: "fn", taskCardHTML: "fn", tasksGridHTML: "fn",
    tasksProgressText: "fn", tasksOverviewHTML: "fn",
    taskStepReportHTML: "fn", taskNextActionHTML: "fn",
    verifyStatusMarkup: "fn", taskCardActions: "fn",
    taskCanFeedback: "fn", taskIterationLabel: "fn", taskIterationsHTML: "fn",
    taskLatestFeedbackNote: "fn",
    taskOrderLabel: "fn", taskDialogAdoptHTML: "fn", taskDialogButtonHTML: "fn",
    taskDialogAreaHTML: "fn",
    nextTaskHint: "fn", taskNextHintHTML: "fn",
    ideaResultHTML: "fn", taskNeedsRedoBadge: "fn",
    taskStepReportBlocksHTML: "fn",
    globalChatHTML: "fn", globalNoteBadgeHTML: "fn",
    taskEditFormHTML: "fn", taskMoreMenuHTML: "fn",
    ideaDraftListHTML: "fn",
    taskResourcesHTML: "fn", resourceIsHardware: "fn", aggregateResourceGroups: "fn", resourcesOverviewHTML: "fn",
    scoreRefsOverviewHTML: "fn",
    taskChecklistHTML: "fn", checklistStateKey: "fn",
    taskErrorsHTML: "fn", tasksDoneCount: "fn",
    unresolvedPrereqs: "fn",
  },
  "flash.js": {
    flashBusyText: "fn", flashResultHTML: "fn", flashGuideHTML: "fn",
    flashOutputHTML: "fn", flashCommandHTML: "fn", flashPanelHTML: "fn",
    flashContainer: "fn",
  },
  "diff.js": {
    mainDiffHTML: "fn", diffStatsLineHTML: "fn",
  },
  "delivery.js": {
    deliveryActionsHTML: "fn", deliveryCheckHTML: "fn", deliveryPackageHTML: "fn",
  },
  "params.js": {
    paramListHTML: "fn", paramResultHTML: "fn",
  },
  "params-chat.js": {
    paramsChatMessageHTML: "fn", paramsChatInputHTML: "fn", paramsChatHTML: "fn",
  },
  "settings.js": {
    SETTINGS_COLLAPSE_KEY: "string", SETTINGS_DEFAULT_COLLAPSED: "object",
    parseSettingsCollapse: "fn", settingsDefaultCollapsed: "fn",
    effectiveCollapsed: "fn", settingsMasterLabel: "fn",
    sectionCollapseLabel: "fn", settingsSectionHead: "fn",
    applySettingsCollapseState: "fn",
  },
  "workflow.js": {
    wfNum: "fn", formatWorkflowUsage: "fn", formatWorkflowCost: "fn",
    formatWorkflowSummary: "fn", formatWorkflowCall: "fn",
  },
  "revise-tabs.js": {
    REVISE_TABS: "object",
    revisePanelFor: "fn", reviseTabsHTML: "fn", reviseTabBadge: "fn",
    reviseTabNext: "fn",
  },
};

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

for (const [file, names] of Object.entries(DOMAINS)) {
  test(`fx/${file}：已搬名称单源在模块，index.html 无定义（防双源回退）`, async () => {
    const mod = await import(new URL("../../src/contest_generator/static/js/fx/" + file, import.meta.url));
    const missing = [];
    const redefined = [];
    for (const [name, kind] of Object.entries(names)) {
      if (kind === "fn") {
        if (typeof mod[name] !== "function") missing.push(name);
        if (new RegExp("function\\s+" + escapeRe(name) + "\\s*\\(").test(html)) redefined.push(name);
      } else {
        if (typeof mod[name] !== kind) missing.push(name + "（期望 " + kind + "）");
        if (new RegExp("const\\s+" + escapeRe(name) + "\\s*=").test(html)) redefined.push(name);
      }
    }
    assert.deepEqual(
      missing, [],
      `fx/${file} 缺少导出或类型不符：${missing.join(", ")}`
    );
    assert.deepEqual(
      redefined, [],
      `index.html 重新定义了（双源回退）：${redefined.join(", ")}`
    );
  });
}
