// 最终截图（code-editor-utilize）：565x474 视口——打开的编辑器 + 状态栏
// （含烧录按钮）+ 烧录面板展开；另拍一张替换面板。
import { writeFileSync } from "node:fs";
import { connect, SAMPLE } from "./cdp.mjs";

const { Eval, waitFor, cdp } = await connect();

await cdp("Emulation.setDeviceMetricsOverride", { width: 565, height: 474, deviceScaleFactor: 1, mobile: false });
await new Promise((r) => setTimeout(r, 400));

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}, 'main.c'))`);
await waitFor(`!!document.querySelector('.code-ta')`);
await Eval(`document.getElementById('btn-code-flash').click()`);
await waitFor(`!document.getElementById('code-flash-panel').classList.contains('hidden')`);
await Eval(`window.scrollTo(0, document.body.scrollHeight)`);
await new Promise((r) => setTimeout(r, 500));

const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/code-editor-utilize/final-565-flash.png", Buffer.from(shot.result.data, "base64"));

// 替换面板截图（展开侧栏搜索）
await Eval(`(() => { const b = document.querySelector('[data-code-side="search"]'); if (b) b.click(); })()`);
await Eval(`(() => {
  const f = document.getElementById('code-find-input');
  f.value = 'main'; f.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 400));
const shot2 = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/code-editor-utilize/final-565-replace.png", Buffer.from(shot2.result.data, "base64"));

console.log("截图完成");
process.exit(0);
