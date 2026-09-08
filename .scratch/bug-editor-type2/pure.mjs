// 纯函数验证：winCache.lineStarts 未随单行非结构编辑更新 → 第二次击键的
// editSpan.line 错算到下一行（idx=2），winPatchEdit 写错行导致级联。
import {
  windowTextBuild,
  windowEditToView,
  windowEditToModel,
  windowPosFromView,
} from "../../src/contest_generator/static/js/fx/window-text.js";
import { editChangeSpan } from "../../src/contest_generator/static/js/fx/edit-patch.js";
import { buildLineStarts, caretLineFromStarts } from "../../src/contest_generator/static/js/fx/codeeditor.js";

let model = "line1\n\nline3\nline4\nline5\n";
let lines = model.split("\n");
let lineStarts = buildLineStarts(lines);
let winCache = { lines, text: model, lineStarts, lineCount: lines.length };

const type = (ch) => {
  // 模拟浏览器：在窗口文本 caret 处插入字符
  const w = windowTextBuild(winCache.lines, 0, winCache.lineCount, winCache.lineStarts);
  const winInfo = w;
  const caretView = 6 + (winCache.text.split("\n")[1] || "").length; // 第2行行尾
  const rel = windowPosFromView(winInfo, caretView);
  let taValue = winInfo.text;
  taValue = taValue.slice(0, rel) + ch + taValue.slice(rel);

  // 与 syncEditorAfterInput 窗口化路径同序
  const oldWin = winInfo.text;
  const newWin = taValue;
  const span = editChangeSpan(oldWin, newWin);
  const v = windowEditToView(span, winInfo, winCache.lineStarts);
  const r = windowEditToModel(model, null, winCache.text, winInfo, winCache.lineStarts, newWin);
  const editSpan = {
    structural: span.structural,
    p: v.p,
    oldSegLen: v.oldSegLen,
    newSegLen: v.newSegLen,
    line: caretLineFromStarts(winCache.lineStarts || [], v.p),
  };
  model = r.model;

  // winPatchEdit 快路径（非结构）：idx = span.line - 1
  const idx = editSpan.line - 1;
  const oldText = winCache.text;
  const lineStart = oldText.lastIndexOf("\n", editSpan.p - 1) + 1;
  const nl = newWin.indexOf("\n", lineStart);
  const lineEnd = nl === -1 ? newWin.length : nl;
  const newLineText = newWin.slice(lineStart, lineEnd);
  if (winCache.lines) winCache.lines[idx] = newLineText;
  winCache.text = newWin;
  // 修复行：暂不更新 lineStarts（复现旧行为）

  return { oldWin, newWin, span, v, editSpan, idx, model, text: newWin };
};

const a = type("a");
console.log("after a:", JSON.stringify({ editSpan: a.editSpan, idx: a.idx, model: a.model, lines: winCache.lines }));
const b = type("b");
console.log("after b:", JSON.stringify({ editSpan: b.editSpan, idx: b.idx, model: b.model, lines: winCache.lines }));
const c = type("c");
console.log("after c:", JSON.stringify({ editSpan: c.editSpan, idx: c.idx, model: c.model, lines: winCache.lines }));
