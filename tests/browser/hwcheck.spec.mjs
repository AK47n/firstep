// tests/browser/hwcheck.spec.mjs — 真机验收（工单 module-hwcheck/02）：
// **真浏览器 + 真后端**把「硬件检测」栏目点一遍——预览 → 生成检测工程 → 真编译
// → 上板清单勾选 → 刷新回显 → 最近几次检测。
//
// 为什么要有这一层：`tests/js/*.test.mjs` 是纯函数 + 静态接线断言——它能证明
// 「fx 渲染出的 HTML 里有 data-hwcheck-check」「ui 里写了事件委托」，但证明不了
// **点下去真的生成、勾选真的存住、刷新真的回来**：这些是运行时行为（事件委托 /
// localStorage / 真 HTTP / 真工具链），只有真浏览器能作证。
//
// 前置（一次性）：npm install && npx playwright install chromium
// 运行：node --test tests/browser/hwcheck.spec.mjs
// **不在默认 `node --test "tests/js/*.test.mjs"` 里**——真机验收要起服务 + 开浏览器
// （生成一次还要真跑 UV4），不该让每次改前端都付这个成本；改动本栏目交互时手动跑。
//
// 假件：无。服务夹具（tests/browser/server.mjs）起的是**真后端**（真库真母版），
// 端口 8791——不动用户默认的 8000。检测生成零 LLM，不花额度。
//
// 隔离：生成父目录是本次的临时目录（不写用户桌面），跑完删掉。
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright";
import { startServer } from "./server.mjs";

let server = null;
let browser = null;
let page = null;
let parentDir = "";

const HWCHECK_TAB = 'nav button[data-tab="hwcheck"]';

test.before(async () => {
  parentDir = mkdtempSync(join(tmpdir(), "firstep-hwcheck-"));
  server = await startServer();
  browser = await chromium.launch();
  page = await browser.newPage();
});

test.after(async () => {
  if (browser) await browser.close();
  if (server) await server.stop();
  try { rmSync(parentDir, { recursive: true, force: true }); } catch { /* 临时目录 */ }
});

// openTab()：打开页面并切到硬件检测栏目（首帧 / 刷新后都用它）。
// 先等**启动完成的信号**（平台卡渲染出来 = index.html 的 init() 跑过，导航分发
// 的监听也已就位）再点页签：不等它直接点会偶发"点了没反应"（本单复跑真机两次，
// 第二次就撞上 section 一直 hidden——不是产品缺陷，是用例抢跑）。
async function openTab() {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  // 注意 state:"attached"——这个容器此时还在**未选中的页签**里（不可见），
  // 等 visible 会一直等到超时；这里要的只是"服务端状态已到达并渲染过"
  await page.waitForSelector("#hwcheck-platforms .platform-card",
    { state: "attached", timeout: 30000 });
  await page.click(HWCHECK_TAB);
  await page.waitForSelector("#tab-hwcheck", { state: "visible" });
}

// setParent(dir)：填输出父目录并触发 change（栏目据此重载最近列表）。
// 不用「选择文件夹」——那会弹服务端原生对话框，自动化点不了。
async function setParent(dir) {
  await page.fill("#hwcheck-parent", dir);
  await page.dispatchEvent("#hwcheck-parent", "change");
}

test("栏目可点开：平台卡可选、预览出真 main.c（零 LLM 渲染）", async () => {
  await openTab();
  await page.waitForSelector("#hwcheck-platforms .platform-card");
  await page.click("#btn-hwcheck-preview");
  await page.waitForSelector("[data-hwcheck-code]");
  const code = await page.textContent("[data-hwcheck-code]");
  assert.ok(code.includes("int main(void)"), "预览应给出 main.c 文本");
  assert.ok(code.includes("hwcheck_report"), "应有自检结果出口");
  assert.ok(code.includes("板子活着"), "应有一句「板子活着」的上电自报");
});

