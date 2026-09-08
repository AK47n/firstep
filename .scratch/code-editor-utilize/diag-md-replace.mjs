// 诊断 smoke-03 md 预览替换失败：重开流程并 dump 关键状态。
import { connect, SAMPLE } from "./cdp.mjs";

const { Eval, waitFor } = await connect();

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}, '设计报告草稿.md'))`);
await waitFor(`!!document.querySelector('.code-md-preview')`);
await Eval(`(() => {
  const f = document.getElementById('code-find-input');
  f.value = '系统'; f.dispatchEvent(new Event('input', { bubbles: true }));
  if (!document.querySelector('.code-md-preview')) document.getElementById('code-back-preview').click();
})()`);
await waitFor(`!!document.querySelector('.code-md-preview')`);
const before = await Eval(`(() => ({
  previewActive: !!document.querySelector('.code-md-preview'),
  findVal: document.getElementById('code-find-input').value,
  replaceVal: document.getElementById('code-replace-input').value,
  activeTabPath: document.querySelector('.code-tab.on')?.dataset?.tabPath,
}))()`);
console.log("BEFORE", JSON.stringify(before, null, 2));
await Eval(`document.getElementById('btn-code-replace-all').click()`);
await new Promise((r) => setTimeout(r, 1500));
const after = await Eval(`(() => ({
  ta: !!document.querySelector('.code-ta'),
  taVal: document.querySelector('.code-ta')?.value || null,
  findVal: document.getElementById('code-find-input').value,
  dirLabel: document.getElementById('code-dir-label').textContent,
}))()`);
console.log("AFTER", JSON.stringify(after, null, 2));
process.exit(0);
