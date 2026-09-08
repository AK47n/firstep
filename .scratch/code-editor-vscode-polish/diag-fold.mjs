// 调试 codeFoldRanges c 用例
import { codeFoldRanges } from "../../src/contest_generator/static/js/fx/code-fold.js";
const text = 'const char *s = "{";\n// }\nint x;\n}\n';
console.log("chars:");
for (let i = 0; i < text.length; i++) {
  console.log(i, JSON.stringify(text[i]));
}
console.log("folds:", JSON.stringify(codeFoldRanges(text, "c")));
