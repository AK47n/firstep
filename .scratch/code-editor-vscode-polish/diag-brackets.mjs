// 调试 bracketPairAt
import { bracketPairAt } from "../../src/contest_generator/static/js/fx/code-brackets.js";
const t = "f(g(h))";
console.log("outer(1):", JSON.stringify(bracketPairAt(t, 1)));
console.log("inner(3):", JSON.stringify(bracketPairAt(t, 3)));
const tt = 'printf("("); // (\nif (a) {}\n';
console.log("strFake:", tt.indexOf('"(') + 1, JSON.stringify(bracketPairAt(tt, tt.indexOf('"(') + 1)));
console.log("realClose:", tt.indexOf(');'), JSON.stringify(bracketPairAt(tt, tt.indexOf(');'))));
console.log("printfOpen:", tt.indexOf("printf("), "=>", JSON.stringify(bracketPairAt(tt, tt.indexOf("printf("))));
