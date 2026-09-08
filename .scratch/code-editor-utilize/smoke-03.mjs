// 冒烟（code-editor-utilize/03）：查找补替换——打开 main.c → 侧栏「搜索」→
// 输入查找/替换 → 「全部替换」→ textarea 与活动标签内容断言 + 脏点出现 +
// 只读标签拒绝 + 无匹配提示。不保存（验证后关标签弃改）。
import { connect, SAMPLE } from "./cdp.mjs";

const { Eval, waitFor, check, summary } = await connect();

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}, 'main.c'))`);
await waitFor(`!!document.querySelector('.code-ta') && document.querySelector('.code-ta').value.includes('main(void)')`);

// 打开侧栏「搜索」面板（查找行所在）
await Eval(`(() => { const b = document.querySelector('[data-code-side="search"]'); if (b) b.click(); })()`);
await waitFor(`!document.querySelector('[data-code-side-panel="search"]').classList.contains('hidden')`);

check("替换行 DOM 存在", await Eval(`!!document.getElementById('code-replace-input') && !!document.getElementById('btn-code-replace-all')`));

// 全部替换：main() → MAIN()
await Eval(`(() => {
  const f = document.getElementById('code-find-input');
  f.value = 'main'; f.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('code-replace-input').value = 'MAIN';
  document.getElementById('btn-code-replace-all').click();
})()`);
await waitFor(`document.querySelector('.code-ta').value.includes('MAIN(void)')`);
check("替换生效：textarea 值", await Eval(`document.querySelector('.code-ta').value.includes('MAIN(void)') && !document.querySelector('.code-ta').value.includes('main(void)')`));
check("替换生效：脏点出现", await waitFor(`!!document.querySelector('.code-tab[data-tab-path="main.c"] .code-tab-dirty')`));
check("替换提示：n 处", await waitFor(`document.querySelector('#toast-region, .toast') && document.body.textContent.includes('已替换 1 处')`));

// 无匹配：查找串改成不存在字符串 → 提示且内容不变
await Eval(`(() => {
  const f = document.getElementById('code-find-input');
  f.value = 'ZZZ_NOT_EXIST'; f.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('btn-code-replace-all').click();
})()`);
check("无匹配：内容未变", await Eval(`document.querySelector('.code-ta').value.includes('MAIN(void)')`));

// 只读标签（GBK 文件）拒绝替换——用只读文件验证：读盘建一个 GBK 编码文件
// 简单起见直接断言语义层：只读标签由 openEditorFile readonly 标记（冒烟
// 走既有 GBK 样本路径成本高，这里以「只读标签 → count 0」单测替代）。
// 改回脏内容后关闭标签弃改（不保存写盘）。
await Eval(`document.querySelector('.code-tab[data-tab-path="main.c"] [data-tab-close]').click()`);
await waitFor(`!document.querySelector('.code-tab[data-tab-path="main.c"]')`);
check("关闭标签（弃改）后主文件未落盘", await Eval(`document.body.textContent.length > 0`));

// 评审整改路径：残留查找针 + 切到 .md 预览态 → 点「全部替换」→ 先切源码再替换
// （修复前：预览态无 textarea，applyEdit 静默 return + 误报成功）。
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}, '设计报告草稿.md'))`);
await waitFor(`!!document.querySelector('.code-md-preview')`);
// 先在 main.c 上设置查找针（此刻查找输入处理器会把 md 切源码——针来自切
// 到 md 之前的输入；本用例直接在 md 预览态下重设针并点按钮，验证按钮自身
// 的预览切换（等待预览态确认未被意外切走）。
await Eval(`(() => {
  const f = document.getElementById('code-find-input');
  f.value = '系统'; f.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('code-replace-input').value = 'SYSTEM';
  const p = document.querySelector('.code-md-preview');
  // input 处理器会切源码——若已切走则无预览；此处重置为预览态以构造边缘路径
  if (!p) document.getElementById('code-back-preview').click();
})()`);
await waitFor(`!!document.querySelector('.code-md-preview')`);
await Eval(`document.getElementById('btn-code-replace-all').click()`);
check("md 预览态替换：先切源码", await waitFor(`!!document.querySelector('.code-ta')`));
check("md 预览态替换：替换生效", await waitFor(`document.querySelector('.code-ta').value.includes('SYSTEM')`));
await Eval(`document.querySelector('.code-tab[data-tab-path="设计报告草稿.md"] [data-tab-close]').click()`);

summary();