test("生成检测工程：新子目录 + 工程面板 + 上板清单 + 最近列表都出现", async () => {
  await setParent(parentDir);
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });

  const pathText = await page.textContent(".hwcheck-path");
  assert.ok(pathText.includes(parentDir), "工程应生成在指定父目录下：" + pathText);
  assert.match(pathText, /hwcheck-stm32-\d{8}-\d{6}/, "目录名形态固定");
  // 真落盘（不是只画了块面板）
  const onDisk = readdirSync(parentDir);
  assert.equal(onDisk.length, 1, "父目录里应恰好一个新工程目录");
  assert.match(onDisk[0], /^hwcheck-stm32-\d{8}-\d{6}$/);

  const rows = await page.locator("#hwcheck-checklist .hwcheck-check").count();
  assert.ok(rows >= 3 && rows <= 6, "清单 3-6 条，实际 " + rows);
  const expectText = await page.textContent("#hwcheck-checklist .hwcheck-check-expect");
  const tipText = await page.textContent("#hwcheck-checklist .hwcheck-check-tip");
  assert.ok(expectText.includes("应看到："), "每条要讲清应看到什么");
  assert.ok(tipText.includes("不对先查："), "每条要讲清不对先查哪里");

  await page.waitForSelector("#hwcheck-recent .hwcheck-recent-row");
  const recent = await page.textContent("#hwcheck-recent");
  assert.ok(recent.includes(onDisk[0]), "最近几次检测应列出刚生成的这一个");
});

test("勾选态本地备忘 + 刷新回显（清单是给人照着比的，不回显就等于没有）", async () => {
  const first = page.locator("#hwcheck-checklist .hwcheck-check").first();
  await first.click();
  await page.waitForSelector("#hwcheck-checklist .hwcheck-check.done");
  let progress = await page.textContent("#hwcheck-checklist .hwcheck-hint");
  assert.ok(/已确认 1 \/ \d+ 条/.test(progress), "进度应显示已确认 1 条：" + progress);

  await openTab();   // 刷新 + 重进栏目
  await page.waitForSelector("#hwcheck-project .hwcheck-path", { timeout: 30000 });
  const restored = await page.textContent(".hwcheck-path");
  const onDisk = readdirSync(parentDir)[0];
  assert.ok(restored.includes(onDisk), "刷新后应回到上次看的那个检测工程");
  const checked = await page.locator("#hwcheck-checklist .hwcheck-check.done").count();
  assert.equal(checked, 1, "刷新后勾选态应回显");

  await page.locator("#hwcheck-checklist .hwcheck-check").first().click();
  await page.waitForFunction(
    () => document.querySelectorAll("#hwcheck-checklist .hwcheck-check.done").length === 0);
});

test("编译复用既有面板与判读：真 UV4 编译绿（工具链缺失时本用例如实红）", async () => {
  await page.click("[data-hwcheck-compile]");
  await page.waitForSelector("#hwcheck-compile-status.ok", { timeout: 180000 });
  const status = await page.textContent("#hwcheck-compile-status");
  assert.ok(status.includes("编译成功"), "状态行应报编译成功：" + status);
  assert.ok(/0 Error/.test(status), "应是 0 Error：" + status);
});

// ---------------------------------------------------------------------------
// 工单 03：器件选择 → 接线表 / 默认脚冲突 / 建议顺序（真浏览器 + 真后端）
//
// 为什么这一层必须有：接线表/冲突/顺序全是"点了器件之后页面上到底显示什么"，
// 纯函数用例只能证明 fx 渲染得出那段 HTML，证明不了**选器件真的触发了服务端
// 投影、真的把结果画到那三个容器里**。
// ---------------------------------------------------------------------------

// pickDevice(slug)：在器件池里搜出来点一下（器件卡与模块库页同一套卡片渲染）。
async function pickDevice(slug) {
  await page.fill("#hwcheck-device-search", slug);
  await page.waitForSelector(`#hwcheck-device-grid [data-add="${slug}"]`);
  await page.click(`#hwcheck-device-grid [data-add="${slug}"]`);
}

