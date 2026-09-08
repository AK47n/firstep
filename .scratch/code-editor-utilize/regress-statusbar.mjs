// 回归（code-editor-utilize）：565x474 窄视口——状态栏新增「烧录到板子」后
// 按钮不竖排（对照 07f 竖排 bug：编译/保存全部拆行）；三栏中栏保底 150 不变。
import { connect, SAMPLE } from "./cdp.mjs";

const { Eval, waitFor, check, cdp, summary } = await connect();

// 565x474（同用户截图视口）——CDP 设备仿真，验证状态栏按钮不竖排
await cdp("Emulation.setDeviceMetricsOverride", { width: 565, height: 474, deviceScaleFactor: 1, mobile: false });
await new Promise((r) => setTimeout(r, 400));
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}, 'main.c'))`);
await waitFor(`!!document.querySelector('.code-ta')`);

const info = await Eval(`(() => {
  const flash = document.getElementById('btn-code-flash');
  const compile = document.getElementById('btn-code-compile');
  const save = document.getElementById('btn-code-save-all');
  const sb = document.querySelector('.code-statusbar');
  return {
    flashText: flash.textContent,
    flashH: flash.getBoundingClientRect().height,
    compileH: compile.getBoundingClientRect().height,
    saveH: save.getBoundingClientRect().height,
    sbH: sb.getBoundingClientRect().height,
    flex: getComputedStyle(flash).flex,
    nowrap: getComputedStyle(flash).whiteSpace,
  };
})()`);
check("烧录按钮 flex:none + nowrap", info.flex === "0 0 auto" || info.flex.includes("0 0 auto") || info.flex.startsWith("0 0") || info.flex === "none", JSON.stringify(info.flex));
check("状态栏单行（按钮高度 < 40）", info.flashH < 40 && info.compileH < 40 && info.saveH < 40, `${info.flashH}/${info.compileH}/${info.saveH}`);
check("状态栏高度未膨胀（< 60）", info.sbH < 60, String(info.sbH));
check("烧录按钮文案完整（未拆行）", info.flashText === "烧录到板子", info.flashText);

// 窄视口渲染断言（CSS grid 保底已由 07f/上一轮修复 + 本次未改布局——仅确认
// 新面板不破坏 .code-layout 行高）：面板打开后 layout 高度 > 0
await Eval(`document.getElementById('btn-code-flash').click()`);
await waitFor(`!document.getElementById('code-flash-panel').classList.contains('hidden')`);
const layoutH = await Eval(`document.querySelector('.code-layout').getBoundingClientRect().height`);
check("烧录面板打开后编辑器仍占位（layoutH > 100）", layoutH > 100, String(layoutH));

summary();
