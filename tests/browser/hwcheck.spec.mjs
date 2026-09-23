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
// 端口由夹具自己向内核要一个空闲端口（工单 ui-dom-contract-gate/01 起不再固定 8791）
// ——不动用户默认的 8000。检测生成零 LLM，不花额度。
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
// 「我的器件」这一组用例的 id：**带时间戳保唯一**——数据目录在真机上（
// `~/.contest_generator/hwcheck_devices/`），固定 id 会与用户自己建的那件撞名。
// 每条用完即删（`myDeviceCleanup`），跑完不在用户数据目录里留东西。
const MY_DEVICE_ID = `mine_probe${Date.now().toString().slice(-6)}`;

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

// clearDevices()：把器件集清空（**用例级隔离**，工单 ui-dom-contract-gate/01）。
//
// 为什么必须有：这些用例**共用一张页面**（`test.before` 开一次），前一条中途失败
// （超时 / 断言红）会把它的器件留在选择集里，后一条就从"脏状态"开始——本机实测：
// 「选上 MPU6050」超时后 ml_mpu6050 留下，紧接着「选上 led」变成两件同选 → 撞脚被
// 如实拦下 → 面板不渲染 → 也 30s 超时。一条真红滚成两条，读的人会以为坏了两个地方。
//
// 用 `dispatchEvent` 而不是 `click()`：chip 容器每次选择变化后被整体重绘
// （`box.innerHTML = …`），Playwright 的 click 会等"元素稳定"而重绘恰好让它永远
// 不稳定（本文件下面那条用例的注释记着这个坑，实测卡满 30s）；事件委托挂在容器上，
// 派发事件同样走真实的产品路径。
async function clearDevices() {
  const removed = await page.evaluate(() => {
    const chips = [...document.querySelectorAll("#hwcheck-device-chips [data-remove]")];
    for (const chip of chips) {
      chip.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    }
    return chips.map((c) => c.getAttribute("data-remove"));
  });
  if (!removed.length) return;
  await page.waitForFunction(
    () => document.querySelectorAll("#hwcheck-device-chips [data-remove]").length === 0,
    undefined, { timeout: 10000 });
}

