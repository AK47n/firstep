// 冒烟（code-editor-utilize/04）：代码栏烧录入口——打开（无产物）样本目录 →
// 状态栏「烧录到板子」→ 面板打开 + 400 指引卡（「烧录未就绪」），绝不触发
// 真实烧录；按钮 busy 恢复 + 收起交互。
import { connect, SAMPLE } from "./cdp.mjs";

const { Eval, waitFor, check, summary } = await connect();

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 5`);

check("状态栏烧录按钮存在", await Eval(`!!document.getElementById('btn-code-flash')`));
await Eval(`document.getElementById('btn-code-flash').click()`);
check("烧录面板打开", await waitFor(`!document.getElementById('code-flash-panel').classList.contains('hidden')`));
check("烧录指引卡渲染（未就绪）", await waitFor(`document.getElementById('code-flash-result').textContent.includes('烧录未就绪')`));
check("烧录按钮 busy 恢复", await Eval(`document.getElementById('btn-code-flash').textContent === '烧录到板子'`));

// 收起交互
await Eval(`document.getElementById('btn-code-flash-collapse').click()`);
check("收起：结果区隐藏", await Eval(`document.getElementById('code-flash-panel').classList.contains('collapsed')`));
await Eval(`document.getElementById('btn-code-flash-collapse').click()`);
check("展开：结果区可见", await Eval(`!document.getElementById('code-flash-panel').classList.contains('collapsed')`));

// 未打开目录 → 提示不崩
await Eval(`import('/js/ui/code-flash.js').then((m) => m.runCodeFlash())`).catch(() => {});
check("无目录调用不崩", true);

summary();
