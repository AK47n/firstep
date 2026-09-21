// synthetic-cases.mjs — 薄再导出（工单 module-import-usage/03 收敛单源）。
//
// 合成用例表已搬进 `tests/js/import-usage-cases.mjs`：闸门用例（`import-usage-guard.test.mjs`）
// 必须在**每次前端门禁**里跑同一张表，而闸门不许依赖 `.scratch/` 这种一次性证据目录
// （03 的双轴评审都点了"闸门里抄了第二份表、且已经分叉"）。本文件只为 `.scratch` 侧的红证脚本
// 保留原路径，避免它们各自改 import。
export { CASES, syntheticChecks } from "../../tests/js/import-usage-cases.mjs";