// 每条用例**收尾兜底**清一次（红了也清——`afterEach` 在用例失败后照样跑）。
// 正常路径由用例自己清（"选择是活的"那些断言本来就要真点掉），这里只防**中途失败**：
// 带着上一件的器件集进下一条，会把「撞脚被如实拦下」误读成"坏了两个地方"
// （本机实测：「选上 MPU6050」超时后 ml_mpu6050 留下 → 紧接着「选上 led」也超时）。
//
// 机制说清楚（评审整改：原来那句"由清空 → 落盘保证"是错的）：`clearDevices` 点的是
// 真的移除路径，选择集会随产品自己的防抖**异步落盘**；真正让下一条从干净集开始的，
// 是**下一条 `openTab()` 的整页重载 + 服务端回读**——它读到的是落盘后的结果。
// 所以这里不清 localStorage / 不等落盘，只要"点掉"这一步真的发出去了。
test.afterEach(async () => {
  if (!page || page.isClosed()) return;
  try { await clearDevices(); } catch (e) { /* 清不干净不该掩盖真正的红：如实打一行 */
    console.log(`[afterEach] 器件集未清干净：${e.message}`);
  }
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

// myDeviceType(selector, value)：像真人一样填一个字段——聚焦 → 输值 → **失焦**。
//
// 为什么不能只用 `page.fill()`：产品在**失焦**时按名称补 id 建议（真人的操作顺序
// 就是"打完名字点下一个框"）。Playwright 的 `fill` 只发 input / change、**不发
// blur**，于是"补建议"这条路根本没被走到——那样验的就不是用户会遇到的路径了。
async function myDeviceType(selector, value) {
  await page.focus(selector);
  await page.fill(selector, value);
  await page.dispatchEvent(selector, "blur");
}

// myDeviceFill(fields)：展开「+ 我的器件」表单并逐字段填值（真点真填）。
//
// ⚠ 先**取消**可能已经开着的表单（用例级隔离）：这些用例共用一张页面，前一条中途
// 失败会把它的表单留在页面上；不先收掉，本条的 `#btn-my-device-new` 就是"点了没
// 反应"（表单已经开着，只是装着上一条的内容）——实测会滚成 30s 超时。
//
// `blur` 触发的"按名称建议 id"在填完 name 之后可能改写 id，所以 id 最后填
// （照真人顺序：先写名字再定 id，或者直接填 id 压过建议）。
async function myDeviceFill(fields) {
  if (await page.$("[data-my-device-cancel]")) {
    await page.click("[data-my-device-cancel]");
    await page.waitForSelector("[data-my-device-form]", { state: "detached" });
  }
  await page.click("#btn-my-device-new");
  await page.waitForSelector("[data-my-device-form]");
  for (const [key, value] of Object.entries(fields)) {
    if (key === "id") continue;
    const selector = `[data-my-device-field="${key}"]`;
    // 总线是 <select>（fill 只认输入类元素），其余是 <input>
    if (key === "bus") {
      await page.selectOption(selector, value);
      await page.dispatchEvent(selector, "blur");
    } else {
      await myDeviceType(selector, value);
    }
  }
  if (fields.id) await myDeviceType('[data-my-device-field="id"]', fields.id);
}

// myDeviceCleanup(ids)：直接走产品端点删掉本次用例建的件（idempotent——没有就跳过）。
// 为什么收尾用 API 而不是点页面：用例中途失败时页面可能已经不在那一块上，
// 而"别在用户数据目录里留垃圾"这件事不该依赖页面状态。
async function myDeviceCleanup(ids) {
  for (const id of ids) {
    try {
      await fetch(`${server.url}/api/my-devices/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
    } catch { /* 收尾失败不该掩盖真正的红 */ }
  }
}

test("「我的器件」：能建（地址双向显示）、能存住（刷新还在）、能改、能删", async () => {
  await openTab();
  await myDeviceFill({
    name: "验收用的库外件", bus: "i2c", address: "0x68",
    register: "0x75", expect: "0x68", notes: "买卖家页抄的",
    id: MY_DEVICE_ID,
  });
  // 地址双向显示：7 位值 + 派生的 8 位读 / 写形式（0x68 → 读 0xD1 / 写 0xD0）
  const preview = await page.textContent("[data-my-device-address-preview]");
  for (const token of ["0x68", "0xD0", "0xD1"]) {
    assert.ok(preview.includes(token), `地址预览应给出 ${token}：${preview}`);
  }
  const snapshot = await page.evaluate((id) => ({
    error: document.querySelector("[data-my-device-form-error]").textContent,
    disabled: document.querySelector("[data-my-device-save]").disabled,
    values: [...document.querySelectorAll("[data-my-device-field]")]
      .map((el) => `${el.dataset.myDeviceField}=${el.value}`),
    rows: [...document.querySelectorAll("[data-my-device-row]")]
      .map((el) => el.dataset.myDeviceRow),
    want: id,
  }), MY_DEVICE_ID);
  assert.deepEqual(snapshot.values, [
    "id=" + MY_DEVICE_ID, "name=验收用的库外件", "bus=i2c", "address=0x68",
    "register=0x75", "expect=0x68", "notes=买卖家页抄的",
  ], "表单现场： " + JSON.stringify(snapshot));
  assert.equal(snapshot.disabled, false, "保存前：按钮该是可点的 —— " + JSON.stringify(snapshot));
  assert.equal(snapshot.error, "", "保存前不该有校验理由 —— " + JSON.stringify(snapshot));
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);
  const row = await page.textContent(`[data-my-device-row="${MY_DEVICE_ID}"]`);
  assert.ok(row.includes("验收用的库外件"), row);
  assert.ok(row.includes("0x68") && row.includes("0xD0"),
    "列表行也要两种写法都给出来：" + row);

  // 存住了：整页刷新后仍在（服务端真源，不是页面内存）
  await openTab();
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);

  // 能改：点「编辑」改名称 → 保存 → 行里是新名字（按 id 幂等更新，不新建第二份）
  await page.click(`[data-my-device-edit="${MY_DEVICE_ID}"]`);
  await page.waitForSelector("[data-my-device-form]");
  await myDeviceType('[data-my-device-field="name"]', "改过名字的库外件");
  await page.click("[data-my-device-save]");
  await page.waitForFunction(
    (id) => {
      const row = document.querySelector(`[data-my-device-row="${id}"]`);
      return !!row && row.textContent.includes("改过名字的库外件");
    }, MY_DEVICE_ID, { timeout: 10000 });
  const count = await page.evaluate(
    (id) => document.querySelectorAll(`[data-my-device-row="${id}"]`).length, MY_DEVICE_ID);
  assert.equal(count, 1, "按 id 幂等更新：不该建出第二行");

  // 能删：点「删除」→ 行消失（服务端也真删了）
  await page.click(`[data-my-device-del="${MY_DEVICE_ID}"]`);
  await page.waitForFunction(
    (id) => !document.querySelector(`[data-my-device-row="${id}"]`),
    MY_DEVICE_ID, { timeout: 10000 });
  const listed = await page.evaluate(async () => {
    const body = await (await fetch("/api/my-devices")).json();
    return body.devices.map((d) => d.id);
  });
  assert.ok(!listed.includes(MY_DEVICE_ID), "服务端也该没有这件：" + listed.join(","));
});

// 这条判据的**真源在服务端**（`CustomDevice.validated(library_slugs=…)` →
// 400 点名要求改名），服务端那条腿的判据在 `tests/test_my_devices.py` /
// `tests/test_my_devices_endpoint.py`（那里造了一个真叫 `mine_gyro` 的库内模块，
// 撞得成）。这里验的是**页面这一层**做得到的那一件：撞**已有自建件**时当场拦住
// ——这是真库上唯一会发生的撞名，也是学生真正会踩的那一下。
//
// 为什么不在真浏览器里造"库内 slug 撞名"：id 文法强制 `mine_` 前缀，而真库
// 96 个 slug 一个都不以 `mine_` 开头（`test_library_slugs_never_take_the_mine_prefix`
// 钉着这条事实）。要在浏览器里撞成，就得给这个 spec 换一个含 `mine_*` 模块的
// 假库——那会连带把检测页的框架件（led / delay / 通道）一起换掉，验收跑的就
// 不是真库了。判据强度的价值不如"验的是真东西"。
test("「我的器件」：撞已有自建件时页面当场拦住（改名 / 覆盖二选一，不静默存）", async () => {
  await openTab();
  await myDeviceFill({
    name: "第一件", bus: "i2c", address: "0x68", id: MY_DEVICE_ID,
  });
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);

  // 再建一件、填同一个 id：保存按钮当场置灰，并明说"已经有一件叫这个了"
  await myDeviceFill({
    name: "想用同一个 id 的第二件", bus: "i2c", address: "0x69", id: MY_DEVICE_ID,
  });
  assert.ok(await page.isDisabled("[data-my-device-save]"),
    "撞已有自建件时保存按钮该置灰");
  const inline = await page.textContent("[data-my-device-form-error]");
  assert.ok(inline.includes(MY_DEVICE_ID) && inline.includes("已经有一件"), inline);
  // 那条 id 名下还是一行（没有被静默加后缀建出第二件）
  const rows = await page.evaluate(
    (id) => document.querySelectorAll(`[data-my-device-row="${id}"]`).length, MY_DEVICE_ID);
  assert.equal(rows, 1, "不该多出一件");
  await myDeviceCleanup([MY_DEVICE_ID]);
});

test("「我的器件」：库内 slug 集里没有 mine_ 开头的（前缀就是两类东西的分界）", async () => {
  // 这条是**事实**、不是守卫：它说明真库上"id 撞库内 slug"撞不成（id 必须
  // `mine_` 开头）。页面仍然按 `known_slugs` 判一次，是给"哪天真有 `mine_*`
  // 模块入库"留的提前拦截；服务端那条腿（400 点名）与它同一条判据、不是两个真相。
  await openTab();
  const known = await page.evaluate(async () => {
    const body = await (await fetch("/api/my-devices")).json();
    return body.known_slugs;
  });
  assert.ok(known.length > 0, "真库应读得到 slug");
  assert.deepEqual(known.filter((slug) => slug.startsWith("mine_")), []);
});

test("「我的器件」：能选（加进这次检测、与库内器件同一次预览不报错）", async () => {
  // 工单验收第 6 条：「能建、能列、**能选**、能改、能删」。
  // 选中之后它会跟库内器件一起进 devices（页面画 chip、服务端回显），但**这一版
  // 它还不是模块**——预览不许因此 400（接进渲染是工单 03 的事）。
  await openTab();
  await myDeviceFill({
    name: "要选上的库外件", bus: "i2c", address: "0x68", id: MY_DEVICE_ID,
  });
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);

  // 加选：行上的按钮 → 出现在已选 chips 里（与库内器件同一套 chip）
  await page.click(`[data-my-device-pick="${MY_DEVICE_ID}"]`);
  await page.waitForSelector(`#hwcheck-device-chips [data-remove="${MY_DEVICE_ID}"]`);

  // 选了它之后预览照常出 main.c（不是 400），且服务端把选择回显回来
  await page.click("#btn-hwcheck-preview");
  await page.waitForSelector("[data-hwcheck-code]");
  const code = await page.textContent("[data-hwcheck-code]");
  assert.ok(code.includes("int main(void)"), code.slice(0, 200));
  const devices = await page.evaluate(() =>
    [...document.querySelectorAll("#hwcheck-device-chips [data-remove]")]
      .map((el) => el.dataset.remove));
  assert.ok(devices.includes(MY_DEVICE_ID), "选中的自建件要在已选里：" + devices.join(","));

  // 取消加选：chip 点掉 → 回到未选中（行上的按钮文案跟着变回「加进这次检测」）
  await page.evaluate((id) => {
    document.querySelector(`#hwcheck-device-chips [data-remove="${id}"]`)
      .dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  }, MY_DEVICE_ID);
  await page.waitForFunction(
    (id) => !document.querySelector(`#hwcheck-device-chips [data-remove="${id}"]`),
    MY_DEVICE_ID, { timeout: 10000 });
  const pick = await page.textContent(`[data-my-device-pick="${MY_DEVICE_ID}"]`);
  assert.ok(pick.includes("加进这次检测"), pick);
  await myDeviceCleanup([MY_DEVICE_ID]);
});

test("「我的器件」：件与平台无关（切平台不丢）+ 非 I2C 如实说这一版不出探测程序", async () => {
  await openTab();
  await myDeviceFill({
    name: "验收用的 SPI 件", bus: "spi", address: "", id: MY_DEVICE_ID,
  });
  // 非 I2C 不摆地址预览（那一类压根没有地址——摆出来等于教用户填一个用不上的
  // 字段），但**如实说**这一版不出探测程序
  assert.equal(await page.$("[data-my-device-address-preview]"), null,
    "非 I2C 不该摆地址预览");
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);
  const row = await page.textContent(`[data-my-device-row="${MY_DEVICE_ID}"]`);
  assert.ok(row.includes("只对 I2C 器件生成探测程序"), row);
  assert.ok(row.includes("不假装测过"), row);

  // 切平台：件**不丢**（件与平台无关——总线脚由平台决定，地址与寄存器是器件的事实）
  const before = await page.getAttribute(
    `[data-my-device-row="${MY_DEVICE_ID}"]`, "data-my-device-row");
  await page.click('[data-hwcheck-platform="mspm0"]');
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);
  const after = await page.getAttribute(
    `[data-my-device-row="${MY_DEVICE_ID}"]`, "data-my-device-row");
  assert.equal(after, before, "切平台后这件还该在列表里");
  await myDeviceCleanup([MY_DEVICE_ID]);
});

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

test("选上 MPU6050：接线表带默认脚与板上共享注记、顺序把它排在最后、默认脚撞脚已被解开", async () => {
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

  // 默认脚冲突：mspm0 默认双通道原撞 PA22（OLED_SPI_RES vs DEBUG_UART_RX）。
  // **工单 hwcheck-pin-conflict-exit/01 之后这里不再是"预警"而是"已经解开"**：
  // 检测页没有引脚配置入口，所以生成前自己跑与赛题页「自动配置」同一个求解器把
  // 默认脚撞脚解开，并把动过的线如实打进载荷（`wiring.pin_fixes`）。
  // 判据因此改成断言**新的正确行为**：冲突区说"没有抢同一个引脚"，接线表里
  // OLED_SPI_RES 已落到 PA2、且写明"原 PA22 与 debug_uart.DEBUG_UART_RX 冲突，已自动移开"。
  // （改动前的旧断言是等 `#hwcheck-conflicts` 里出现 PA22 —— 那条在求解器落地后
  // 永远等不到，本机实测 30s 超时。）
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-conflicts").textContent.includes("没有两件模块抢同一个引脚"));
  const conflicts = await page.textContent("#hwcheck-conflicts");
  assert.ok(conflicts.includes("没有两件模块抢同一个引脚"),
    "默认脚冲突应已在生成前解开，冲突区该如实说没有冲突：\n" + conflicts);
  // 解得开不等于没发生过：移走了哪根、为什么移，必须留在页面上。
  //
  // **判据要钉到那一格**（评审整改）：只查 `wiring.includes("PA2")` 是松的——
  // `"PA24"` 里也含 `"PA2"`，脚被挪到 PA24（或在 PA2 / PA20 / PA24 之间漂）照样绿，
  // 真正兜住判据的只剩 pin_fixes 那段文案。这里按**接线表的 DOM 契约**取：
  // 模块格 `.slug` = oled、角色格 = OLED_SPI_RES 的那一行，它的引脚格必须是 PA2。
  const resRow = page.locator("#hwcheck-wiring table.hwcheck-table tbody tr")
    .filter({ has: page.locator('td .slug:text-is("oled")') })
    .filter({ hasText: "OLED_SPI_RES" });
  assert.equal(await resRow.count(), 1, "接线表里应有 oled · OLED_SPI_RES 那一行：\n" + wiring);
  const resCells = await resRow.locator("td").allInnerTexts();
  assert.equal(resCells[1], "OLED_SPI_RES", "该行第二格应是角色：\n" + resCells.join(" | "));
  assert.equal(resCells[2], "PA2",
    `求解器应把 OLED_SPI_RES 从 PA22 移到 PA2，实际引脚格是「${resCells[2]}」：\n`
    + resCells.join(" | "));
  assert.ok(wiring.includes("已自动移开") && wiring.includes("PA22"),
    "求解器动过的线要如实写在接线表上（原脚 / 为什么）：\n" + wiring);
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

test("自建件在地猛星上的接线：页面给出 PA0 / PA1 与那两句平台代价", async () => {
  // 工单 hwcheck-unknown-device/04 验收第 3 条（**页面面**）：自建件不是模块、
  // 没有 pins 声明，它那一对脚全部来自支点 `i2c_probe`（视图自动补进模块集）——
  // 所以"页面到底显示得出 PA0/PA1 与那两句代价"必须端到端验一次：载荷里有
  // （`tests/test_hwcheck_custom.py` 已钉）不等于**画出来了**（这里是真浏览器）。
  await openTab();
  await page.click('[data-hwcheck-platform="mspm0"]');
  await myDeviceFill({
    name: "自建件接线验收", bus: "i2c", address: "0x68", id: MY_DEVICE_ID,
  });
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);
  await page.click(`[data-my-device-pick="${MY_DEVICE_ID}"]`);
  await page.waitForSelector(`#hwcheck-device-chips [data-remove="${MY_DEVICE_ID}"]`);

  await page.waitForSelector("#hwcheck-wiring .hwcheck-table");
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-wiring").textContent.includes("i2c_probe"));
  const wiring = await page.textContent("#hwcheck-wiring");
  assert.ok(wiring.includes("PA0") && wiring.includes("PA1"),
    "地猛星上这一对脚是 PA0(SDA)/PA1(SCL)，接线表要真给出来：\n" + wiring);
  assert.ok(wiring.includes("板载 LED 共用") && wiring.includes("微闪"),
    "与板载 LED 共用（通信期间微闪）这条暗雷要在页面上：\n" + wiring);
  assert.ok(wiring.includes("上拉位未焊"),
    "PA0 的板载上拉位未焊也要在（学生照表接线时会撞上它）：\n" + wiring);
  // 板上共享单独成条（冲突区那句"没有抢同一个引脚"不能替代它）
  const conflicts = await page.textContent("#hwcheck-conflicts");
  assert.ok(conflicts.includes("板上共享") && conflicts.includes("板载 LED 共用"),
    "板上共享要单独成条：\n" + conflicts);

  await myDeviceCleanup([MY_DEVICE_ID]);
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
  // 去掉器件：件集由 afterEach 统一清（这里顺手清掉搜索框）
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

  // 未专精件（工单 07）：有平台条目但还没配方 → **出通用降级小节**（外观与专精件
  // 可区分：`.hwcheck-generic` 而不是 `.hwcheck-section`），并如实标「未专精」。
  //
  // ⚠ 样本选择是这个用例最脆的一处（样本一旦被配方覆盖，断言就变成假红）：
  //   · `ml_mpu6050` 从工单 05 起已专精 → 不能再用；
  //   · `beep` 从工单 module-hwcheck/09（扩齐 pilot 配方，10 件 17 格）起也专精了
  //     → 本条用例在 HEAD 上就是被它拖红的（本机实测 30s 超时，工单
  //     ui-dom-contract-gate/01 定位并换样本）；
  //   · 现在用 `photoresistance`（stm32 有条目、库内无配方，实测专精小节 0 / 通用小节 1）。
  // 换样本的判据只有一条：**该器件在该平台没有 `hwcheck_recipes.json` 配方**。
  const NO_RECIPE_DEVICE = "photoresistance";
  await page.fill("#hwcheck-device-search", NO_RECIPE_DEVICE);
  await page.waitForSelector(`#hwcheck-device-grid [data-add="${NO_RECIPE_DEVICE}"]`);
  await page.click(`#hwcheck-device-grid [data-add="${NO_RECIPE_DEVICE}"]`);
  await page.waitForSelector("#hwcheck-sections .hwcheck-generic");
  const withUnspecialized = await page.textContent("#hwcheck-sections");
  assert.ok(withUnspecialized.includes(NO_RECIPE_DEVICE),
    "没配方的件要点名：\n" + withUnspecialized);
  assert.ok(withUnspecialized.includes("未专精：只验总线和初始化"),
    "要点名「未专精」这句官方标注（与产物注释同一句）：\n" + withUnspecialized);
  assert.ok(withUnspecialized.includes(`${NO_RECIPE_DEVICE}_init()`),
    "要说清这一趟真做什么（无参初始化），不是一句走过场话术：\n" + withUnspecialized);
  assert.ok(withUnspecialized.includes("不算通过"),
    "通用件没有板上判定，必须明说「不算通过」：\n" + withUnspecialized);
  const sectionCount = await page.locator("#hwcheck-sections .hwcheck-section").count();
  assert.equal(sectionCount, 1, "未专精件不进专精小节清单（只出通用小节）");
  const genericCount = await page.locator("#hwcheck-sections .hwcheck-generic").count();
  assert.equal(genericCount, 1, "未专精件出且只出一条通用小节");

  // 去掉器件 → 计划跟着变（选择是活的，不是一次性快照）。
  // 用 dispatchEvent 而不是 click()：chip 容器在每次选择变化后被整体重绘
  // （`box.innerHTML = …`），Playwright 的 click 会等"元素稳定"而重绘恰好
  // 让它永远不稳定（本用例实测卡满 30s 超时）——事件委托挂在容器上，
  // 派发事件同样走真实的产品路径。
  await page.dispatchEvent('#hwcheck-device-chips [data-remove="led"]', "click");
  await page.waitForFunction(
    () => !document.querySelector("#hwcheck-sections").textContent.includes("[专精] led"));
  await page.dispatchEvent(`#hwcheck-device-chips [data-remove="${NO_RECIPE_DEVICE}"]`, "click");
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

// ---------------------------------------------------------------------------
// 工单 hwcheck-unknown-device/05：自建件的**检测计划**（接线行 / 计划面板 /
// 顺序 / 上板清单）在真页面上的样子
//
// 为什么必须真浏览器：载荷里有 `custom` 不等于画出来了（工单 04 的同一条教训）。
// 这一条把三块都点出来：接线区那一行（名称 + 地址 + 支点那对脚）、计划面板
// （标注词 + 这一趟做什么）、上板清单（三类），以及非 I2C 那件的如实说明。
//
// ⚠ **刻意排在文件最后**：这一条会**生成一个新工程**（清单要生成后才出现在页面上），
// 而本 spec 后面的用例靠"上一次生成的目录"回读（`HWCHECK_LAST_DIR_KEY`）。
// 排在中间会让它们读到这一条生成的工程。
// ---------------------------------------------------------------------------
test("自建件的检测计划：接线那一行 / 计划面板 / 顺序 / 上板清单三类", async () => {
  const SPI_ID = `${MY_DEVICE_ID}spi`;
  await openTab();
  await page.click('[data-hwcheck-platform="stm32"]');
  await myDeviceFill({
    name: "验收用的六轴", bus: "i2c", address: "0x68",
    register: "0x75", expect: "0x68", id: MY_DEVICE_ID,
  });
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);
  await page.click(`[data-my-device-pick="${MY_DEVICE_ID}"]`);
  await page.waitForSelector(`#hwcheck-device-chips [data-remove="${MY_DEVICE_ID}"]`);

  // ① 接线区出现自建件那一行：名称 + 地址 + **支点声明的那对脚**（stm32 = PA6/PA7）
  await page.waitForSelector(`#hwcheck-wiring [data-custom-wiring="${MY_DEVICE_ID}"]`);
  const wiring = await page.textContent(`[data-custom-wiring="${MY_DEVICE_ID}"]`);
  assert.ok(wiring.includes("验收用的六轴") && wiring.includes("0x68"),
    "接线那一行要给出名称与地址：\n" + wiring);
  assert.ok(wiring.includes("i2c_probe") && wiring.includes("PA6") && wiring.includes("PA7"),
    "它那一对脚来自支点 i2c_probe（学生照这一行插线）：\n" + wiring);
  const afterTable = await page.evaluate((id) => {
    const box = document.querySelector("#hwcheck-wiring");
    const table = box.querySelector("table.hwcheck-table");
    const row = box.querySelector(`[data-custom-wiring="${id}"]`);
    return !!table && !!row
      && (table.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  }, MY_DEVICE_ID);
  assert.ok(afterTable, "那一行要接在接线表**之后**（它说的是「上面接线表里那两行」）");

  // ② 计划面板：标注词 + 这一趟做什么；**不许出现 [专精]**
  const plan = await page.textContent(`[data-custom-plan="${MY_DEVICE_ID}"]`);
  assert.ok(plan.includes("自建件：按你确认的事实探测"), "标注词要原样印出来：\n" + plan);
  assert.ok(plan.includes("板上判 OK / FAIL"), "三档文案来自服务端单源：\n" + plan);
  assert.ok(plan.includes("0x68") && plan.includes("0x75"), "地址 / 寄存器要看得见：\n" + plan);
  assert.ok(!plan.includes("[专精]"), "自建件不冒充库内验证过的结论：\n" + plan);
  assert.ok(plan.includes("板上判定"), "有探测小节要说清这一趟真判：\n" + plan);

  // ③ 顺序表：自建件**排最后**，带标注词与名称（库内那几件一个不动）
  await page.waitForSelector("#hwcheck-order .hwcheck-order-row");
  const lastRow = await page.evaluate(() => {
    const rows = [...document.querySelectorAll("#hwcheck-order .hwcheck-order-row")];
    return rows.length ? rows[rows.length - 1].textContent : "";
  });
  assert.ok(lastRow.includes(MY_DEVICE_ID) && lastRow.includes("验收用的六轴"),
    "自建件排在最后（库里验证过的在前）：\n" + lastRow);
  assert.ok(lastRow.includes("自建件：按你确认的事实探测"), lastRow);

  // ④ 上板清单：**三类各一条**（有应答 / 期望值不符 / 无应答）——清单要生成后才在页面上
  await setParent(parentDir);
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });
  await page.waitForSelector("#hwcheck-checklist .hwcheck-check");
  const checklist = await page.textContent("#hwcheck-checklist");
  assert.ok(checklist.includes("应答：有"), "「有应答」那一条：\n" + checklist);
  assert.ok(checklist.includes("期望值 0x68") && checklist.includes("与期望值一致"),
    "「期望值不符」那一条：\n" + checklist);
  assert.ok(checklist.includes("地址上没有应答"),
    "「无应答」那一条（连排查话术一起给）：\n" + checklist);
  const tagged = await page.locator(
    `#hwcheck-checklist [data-hwcheck-check^="custom-${MY_DEVICE_ID}"]`).count();
  assert.equal(tagged, 3, "自建件那三条要在清单里，实际 " + tagged + " 条：\n" + checklist);

  // ⑤ 非 I2C 那件：计划面板如实说"这一趟没有它的探测小节"，产物里一个字都没有
  await myDeviceFill({
    name: "验收用的 SPI 屏", bus: "spi", address: "", id: SPI_ID,
  });
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${SPI_ID}"]`);
  await page.click(`[data-my-device-pick="${SPI_ID}"]`);
  await page.waitForSelector(`#hwcheck-device-chips [data-remove="${SPI_ID}"]`);
  await page.waitForSelector(`[data-custom-plan="${SPI_ID}"]`);
  const spiPlan = await page.textContent(`[data-custom-plan="${SPI_ID}"]`);
  assert.ok(spiPlan.includes("没有探测小节") || spiPlan.includes("不假装测过"),
    "非 I2C 那件要如实说这一版不给它生成探测程序：\n" + spiPlan);
  assert.ok(spiPlan.includes("这一趟没有它的探测小节"), spiPlan);
  assert.equal(await page.$(`[data-custom-wiring="${SPI_ID}"]`), null,
    "它没有线可接：接线区不许编一行出来");
  await page.click("#btn-hwcheck-preview");
  await page.waitForSelector("[data-hwcheck-code]");
  const code = await page.textContent("[data-hwcheck-code]");
  assert.ok(!code.includes(SPI_ID), "非 I2C 件不许进产物（不假装测过）：\n" + code.slice(0, 600));

  await myDeviceCleanup([MY_DEVICE_ID, SPI_ID]);
});

