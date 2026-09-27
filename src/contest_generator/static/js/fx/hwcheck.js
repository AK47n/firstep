// fx/hwcheck.js — **过渡态 barrel**（工单 hwcheck-hygiene/09）：本文件只剩再导出，
// 由 10 号单删除（届时消费者改指下面这六个模块）。
//
// 为什么让它活一笔提交：1380 行按职责拆成六件是"零行为变化"的机械搬迁，却有 2600 行移动量。
// 这一步让**搬迁**与**迁移消费者**分成两笔 diff：消费者里的 import **一个字没动**
//（`ui/hwcheck.js` 与用例仍指 `/js/fx/hwcheck.js`）；跟着搬的只有两处**读源码文件**的断言
//（`tests/js/hwcheck.test.mjs` 的「fx 不得 import ui / 碰 DOM / 发请求」改成对六件逐个断言、
// `tests/test_hwcheck.py` 两处读路径改指新家）——钉在旧路径上它们要么恒真、要么红。
// 搬漏了什么由 tests/js/hwcheck-split-integrity.test.mjs
// 按搬前快照（.scratch/hwcheck-hygiene/fx-hwcheck-before-split.js）逐名逐字对账。
//
// 六件（按职责；它们之间的单向依赖写在 `hwcheck-state.js` 头部——那份是单源）：
//   hwcheck-state.js    状态归一 / 载荷 / 平台卡 / 提示与错误文案
//   hwcheck-project.js  生成请求 / 编译降级 / 上板清单 / 最近几次检测 / 工程面板
//   hwcheck-wiring.js   器件选择 / 接线表 / 默认脚冲突 / 建议顺序
//   hwcheck-plan.js     逐件小节 / 未专精点名 / 命令台 / 自建件计划
//   hwcheck-triage.js   现象回填 / AI 排障
//   hwcheck-handoff.js  检测页 → 生成页衔接
//
// ⚠ barrel **不再**发布 window 桥条目（桥由六件各自发布自己那一段，并集与搬前逐名相同）：
// 旧文件底部那一块 `Object.assign(window, …)` 已按声明的归属拆到六件里。

export {
  hwcheckPlatformState, hwcheckSelectPlatform, HWCHECK_CHANNEL_KEYS,
  hwcheckPickState, hwcheckRequestPayload, hwcheckDeviceSlugs,
  hwcheckCanPreview, hwcheckPlatformCardsHTML, hwcheckHintHTML,
  hwcheckErrorHTML, hwcheckGenerateErrorHTML, hwcheckDroppedNoteHTML,
  hwcheckEmptyHTML, hwcheckPanelHTML, hwcheckCodeTarget,
  hwcheckPreviewState, hwcheckPlatformLabel,
} from "./hwcheck-state.js";

export {
  hwcheckGeneratePayload, hwcheckChecklistKey, hwcheckCheckedIds,
  hwcheckChecklistToggle, hwcheckChecklistHTML, hwcheckChecklistProgressHTML,
  hwcheckBoardState, hwcheckProjectState, hwcheckChannelText,
  hwcheckProjectInfoHTML, hwcheckToolchainNote, hwcheckChannelNoteHTML,
  hwcheckUnverifiedNoteHTML, hwcheckActionsHTML, hwcheckProjectPanelHTML,
  hwcheckRecentHTML, hwcheckRecentEmptyHTML, hwcheckProjectEmptyHTML,
  HWCHECK_PARENT_KEY, HWCHECK_LAST_DIR_KEY,
} from "./hwcheck-project.js";

export {
  hwcheckDevicePick, hwcheckDeviceGroupNoticeHTML, hwcheckDevicePool,
  hwcheckDeviceKit, hwcheckDeviceChipsHTML, hwcheckDeviceEmptyHTML,
  hwcheckMissingDevicesHTML, hwcheckPinFixHTML, hwcheckPinCapacityNoteHTML,
  hwcheckWiringTableHTML, hwcheckBoardSharesHTML, hwcheckPinGroupsHTML,
  hwcheckOrderDesc, hwcheckOrderHTML,
} from "./hwcheck-wiring.js";

export {
  hwcheckSectionsState, hwcheckSectionPlanText, hwcheckSectionNoteHTML,
  hwcheckSectionsHTML, hwcheckUnspecializedHTML, hwcheckSectionsEmptyHTML,
  hwcheckConsoleState, hwcheckConsoleNoteHTML, hwcheckConsoleHTML,
  hwcheckCustomState, hwcheckCustomPlanHTML, hwcheckCustomWiringHTML,
} from "./hwcheck-plan.js";

export {
  hwcheckSymptomText, hwcheckCanTriage, hwcheckTriagePayload,
  hwcheckChecklistPayload, hwcheckAdviceState, hwcheckRecordState,
  hwcheckChecklistState, hwcheckTriageErrorHTML, hwcheckAdviceEmptyHTML,
  hwcheckAdviceHTML,
} from "./hwcheck-triage.js";

export {
  hwcheckHandoffPlan, hwcheckHandoffMerge, hwcheckHandoffPinNote,
  hwcheckHandoffResultText, hwcheckHandoffHTML,
} from "./hwcheck-handoff.js";