test("选上 MPU6050：接线表带默认脚与板上共享注记、顺序把它排在最后、冲突预警标 ⚠", async () => {
  await openTab();
  await page.click('[data-hwcheck-platform="mspm0"]');
  await pickDevice("ml_mpu6050");

  // chips = 已选（复用推荐区 chip：data-remove 是"从工程里去掉"）
  await page.waitForSelector('#hwcheck-device-chips [data-remove="ml_mpu6050"]');

  // 接线表：MPU6050 的默认脚 PA1/PA0 + 板载 LED 共用（这条暗雷必须在页面上）
  await page.waitForSelector("#hwcheck-wiring .hwcheck-table");
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-wiring").textContent.includes("ml_mpu6050"));
  const wiring = await page.textContent("#hwcheck-wiring");
  assert.ok(wiring.includes("I2C_0_SCL") && wiring.includes("PA1"),
    "接线表应给出 MPU6050 的 SCL 默认脚：\n" + wiring);
  assert.ok(wiring.includes("I2C_0_SDA") && wiring.includes("PA0"), "SDA 同理");
  assert.ok(wiring.includes("板载共享") && wiring.includes("板载 LED 共用"),
    "板载 LED 同脚这条暗雷要如实呈现：\n" + wiring);

  // 默认脚冲突：mspm0 默认双通道撞 PA22（工单 02 的生成 400 在页面上提前可见）
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-conflicts").textContent.includes("PA22"));
  const conflicts = await page.textContent("#hwcheck-conflicts");
  assert.ok(conflicts.includes("引脚冲突") && conflicts.includes("PA22"),
    "冲突预警应点名撞在一起的脚：\n" + conflicts);
  // 板上自带的共享（板载 LED 与 I2C0 同脚）：同脚组看不见它，必须单独列出来
  // ——否则冲突区那句"没有抢同一个引脚"就是假安心（工单 03 评审整改）
  assert.ok(conflicts.includes("板上共享") && conflicts.includes("板载 LED 共用"),
    "板载 LED 同脚要单独成条：\n" + conflicts);

  // 建议顺序：bring-up 先做，器件排最后
  const order = await page.textContent("#hwcheck-order");
  assert.ok(order.includes("先做·板子活着"), "应标出先做的那几件：\n" + order);
  assert.ok(order.includes("为什么是这个次序"), "应说明为什么按这个次序");
  const slugs = await page.locator("#hwcheck-order .hwcheck-order-row .slug").allTextContents();
  assert.equal(slugs[slugs.length - 1], "ml_mpu6050",
    "器件应排在 bring-up 模块之后，实际：" + slugs.join(" → "));

  // 去掉器件 → 表里不再有它（选择是活的，不是一次性快照）
  await page.click('#hwcheck-device-chips [data-remove="ml_mpu6050"]');
  await page.waitForFunction(
    () => !document.querySelector('#hwcheck-device-chips [data-remove="ml_mpu6050"]'));
  await page.waitForFunction(
    () => !document.querySelector("#hwcheck-wiring").textContent.includes("ml_mpu6050"));
});

test("本平台没有条目的器件：点名「无法检测」，不静默省略", async () => {
  await openTab();
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.fill("#hwcheck-device-search", "sr04");
  await page.waitForSelector('#hwcheck-device-grid [data-add="sr04"]');
  await page.click('#hwcheck-device-grid [data-add="sr04"]');
  await page.waitForSelector("#hwcheck-device-missing .hwcheck-warn");
  const missing = await page.textContent("#hwcheck-device-missing");
  assert.ok(missing.includes("sr04") && missing.includes("无本平台版本")
    && missing.includes("无法检测"), "缺条目要点名：\n" + missing);
  // 去掉它，别把这份状态留给后面的用例
  await page.click('#hwcheck-device-chips [data-remove="sr04"]');
  await page.fill("#hwcheck-device-search", "");
});

