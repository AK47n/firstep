// 阶段 2 工单 01：index.html 五函数删除 + workflow.js import 行插入（CRLF 感知 + 锚定校验）
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);

// 1) import 行插入：settings.js import 之后（文件物理序最后一条 fx import）
const impIdx = lines.findIndex((l) => l.includes('from "/js/fx/settings.js"'));
if (impIdx < 0) throw new Error("settings.js import not found");
if (lines.some((l) => l.includes('from "/js/fx/workflow.js"'))) throw new Error("workflow import already present");
const impLine = 'import { wfNum, formatWorkflowUsage, formatWorkflowCost, formatWorkflowSummary, formatWorkflowCall } from "/js/fx/workflow.js";';
lines.splice(impIdx + 1, 0, impLine);

// 2) 定义块删除：区段注释（最近 LLM 工作流）→ renderRecentWorkflows 上一行
const cIdx = lines.findIndex((l) => l.includes("最近 LLM 工作流（工单 llm-observability-dashboard/03）：只读内存仪表盘"));
const rIdx = lines.findIndex((l) => l.startsWith("function renderRecentWorkflows(data) {"));
if (cIdx < 0 || rIdx < 0 || rIdx < cIdx) throw new Error("span anchors not found");
if (!lines[cIdx - 1].startsWith("// ----")) throw new Error("prev of comment not dashes: " + JSON.stringify(lines[cIdx - 1]));
if (!lines[cIdx + 1].startsWith("// ----")) throw new Error("comment close not dashes: " + JSON.stringify(lines[cIdx + 1]));
if (!lines[cIdx + 2].startsWith("function wfNum(value) {")) throw new Error("after comment not wfNum: " + JSON.stringify(lines[cIdx + 2]));
if (lines[rIdx - 1].trim() !== "") throw new Error("line before renderRecentWorkflows not blank: " + JSON.stringify(lines[rIdx - 1]));
if (lines[cIdx + 1].includes("已迁至")) throw new Error("already migrated?");
const removed = lines.slice(cIdx - 1, rIdx);
const removedText = removed.join(eol);
for (const name of ["wfNum", "formatWorkflowUsage", "formatWorkflowCost", "formatWorkflowSummary", "formatWorkflowCall"]) {
  if (!new RegExp("function " + name + "\\s*\\(").test(removedText)) throw new Error("missing " + name + " in removed span");
}
const newBlock = [
  "// ---------------------------------------------------------------------------",
  "// 最近 LLM 工作流（工单 llm-observability-dashboard/03）：只读内存仪表盘",
  "// 纯函数已迁至 static/js/fx/workflow.js（阶段 2 工单 01）：wfNum / formatWorkflowUsage /",
  "// formatWorkflowCost / formatWorkflowSummary / formatWorkflowCall；以下为渲染胶水。",
  "// ---------------------------------------------------------------------------",
];
lines.splice(cIdx - 1, removed.length, ...newBlock);

writeFileSync(p, lines.join(eol), "utf8");
console.log("OK: import inserted at 1-based", impIdx + 2, "; removed", removed.length, "lines ->", newBlock.length, "lines");
