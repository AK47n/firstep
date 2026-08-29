// fx/reset.js — 「重置本地记录」键判定纯件（工单 reset-local-records/02）
//
// 清理清单单源：哪些 localStorage 键属于「题相关记录」（换题前应清），
// 哪些是 UI 偏好 / 会话态（必须保留）。胶水层（ui/settings.js）遍历
// localStorage 逐键判定 → 移除 → 计数；本模块只做纯判定（fx 无副作用
// 约定：不碰 localStorage）。
//
// 题相关记录（换题即失效）：
//   firstep.checklist.v1.*        任务按步自检勾选（每步一次，过题即废）
//   firstep.draft.v1              生成页题面草稿（上一题的题目文本）
//   score-checklist:<output_dir>  评分点核对勾选（绑定具体工程目录）
//   firstep.buy-decisions.v1      购买决策记忆（AI 推荐流程已定结论恢复）
// 保留（UI 偏好 / 全局统计 / 会话态）：
//   firstep.theme / firstep.mainc.zoom / firstep.settingsCollapse.v1 /
//   firstep.usage.v1（全局用量统计，非题数据）；firstep_tab_id 在
//   sessionStorage，不在清理范围。

/** 精确匹配的键（全等）。 */
export const RESETTABLE_EXACT_KEYS = [
  "firstep.draft.v1",
  "firstep.buy-decisions.v1",
];

/** 前缀匹配的键（前匹配即算题相关）。 */
export const RESETTABLE_KEY_PREFIXES = [
  "firstep.checklist.v1.",
  "score-checklist:",
];

/** 单个键是否属于可重置的题相关记录。 */
export function isResettableKey(key) {
  if (!key) return false;
  return RESETTABLE_EXACT_KEYS.includes(key)
    || RESETTABLE_KEY_PREFIXES.some((p) => key.startsWith(p));
}

/** 从键列表挑出全部可重置键（保序、去重）——胶水层收集 localStorage
 * 键名后调用，计数与移除都基于返回值（清除清单与判定单源一致）。 */
export function collectResettableKeys(keys) {
  return [...new Set(keys.filter((k) => isResettableKey(k)))];
}
