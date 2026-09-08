// 调试 bracketPairAt（02）
import { bracketPairAt } from "../../src/contest_generator/static/js/fx/code-brackets.js";
const tt = 'printf("("); // (\nif (a) {}\n';
const realOpen = tt.indexOf("(a)");
console.log("idx ('(a)') =", realOpen);
console.log("pairAt(realOpen):", JSON.stringify(bracketPairAt(tt, realOpen)));
console.log("pairAt(realOpen+1):", JSON.stringify(bracketPairAt(tt, realOpen + 1)));