test("专精小节：选上 led 就在检测计划里出 [专精] 小节（未专精件不在这里）", async () => {
  await openTab();
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.fill("#hwcheck-device-search", "led");
  await page.waitForSelector('#hwcheck-device-grid [data-add="led"]');
  await page.click('#hwcheck-device-grid [data-add="led"]');
  await page.waitForSelector("#hwcheck-sections .hwcheck-section");
  const plan = await page.textContent("#hwcheck-sections");
  assert.ok(plan.includes("[专精]") && plan.includes("led"),
    "专精件要带 [专精] 标记：\n" + plan);
  assert.ok(plan.includes("初始化（不判返回值）"),
    "这一节测什么要说清（led_init 是 void → 如实说不判返回值）：\n" + plan);
  assert.ok(plan.includes("只看现象"),
    "没有读取型探头的件必须标「只看现象」，不许看起来像测过了：\n" + plan);
  assert.ok(plan.includes("三色通道") || plan.includes("PC13"),
    "平台差异说明直接印在检测页上：\n" + plan);

  // 未专精件：有平台条目但这一版还没配方 → 单独点名（**不进专精小节清单**）
  // ⚠ 样本是 `beep`，不能再用 ml_mpu6050：工单 05 起它已经专精了（本文件下面
  // 有它自己的用例），拿它当"未专精"的样本会变成一条假红。
  await page.fill("#hwcheck-device-search", "beep");
  await page.waitForSelector('#hwcheck-device-grid [data-add="beep"]');
  await page.click('#hwcheck-device-grid [data-add="beep"]');
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-sections").textContent
      .includes("不会给它出检测小节"));
  const withUnspecialized = await page.textContent("#hwcheck-sections");
  assert.ok(withUnspecialized.includes("beep"),
    "没配方的件要点名：\n" + withUnspecialized);
  const sectionCount = await page.locator("#hwcheck-sections .hwcheck-section").count();
  assert.equal(sectionCount, 1, "未专精件不产生专精小节（只点名）");

  // 去掉器件 → 计划跟着变（选择是活的，不是一次性快照）。
  // 用 dispatchEvent 而不是 click()：chip 容器在每次选择变化后被整体重绘
  // （`box.innerHTML = …`），Playwright 的 click 会等"元素稳定"而重绘恰好
  // 让它永远不稳定（本用例实测卡满 30s 超时）——事件委托挂在容器上，
  // 派发事件同样走真实的产品路径。
  await page.dispatchEvent('#hwcheck-device-chips [data-remove="led"]', "click");
  await page.waitForFunction(
    () => !document.querySelector("#hwcheck-sections").textContent.includes("[专精] led"));
  await page.dispatchEvent('#hwcheck-device-chips [data-remove="beep"]', "click");
  await page.fill("#hwcheck-device-search", "");
});

test("MPU6050 专精小节：板上判定 + 平台差异如实印在页面上（stm32 只有原始六轴）", async () => {
  await openTab();
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.fill("#hwcheck-device-search", "mpu6050");
  await page.waitForSelector('#hwcheck-device-grid [data-add="ml_mpu6050"]');
  await page.click('#hwcheck-device-grid [data-add="ml_mpu6050"]');
  await page.waitForSelector("#hwcheck-sections .hwcheck-section");

  const plan = await page.textContent("#hwcheck-sections");
  assert.ok(plan.includes("[专精]") && plan.includes("ml_mpu6050"),
    "这一件要出专精小节：\n" + plan);
  assert.ok(plan.includes("通信探头带判定") && plan.includes("0x68"),
    "板上判定那一档要说清探头与期望值：\n" + plan);
  assert.ok(plan.includes("6 项读数回显"),
    "stm32 侧是原始六轴（6 项）——不是角度：\n" + plan);
  assert.ok(plan.includes("没有姿态解算") && plan.includes("原始六轴"),
    "平台差异（本平台不给角度）必须直接印在页面上，\n"
    + "否则学生会把「显示不了角度」误判成「我接错了」：\n" + plan);
  assert.ok(plan.includes("I2C_Init"),
    "前置调用（先起软 I2C 总线）也要看得见：\n" + plan);

  // 产出的 main.c 里同样有这一节（页面与产物同一个判据来源）
  await page.click("#btn-hwcheck-preview");
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-output").textContent
      .includes("hwcheck_check_ml_mpu6050();"));
  const mainC = await page.textContent("#hwcheck-output");
  assert.ok(mainC.includes("r = MPU6050_Read(WHO_AM_I);"),
    "探头（读身份寄存器比对期望值）要落进产物：\n" + mainC.slice(0, 2000));
  assert.ok(mainC.includes('hwcheck_report_int(ax);'), "原始六轴走整数回显");
  await page.dispatchEvent('#hwcheck-device-chips [data-remove="ml_mpu6050"]', "click");
  await page.fill("#hwcheck-device-search", "");
});

