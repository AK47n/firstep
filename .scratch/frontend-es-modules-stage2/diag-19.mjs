// 诊断：模拟 apply-19 的 steps 替换
import { readFileSync } from "node:fs";
let s = readFileSync("src/contest_generator/static/js/ui/generate-steps.js", "utf8");
const seamRe = /const stepsDeps = \{ readinessState: null \};\r?\n\/\/ readiness 簇服务（host 注册）：refreshGenOverview 的「生成按钮就绪」判定。\r?\n\/\/ 工单 19 迁出 readineess 簇后改静态 import。\r?\nfunction setStepsDeps\(deps\) \{ Object\.assign\(stepsDeps, deps\); \}\r?\n\r?\n/;
console.log("seamRe:", seamRe.test(s));
const seamNoteRe = /\/\/ 跨簇服务（host 内联暂不可静态 import）：readinessState（readiness 簇，\r?\n\/\/ 工单 19 迁出后改静态 import）经 setStepsDeps 接缝注册（index.html 启动区）。/;
console.log("noteRe:", seamNoteRe.test(s));
const impAnchor = 'import { generateReadinessChecks } from "/js/fx/readiness.js";';
console.log("impAnchor:", s.includes(impAnchor));
console.log("callReplaced:", s.includes("stepsDeps.readinessState()"));
s = s.replace("stepsDeps.readinessState()", "readinessState()");
console.log("afterCall:", s.includes("stepsDeps"));
console.log("tailRefS:", s.slice(0, 40));
