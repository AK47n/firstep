// 诊断（B14-01）：`.step-dot.warn` 与 `.step-dot.current` 同时存在时谁赢？
// 用合成元素做级联实验（不碰真实 DOM 的状态）。
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251;
await rebuildTab({ port: PORT });
const conn = await connect({ port: PORT, timeoutMs: 20000 });
const Eval = (e) => conn.Eval(e);
for (let i = 0; i < 80; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.querySelector('.step-nav .step-dot')`)) break;
  await new Promise((r) => setTimeout(r, 250));
}

const info = await Eval(`(() => {
  const dot = document.querySelector('.step-nav .step-dot');
  const parent = dot.parentElement;
  const mk = (cls, id) => { const n = document.createElement('button'); n.className = cls; n.id = id; parent.appendChild(n); return n; };
  const elCurrent = mk('step-dot current', 'x-a');
  const elWarn = mk('step-dot warn', 'x-b');
  const elBoth = mk('step-dot current warn', 'x-c');
  const elDone = mk('step-dot done', 'x-d');
  const bg = (n) => getComputedStyle(n).backgroundColor;
  const out = {
    real: { cls: dot.className, bg: bg(dot) },
    current: bg(elCurrent), warn: bg(elWarn), bothCurrentAndWarn: bg(elBoth), done: bg(elDone),
  };
  [elCurrent, elWarn, elBoth, elDone].forEach((n) => n.remove());
  return out;
})()`);
console.log(JSON.stringify(info, null, 1));
conn.close();