test("同组互斥 = 单选交换：mspm0 上点第二件姿态件会自动换掉第一件并说明", async () => {
  await openTab();
  await page.click('[data-hwcheck-platform="mspm0"]');
  await page.fill("#hwcheck-device-search", "mpu6050");
  await page.waitForSelector('#hwcheck-device-grid [data-add="ml_mpu6050"]');
  await page.click('#hwcheck-device-grid [data-add="ml_mpu6050"]');
  await page.waitForSelector('#hwcheck-device-chips [data-remove="ml_mpu6050"]');

  // 提示：这一组只能选一件 + 再点谁会自动换掉谁
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-device-groups").textContent
      .includes("同组互斥"));
  const notice = await page.textContent("#hwcheck-device-groups");
  assert.ok(notice.includes("航向保持"), "要说清是哪一组：\n" + notice);
  assert.ok(notice.includes("会自动换掉 ml_mpu6050"),
    "点之前就告诉用户会发生什么：\n" + notice);

  // 点同组的第二件：第一件被换掉（不是两件都在）
  await page.fill("#hwcheck-device-search", "jy61p");
  await page.waitForSelector('#hwcheck-device-grid [data-add="jy61p"]');
  await page.click('#hwcheck-device-grid [data-add="jy61p"]');
  await page.waitForSelector('#hwcheck-device-chips [data-remove="jy61p"]');
  const chips = await page.textContent("#hwcheck-device-chips");
  assert.ok(chips.includes("jy61p"), "刚点的那件要在：\n" + chips);
  assert.ok(!chips.includes("ml_mpu6050"),
    "同组旧成员要被单选交换掉（这一组只能选一件）：\n" + chips);
  const after = await page.textContent("#hwcheck-device-groups");
  assert.ok(!after.includes("请去掉一件"),
    "交换之后不该还是冲突态：\n" + after);
  await page.dispatchEvent('#hwcheck-device-chips [data-remove="jy61p"]', "click");
  await page.fill("#hwcheck-device-search", "");
});

test("串口命令台：选上 led 就列出复测命令；不勾串口则明说不能交互复测", async () => {
  await openTab();
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.fill("#hwcheck-device-search", "led");
  await page.waitForSelector('#hwcheck-device-grid [data-add="led"]');
  await page.click('#hwcheck-device-grid [data-add="led"]');
  await page.waitForSelector("#hwcheck-console .hwcheck-table");

  const panel = await page.textContent("#hwcheck-console");
  assert.ok(panel.includes("l") && panel.includes("led"),
    "命令表要说清敲哪个字符复测哪一件：\n" + panel);
  assert.ok(panel.includes("板载 LED：重跑一次点灯初始化"),
    "配方给的那句说明要原样印出来（页面与板上回显同一句）：\n" + panel);
  for (const command of ["r", "y", "g", "o", "b"]) {
    assert.ok(panel.includes(command), "既有命令 " + command + " 也要列（语义没变）：\n" + panel);
  }
  assert.ok(panel.includes("能交互式复测"), "有串口就要说清能复测：\n" + panel);

  // 产出的 main.c 与页面同源：命令台进产物，且排在库内 poll 之前。
  await page.click("#btn-hwcheck-preview");
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-output").textContent
      .includes("hwcheck_console_poll();"));
  const mainC = await page.textContent("#hwcheck-output");
  assert.ok(mainC.includes("debug_cmd_peek()") && mainC.includes("debug_cmd_consume()"),
    "命令台要经库侧 peek / consume 认领命令：\n" + mainC.slice(0, 2000));
  assert.ok(mainC.indexOf("hwcheck_console_poll();") < mainC.indexOf("debug_cmd_poll();"),
    "必须先我们的命令台再库内 poll（反了既有命令会先把缓冲清空）：\n"
    + mainC.slice(0, 2000));
  assert.ok(mainC.includes("/* 既有命令：原样留给库内 debug_cmd_poll()"),
    "既有 r/y/g/o/b 那一支要原样留给库里：\n" + mainC.slice(0, 2000));

  // 取消勾选「调试串口」→ 页面**明说**不能交互式复测（票面：不静默降级）
  await page.uncheck('input[data-hwcheck-channel="debug_uart"]');
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-console").textContent
      .includes("不能交互式复测"));
  const noSerial = await page.textContent("#hwcheck-console");
  assert.ok(noSerial.includes("勾上"), "还要给出下一步（怎么才能复测）：\n" + noSerial);
  assert.ok(!noSerial.includes("敲这个"), "不能用的一趟不摆命令表：\n" + noSerial);

  await page.check('input[data-hwcheck-channel="debug_uart"]');
  await page.waitForSelector("#hwcheck-console .hwcheck-table");
  await page.dispatchEvent('#hwcheck-device-chips [data-remove="led"]', "click");
  await page.fill("#hwcheck-device-search", "");
});

