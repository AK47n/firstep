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

// 末几次 `/api/hwcheck/preview` 的**状态码 + 响应体**（工单 ci-gate-fixes/08 的诊断用）：
// `previewDiag()` 拿它回答"服务端到底答了什么"——CI 上那两条红卡在"等预览载荷渲染出来的
// 东西"，而 playwright 超时里看不出是 400 了、还是 200 但载荷里没这一条。只在诊断里读，
// 不参与任何判据（判据仍是页面上看得见的行为）。
const previewResponses = [];

test.before(async () => {
  parentDir = mkdtempSync(join(tmpdir(), "firstep-hwcheck-"));
  server = await startServer();
  browser = await chromium.launch();
  page = await browser.newPage();
  page.on("response", (resp) => {
    if (!resp.url().includes("/api/hwcheck/preview")) return;
    resp.text().then((body) => {
      previewResponses.push({ status: resp.status(), body: body.replace(/\s+/g, " ").slice(0, 500) });
      if (previewResponses.length > 3) previewResponses.shift();
    }).catch(() => { /* 诊断用，取不到就算了 */ });
  });
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
  // **重试派发**（工单 ci-gate-fixes/11）：chip 容器每次选择变化都会被整块重绘
  // （`box.innerHTML = …`），在途的那次重绘会把刚派发的事件连同节点一起换掉 —— 那次点击
  // 等于白点，而"等 10 秒仍不空"在慢机器上就会变成一条红（CI 实测：这条先是每次都在
  // afterEach 里记一行，run 36218384073 里第一次从用例体内的 `:1046` 冒出来、把
  // 「检测页 → 生成页」整条判红；同一条用例上一跑是绿的 = 偶发）。
  // 所以：派发 → 等空 → 还空不了就**再派发一次**（最多 5 轮）。真清不干净仍然抛错，
  // 判据没被削弱——只是把"白点一次"从必然失败变成可重试。
  for (let attempt = 0; attempt < 5; attempt++) {
    const dispatched = await page.evaluate(() => {
      const chips = [...document.querySelectorAll("#hwcheck-device-chips [data-remove]")];
      for (const chip of chips) {
        chip.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      }
      return chips.length;
    });
    if (!dispatched) return;
    try {
      await page.waitForFunction(
        () => document.querySelectorAll("#hwcheck-device-chips [data-remove]").length === 0,
        undefined, { timeout: 10000 });
      return;
    } catch (e) { /* 这一轮没清干净：下一轮重派发（别把这一轮的错误吞掉结论） */ }
  }
  throw new Error("器件集清不干净：连续 5 轮派发移除都没等到空集");
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
//
// ⚠ **这行 `console.log` 是判据，不是噪声**（工单 hwcheck-hygiene/08 的诊断结论）：
// 它出现 = `clearDevices()` 连续 5 轮派发都没等到空集。**机制**（08 用定点压测复核过，
// 不是推断）：芯片容器每次选择变化都 `box.innerHTML = …` **整块重绘**，而下面那个
// `page.evaluate` 是**一口气点掉所有 chip** 的——第 1 件的 click 触发重绘，**其余 chip 的
// 节点当场从文档里被摘掉**，它们那几次 click 白点，于是"等 10 秒仍不空"。
// 08 的读数（`.scratch/hwcheck-hygiene/probe-08-clear-race*.txt`）：**两件起清、只派发一次
// → 10/10 与 24/24 都没清掉**（每次只剩最后一件）；**同一形状走下面的重试派发 → 10/10 清掉
// （p50 7ms）**。一件时两种形状都过（第 2 次派发打在空集上无害）——这正是本单第一版压测
// 用单件跑、零命中却什么也没证明的原因（评审抓到）。
// 改法就是下面的**重试派发**；真清不干净（连续 5 轮）仍然大声抛错，判据没被削弱。
// 所以这行一旦再出现，先按"某一步的重绘又变了 / 又多了一批同时段的 chip"查，别当随机噪声。
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

// previewDiag()：**预览载荷**类等待失败时，把"页面那边现在是什么样"一起带进错误里
// （工单 ci-gate-fixes/08）。
//
// 为什么需要它：CI run `36213107191` 上 `:818`/`:914` 两条都死在"等预览载荷渲染出来的东西"
// 上，而错误里只有一句 playwright 超时——分不清是"预览 400 了（后端那句中文原因就亮在接线区）"、
// "载荷里没有这一条"还是"渲染根本没跑"。本机四种条件（缺工具链 / 满载 / CRLF 检出 / UTC）
// 都复现不出来（读数在工单里），所以与其猜，不如让下一次 CI 把答案**带回来**。
async function previewDiag() {
  // ⚠ 响应那一段在 **Node 侧**拼（`previewResponses` 住在测试进程里）——把它放进
  // `page.evaluate` 的闭包里会 `ReferenceError`（浏览器上下文没有这个变量）。
  // 红证 `probe-08-diag-redproof.py` 当场抓到的就是这个：诊断自己炸了、什么都没打出来。
  const responses = `[诊断] 末几次 /api/hwcheck/preview 响应 → ${JSON.stringify(previewResponses)}`;
  try {
    const pageText = await page.evaluate(() => {
      const text = (sel) => {
        const el = document.querySelector(sel);
        return el
          ? el.textContent.replace(/\s+/g, " ").trim().slice(0, 600)
          : `(${sel} 不存在)`;
      };
      return `[诊断] 接线区 #hwcheck-wiring → ${text("#hwcheck-wiring")}\n`
        + `[诊断] 命令台 #hwcheck-console → ${text("#hwcheck-console")}`;
    });
    return `${pageText}\n${responses}`;
  } catch (e) {
    return `[诊断] 连页面文本都没取到：${e.message}\n${responses}`;
  }
}

test("编译复用既有面板与判读：真 UV4 编译绿（工具链缺失时如实 skip）", async (t) => {
  // 工单 ci-gate-fixes/08：这条用例的**前提是真工具链**——`fx/hwcheck-project.js` 的 `ready` 门
  // （读 `/api/state` 的 `toolchains.<platform>`）为 false 时，编译按钮按产品设计**置灰**，
  // 点它只会 30 秒超时（CI run 36213107191 的现场：locator 解析到了元素但 element is not
  // enabled）。开发机装着 Keil 所以这条一直绿，CI runner 上既没有、也不该有 Keil。
  //
  // 缺前提时**显式 skip 并写明原因**：跳过在摘要里看得见，不静默变绿，也不拿"超时"冒充
  // "产品坏了"。本机装了 Keil（或在 config.json 配了 `uv4_path`）就跑得到这一条，
  // 判据强度不变。
  const toolchains = await page.evaluate(() => fetch("/api/state")
    .then((r) => r.json()).then((s) => s.toolchains || {}).catch(() => ({})));
  if (toolchains.stm32 === false) {
    t.skip("本机没有 Keil UV4（/api/state.toolchains.stm32=false）——这条要真编译才成立，"
      + "编译按钮此时按产品设计置灰。装上 Keil 或配 config.json 的 uv4_path 后可跑；"
      + "CI runner 上不装 Keil（见工单 ci-gate-fixes/08）");
    return;
  }
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
  // 多实例只验首路（工单 hwcheck-hygiene/07）：led 声明了 multi_instance.max=8，
  // 生成页真能配 4 路，而检测配方只驱动第一路——这句话必须在**真页面上**，
  // 否则学生看到回显的通道数会以为每一路都验过了。判据取真 DOM 文本（不是源码串）。
  assert.ok(plan.includes("多实例只验第一路"),
    "多实例件要在页面上如实说「只验第一路」：\n" + plan);

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

test("预览失败：专用文案 + 不留下上一次的 main.c（工单 hwcheck-hardening/07）", async () => {
  await openTab();
  await setParent(parentDir);

  // ① 先正常预览一次：页面上有了一份真的 main.c（下面要证它会消失）
  await page.click("#btn-hwcheck-preview");
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-output").textContent.includes("hwcheck_"));
  const before = await page.textContent("#hwcheck-output");
  assert.ok(before.includes("hwcheck_"), "先要有一份真的预览产物，这条判据才有意义");

  // ② 让下一次预览**真的失败**（拦在浏览器层，回一个 400 中文理由）
  const REASON = "预览测试用的假失败：库中不存在模块 nope";
  await page.route("**/api/hwcheck/preview", (route) => route.fulfill({
    status: 400,
    contentType: "application/json",
    body: JSON.stringify({ detail: REASON }),
  }));
  try {
    await page.click("#btn-hwcheck-preview");
    // 专用文案出现（**不是**"接线表与冲突暂时取不到"——那句会把学生引去查线）
    await page.waitForFunction(
      () => document.querySelector("#hwcheck-output").textContent.includes("检测程序预览失败"));
    const failed = await page.textContent("#hwcheck-output");
    assert.ok(failed.includes("库中不存在模块 nope"), "服务端给的中文理由要原样带出");
    assert.ok(!failed.includes("接线表"), "失败文案不许再把用户引去查接线表");
    // 关键：**上一次的 main.c 必须不在了**（那份属于上一组器件，留着就会被照着烧）
    assert.ok(!failed.includes("hwcheck_write_serial"),
      "预览失败之后还留着上一次的 main.c —— 学生照它编译烧录就是烧错东西：\n"
      + failed.slice(0, 800));
  } finally {
    await page.unroute("**/api/hwcheck/preview");
  }

  // ③ 解除拦截后能正常渲染回来（错误提示也不残留）
  await page.click("#btn-hwcheck-preview");
  await page.waitForFunction(
    () => !document.querySelector("#hwcheck-output").textContent.includes("检测程序预览失败")
      && document.querySelector("#hwcheck-output").textContent.includes("hwcheck_"));
  const recovered = await page.textContent("#hwcheck-output");
  assert.ok(recovered.includes("hwcheck_"), "恢复后要重新渲染出检测程序");
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

// ---------------------------------------------------------------------------
// 工单 hwcheck-unknown-device/06：自建件的**串口复测命令**
//
// 一句话判据：页面命令区说"敲这个字符复测这件"，产物里就必须真有那条 `case`，
// 而且它调的是**上电那一遍同一个函数**（"复测输出与上电同措辞"的结构前提）。
//
// 为什么必须真浏览器：载荷里有 `commands` 不等于命令区画出来了、也不等于它与
// 产物里那条 case 是同一个字符——这条把页面读到的字符直接拿去产物里找。
//
// ⚠ 同样**排在文件最后**：这一条也会生成一个新工程（与上一条同一条理由）。
// ---------------------------------------------------------------------------
test("自建件的串口复测：页面给出字符与说明，产物里那条 case 认同一个函数", async () => {
  const ID = `${MY_DEVICE_ID}rt`;
  await openTab();
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.check('input[data-hwcheck-channel="debug_uart"]');
  await myDeviceFill({
    name: "验收用的复测件", bus: "i2c", address: "0x68",
    register: "0x75", expect: "0x68", id: ID,
  });
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${ID}"]`);
  await page.click(`[data-my-device-pick="${ID}"]`);
  await page.waitForSelector(`#hwcheck-device-chips [data-remove="${ID}"]`);

  // ① 命令区：自建件那一行有字符 / 名称 / 标注词 / 说明（全部来自服务端载荷）
  try {
    await page.waitForSelector("#hwcheck-console .hwcheck-table");
  } catch (e) {
    throw new Error(`等命令表超时（#hwcheck-console .hwcheck-table）：${e.message}\n`
      + await previewDiag());
  }
  const row = await page.evaluate((id) => {
    const rows = [...document.querySelectorAll("#hwcheck-console .hwcheck-table tbody tr")];
    const hit = rows.find((r) => r.textContent.includes(id));
    if (!hit) return null;
    const cells = [...hit.querySelectorAll("td")].map((td) => td.textContent);
    return { command: cells[0].trim(), label: cells[1], description: cells[2] };
  }, ID);
  assert.ok(row, "命令表里要有自建件那一行：\n"
    + await page.textContent("#hwcheck-console"));
  assert.equal(row.command.length, 1, "复测字符是单字符：" + JSON.stringify(row));
  assert.ok(row.label.includes("验收用的复测件"), "要认得出是哪一件（名称）：" + row.label);
  assert.ok(row.label.includes("自建件"), "要标出这是自建件（不冒充库内验证过的结论）：" + row.label);
  assert.ok(row.description.trim(), "说明那一列不许空着：" + row.description);

  // ② 产物：同一个字符的 case 在，且复测调的是上电那一遍同一个函数
  await page.click("#btn-hwcheck-preview");
  await page.waitForFunction(
    (command) => document.querySelector("#hwcheck-output").textContent
      .includes(`case '${command}':`),
    row.command, { timeout: 30000 });
  const mainC = await page.textContent("#hwcheck-output");
  const call = `hwcheck_custom_${ID}();`;
  const calls = mainC.split(call).length - 1;
  assert.equal(calls, 2,
    "上电那一遍 + 命令台复测那一遍（同一个函数 = 同一措辞），实际 " + calls + " 次：\n"
    + mainC.slice(0, 2000));
  const defined = mainC.split(`static void hwcheck_custom_${ID}(void)`).length - 1;
  assert.equal(defined, 1, "小节只定义一处（命令台不许自带一份副本）");
  assert.ok(mainC.indexOf(call) < mainC.indexOf("while (1)"),
    "上电那一遍要先调到它：\n" + mainC.slice(0, 2000));
  assert.ok(mainC.includes("hwcheck_console_poll();"),
    "命令台要在产物里（不然页面那个字符没人认）：\n" + mainC.slice(0, 2000));

  // ③ 不勾串口 → 明说不能交互式复测（照既有口径），命令表不摆出来
  await page.uncheck('input[data-hwcheck-channel="debug_uart"]');
  await page.waitForFunction(
    () => document.querySelector("#hwcheck-console").textContent
      .includes("不能交互式复测"));
  assert.ok(!(await page.textContent("#hwcheck-console")).includes(ID),
    "不能复测的一趟不摆命令表");
  await page.check('input[data-hwcheck-channel="debug_uart"]');

  await myDeviceCleanup([ID]);
});


test("资料 → 事实草稿：入口与知情文案在页面上；空文本点击给本地提示（零 LLM）", async () => {
  // 本支 spec 的既有纪律是「检测生成零 LLM，不花额度」——这条用例守住同一条线：
  // 只验**入口渲染**与**本地提示**，不点出任何一次真抽取（浏览器夹具继承真机
  // 配置，真点一次就是真调 LLM）。抽取 / 填表 / 降级三路都有端点与 fx 用例钉着。
  await page.click(HWCHECK_TAB);
  await page.waitForSelector("#my-devices-material .my-device-material-notice");

  // ① 知情文案（票面硬要求：页面**明说**资料会被送到 AI 通道 + AI 不写代码）
  const notice = await page.textContent(".my-device-material-notice");
  const flat = notice.replace(/\s+/g, "");
  assert.ok(flat.includes("资料会被送到AI通道"), notice);
  assert.ok(flat.includes("不写代码"), notice);

  // ② 空文本点击 → 本地提示（先贴一段资料），不发任何请求
  await page.click("[data-my-device-draft]");
  await page.waitForSelector(".my-device-material-message");
  const message = await page.textContent(".my-device-material-message");
  assert.ok(message.includes("先贴一段资料"), message);
});

// ---------------------------------------------------------------------------
// 工单 hwcheck-acceptance/03：被拦下时的**出路**要点名这一页上真有的控件
//
// 一句话判据：学生读到的那句话，照着做必须走得通。所以这条用例不满足于读文本
// ——它**照着那句话做一遍**（取消勾选「OLED 屏」）再生成，必须成功。
//
// 现场 = 地猛星 + 默认双通道 + xunji + rc522（与 tests/test_hwcheck_board.py 的
// 同脚那一条同一个组合）：撞的既有通道带进来的 oled、也有器件 rc522。旧文案
// （"回到上面的器件选择去掉一件"）在这儿是指错的——oled 根本不在器件列表里，
// 它是「2. 输出通道」里的勾选框。
//
// ⚠ **排在文件最后**：这一条会生成一个新工程（与上面两条自建件用例同一条理由
// ——它们靠"上一次生成的目录"回读，不能被这一条抢走）。
// ---------------------------------------------------------------------------
test("装不下时的出路点名这一页的控件：照着它做（取消勾选 OLED 屏）真能生成", async () => {
  await openTab();
  await page.click('[data-hwcheck-platform="mspm0"]');
  await pickDevice("xunji");
  await pickDevice("rc522");
  await page.waitForSelector('#hwcheck-device-chips [data-remove="rc522"]');

  // 选齐两件就被拦下：**生成之前**就把 400 原文显示出来（不是等点了生成才知道）。
  // ⚠ 落点是**产物区**（工单 hwcheck-hardening/07）：这段文案以前挂在接线区、顶着
  // 「接线表与冲突暂时取不到」的标题——那句会把学生引去查线；现在它归到
  // `previewError`（标题是"检测程序预览失败"），接线区在失败时留空。
  try {
    await page.waitForFunction(
      () => document.querySelector("#hwcheck-output").textContent
        .includes("【检测页出路】"), undefined, { timeout: 30000 });
  } catch (e) {
    throw new Error(`等产物区的「【检测页出路】」超时：${e.message}\n` + await previewDiag());
  }
  const copy = await page.textContent("#hwcheck-output");
  assert.ok(copy.includes("检测程序预览失败"), "标题要说清是哪一步失败：\n" + copy.slice(0, 300));
  assert.ok(copy.includes("取消勾选「2. 输出通道」里的「OLED 屏」"),
    "通道带进来的那一方要点名那个勾选框：\n" + copy);
  assert.ok(copy.includes("去掉「3. 要测的器件」里勾上的 rc522"),
    "器件带进来的那一方要点名器件清单里那一件：\n" + copy);
  assert.ok(!copy.includes("回到上面的器件选择"),
    "旧文案把人支去器件列表——oled 不在那儿（票面反例）：\n" + copy);

  // 点「生成检测工程」是同一句话（预览 / 生成同一判据，都 400）
  await setParent(parentDir);
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("#hwcheck-project .error", { timeout: 60000 });
  const error = await page.textContent("#hwcheck-project .error");
  assert.ok(error.includes("取消勾选「2. 输出通道」里的「OLED 屏」"), error);
  assert.ok(error.includes("去掉「3. 要测的器件」里勾上的 rc522"), error);

  // **照着那句话做**：取消勾选「OLED 屏」→ 拦下消失 → 再生成一次，成功。
  await page.uncheck('input[data-hwcheck-channel="oled"]');
  await page.waitForSelector("#hwcheck-wiring .hwcheck-table", { timeout: 30000 });
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });
  const path = await page.textContent(".hwcheck-path");
  assert.ok(path.includes(parentDir), "照着做之后应真的生成出工程：" + path);
  assert.match(path, /hwcheck-mspm0-\d{8}-\d{6}/, "目录名形态固定");
  await page.check('input[data-hwcheck-channel="oled"]');
});

// ---------------------------------------------------------------------------
// 工单 hwcheck-acceptance/04：检测页 → 生成页的衔接（只带器件、不带引脚）
//
// 一句话判据：在检测页选中的**库内**器件，点一下就真的出现在生成页的已选清单里
// （并触发依赖展开）；库外自建件**没有**跟过去，而页面在点之前就把原因说清了。
//
// 为什么必须真浏览器：`tests/js/hwcheck.test.mjs` 能证 fx 算得对、接线写了，但
// "点下去真的进了**另一个栏目**的选择集"是跨模块的运行时行为（页签切换 + 生成页
// 状态 + 真 /api/selection/expand）——只有真浏览器 + 真后端能作证。
//
// ⚠ **排在文件最后**：这一条会动生成页的选择集，而上面几条靠"上一次生成的目录"
// 回读（同 03 那条的理由）。
// ---------------------------------------------------------------------------
const HANDOFF_DEVICE_ID = `mine_handoff${Date.now().toString().slice(-6)}`;

test("检测页 → 生成页：库内件一键带过去并置为选中态；库外自建件不带并说明原因", async () => {
  await openTab();
  // ① 生成页先选定平台：不选的话带过去只会停在「已选（未展开依赖）」那一行，
  //    验不到依赖展开这一跳（而"带过去之后能直接配引脚"正是这个入口的意义）。
  await page.click('nav button[data-tab="generate"]');
  await page.waitForSelector("#platforms .platform-card:not(.disabled)");
  await page.click("#platforms .platform-card:not(.disabled)");
  await page.waitForSelector("#platforms .platform-card.selected");

  // ② 回检测页：选一件库内件 + 建一件库外自建件并选上
  await page.click(HWCHECK_TAB);
  await page.waitForSelector("#tab-hwcheck", { state: "visible" });
  await clearDevices();                      // 上一次检测回读来的器件先清掉
  await pickDevice("led");
  await page.waitForSelector('#hwcheck-device-chips [data-remove="led"]');
  await myDeviceFill({
    name: "验收用的库外件（带过去那条路不该认它）", bus: "i2c", address: "0x68",
    register: "0x75", expect: "0x68", notes: "验收造的一件", id: HANDOFF_DEVICE_ID,
  });
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${HANDOFF_DEVICE_ID}"]`);
  await page.click(`[data-my-device-pick="${HANDOFF_DEVICE_ID}"]`);
  await page.waitForSelector(`#hwcheck-device-chips [data-remove="${HANDOFF_DEVICE_ID}"]`);

  // ③ **点之前**页面就把话说全了：带哪几件、哪件不带（为什么）、引脚不带
  const box = await page.textContent("#hwcheck-handoff");
  assert.ok(box.includes("只带器件、不带引脚"), "引脚那一句必须在：" + box);
  assert.ok(box.includes("led"), "要点名带哪几件：" + box);
  assert.ok(box.includes("验收用的库外件"), "要点名是哪一件自建件：" + box);
  assert.ok(box.includes("不在模块库里"), "要说清自建件为什么带不过去：" + box);
  const label = (await page.textContent("[data-hwcheck-handoff]")).trim();
  assert.equal(label, "把这 1 件带进生成页", "只有库内那一件算数：" + label);
  assert.equal(await page.isDisabled("[data-hwcheck-handoff]"), false, "有可带的就该可点");

  // ④ 真点：落到生成页，已选清单里真的有 led（且**没有**那件自建件）。
  //    顺手**数一次请求**：这一批只许打一次 /api/selection/expand（逐件并入会连打
  //    N 次）——这是行为判据，不该去数源码里 runExpand() 出现了几次（双轴评审整改）。
  const expandCalls = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/api/selection/expand")) {
      expandCalls.push(req.url());
    }
  });
  await page.click("[data-hwcheck-handoff]");
  await page.waitForSelector("#tab-generate", { state: "visible" });
  await page.waitForFunction(
    () => document.querySelector("#selected-count").textContent.includes("已展开"),
    undefined, { timeout: 30000 });
  const selected = await page.textContent("#selected-list");
  assert.ok(selected.includes("led"), "带过去的那件要在已选清单里：" + selected);
  assert.ok(!selected.includes(HANDOFF_DEVICE_ID),
    "库外自建件不许进生成载荷（它没有 manifest、不进 slugs）：" + selected);
  assert.equal(expandCalls.length, 1,
    "并入一批只许展开一次（实际 " + expandCalls.length + " 次 /api/selection/expand）");
  // ⚠ 读**最新那条** toast（#toast-root 里最多并存 3 条：上一步"已存进我的器件"那条
  // 还在，读整个容器会把两次点击的文案混在一起 —— 本机实测踩到）
  const toast = await page.textContent("#toast-root .toast:last-child");
  assert.ok(toast.includes("已带进生成页 1 件"), "要给一句「带过去了几件」：" + toast);
  assert.ok(toast.includes("引脚"), "顺带再说一次引脚不带：" + toast);

  // ④b 再点一次同一批：**不重复加、不再展开**，页面上如实说"本来就在工程里"
  await page.click(HWCHECK_TAB);
  await page.waitForSelector("#tab-hwcheck", { state: "visible" });
  expandCalls.length = 0;
  await page.click("[data-hwcheck-handoff]");
  await page.waitForSelector("#tab-generate", { state: "visible" });
  const toast2 = await page.textContent("#toast-root .toast:last-child");
  assert.ok(toast2.includes("本来就在工程里"), "第二次点要说清它已经在工程里：" + toast2);
  assert.ok(!toast2.includes("已带进生成页"), "没新加就不许说带过去了：" + toast2);
  const listed = await page.textContent("#selected-list");
  assert.equal((listed.match(/\bled\b/g) || []).length, 1, "不许加出第二份：" + listed);

  // ⑤ 只剩库外件时：按钮置灰 + 理由留在页面上（不是"点了没反应"）
  await page.click(HWCHECK_TAB);
  await page.waitForSelector("#tab-hwcheck", { state: "visible" });
  await page.evaluate((slug) => {
    document.querySelector(`#hwcheck-device-chips [data-remove="${slug}"]`)
      .dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  }, "led");
  await page.waitForFunction(() => {
    const box = document.querySelector("#hwcheck-handoff");
    const btn = box && box.querySelector("[data-hwcheck-handoff]");
    return !!btn && btn.disabled;
  }, undefined, { timeout: 10000 });
  const box2 = await page.textContent("#hwcheck-handoff");
  assert.ok(box2.includes("都带不过去"), box2);
  assert.ok(box2.includes("验收用的库外件"), box2);
  assert.equal(expandCalls.length, 0, "只有库外件时一次展开都不该发：" + expandCalls.length);

  // 收尾：删掉这件自建件（它住在用户数据目录里，不该留下）
  await myDeviceCleanup([HANDOFF_DEVICE_ID]);
  await clearDevices();
});

// ---------------------------------------------------------------------------
// 工单 hwcheck-hygiene/12：把「源码里有这行」换成「点下去会怎样」
//
// 11 号单把 `ui/hwcheck.js` 拆成四件时，35 条读源码串的断言跟着搬了家。本单逐条判它们
// 测的是**纯函数行为**还是 **ui 接线**：接线的那些**删掉**，改成这里的行为用例——
// 断言的对象从"源码某处写着 `renderMyDevices()`"变成"点了之后页面上真的变了"。
// 每条用例的注释里点名它替掉的是哪一条（票尾有整张对照表）。
//
// 这一组自带前提（本文件用例共用一张页面）：能清 localStorage 的先清，再 `openTab()`——
// 「上次看的检测工程」那份备忘会让首帧就回读出一份工程，空态类断言会被上一条的残留喂绿。
// ---------------------------------------------------------------------------

// freshTab()：清掉本地备忘（最近看的检测工程 / 勾选态）再打开本栏目——空态判据的前提。
async function freshTab() {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => localStorage.clear());
  await openTab();
}

// myDeviceValues()：当前表单的字段现值（按 data-my-device-field 逐项取）。
const myDeviceValues = () => page.evaluate(() => Object.fromEntries(
  [...document.querySelectorAll("[data-my-device-field]")]
    .map((el) => [el.dataset.myDeviceField, el.value])));

test("「我的器件」：手填过 id 就不被「名称 → id 建议」覆盖（替掉「ui 的 id 建议不覆盖用户手填的 id」）", async () => {
  await freshTab();
  await page.click("#btn-my-device-new");
  await page.waitForSelector("[data-my-device-form]");

  // ① 先手动定下 id，再回来改名称并失焦 —— 手填的 id 必须原样留着
  await myDeviceType('[data-my-device-field="id"]', MY_DEVICE_ID);
  await myDeviceType('[data-my-device-field="name"]', "手填过 id 的件");
  assert.equal(await page.inputValue('[data-my-device-field="id"]'), MY_DEVICE_ID,
    "手填的 id 被名称建议覆盖了");

  // ② 反向对照：id 还是自动建议值时，改名称**应当**跟着更新
  //    （没有这一半，上一条"两边都不动"也能绿）
  await page.fill('[data-my-device-field="id"]', "");
  await myDeviceType('[data-my-device-field="name"]', "gyro module");
  assert.equal(await page.inputValue('[data-my-device-field="id"]'), "mine_gyro_module",
    "id 为空时该按名称给建议");
  await page.click("[data-my-device-cancel]");
});

test("「我的器件」：逐字打字不被整块重绘吞掉，补 id 建议也不清空别的字段（替掉两条源码串断言）", async () => {
  await freshTab();
  await page.click("#btn-my-device-new");
  await page.waitForSelector("[data-my-device-form]");

  // ① 逐字打地址：每敲一个字符都会触发一次表单同步 —— 那次同步若整块重绘，
  //    正在打字的 `<input>` 会被换掉，现象就是"打一个字表单就清空"
  await page.click('[data-my-device-field="address"]');
  await page.keyboard.type("0x68");
  assert.equal(await page.inputValue('[data-my-device-field="address"]'), "0x68",
    "打字被整块重绘吞掉了");

  // ② 先填好地址 / 寄存器 / 期望值，再改名称并失焦（失焦会按名称补 id 建议）——
  //    补建议只许动 id 那一个框，别把刚填的字段一起刷回初值
  await myDeviceType('[data-my-device-field="register"]', "0x75");
  await myDeviceType('[data-my-device-field="expect"]', "0x68");
  await myDeviceType('[data-my-device-field="name"]', "卖家给的六轴模块");
  const values = await myDeviceValues();
  assert.equal(values.address, "0x68", "补 id 建议把地址清了：" + JSON.stringify(values));
  assert.equal(values.register, "0x75", "补 id 建议把寄存器清了：" + JSON.stringify(values));
  assert.equal(values.expect, "0x68", "补 id 建议把期望值清了：" + JSON.stringify(values));
  assert.equal(values.id, "mine_device", "中文名派生不出 slug 时该给 mine_device：" + values.id);
  await page.click("[data-my-device-cancel]");
});

test("「我的器件」：切平台不丢正在填的表单（件与平台无关；替掉「不随平台清空」）", async () => {
  await freshTab();
  await page.click("#btn-my-device-new");
  await page.waitForSelector("[data-my-device-form]");
  await myDeviceType('[data-my-device-field="name"]', "填到一半的件");
  await myDeviceType('[data-my-device-field="address"]', "0x68");
  const before = await myDeviceValues();

  await page.click('[data-hwcheck-platform="mspm0"]');
  await page.waitForFunction(
    () => document.querySelector('[data-hwcheck-platform="mspm0"]').classList.contains("selected"));
  const after = await myDeviceValues();
  assert.deepEqual(after, before, "换平台把正在填的表单清了");
  assert.ok(await page.$("[data-my-device-form]"), "换平台不该把表单收起来");
  await page.click("[data-my-device-cancel]");
});

test("顶部总口径真的在页面上（未上板那句；替掉「结构钉：总口径那句真的被渲染出来」）", async () => {
  await freshTab();
  const text = await page.textContent("#hwcheck-unverified-note");
  assert.ok(text.includes("尚未在真板上验证过"), "总口径没渲染出来：" + text);
  assert.ok(text.includes("能生成 + 能编译"), "总口径该说清证据到哪一步：" + text);
  assert.ok(!text.includes("**"), "总口径里出现了字面星号：" + text);
});

test("空态：串口复测那句把自建件也算进去（替掉「ui 的空态文案把自建件也算进」）", async () => {
  await freshTab();
  const text = await page.textContent("#hwcheck-console");
  assert.ok(text.includes("库内器件按配方、自建件按它自己的探测小节"),
    "空态文案没把自建件算进「哪些能复测」：" + text);
  assert.ok(!text.includes("**"), "空态文案里出现了字面星号：" + text);
});

test("器件卡「说明」：开弹窗，且**不**把这一件加进 / 移出这次检测（替掉「ui 的说明弹窗走既有委托」）", async () => {
  await freshTab();
  await clearDevices();
  await page.waitForSelector("#hwcheck-device-grid .module-card .mc-info");
  const slug = await page.evaluate(
    () => document.querySelector("#hwcheck-device-grid .module-card").dataset.add);
  await page.click(`#hwcheck-device-grid [data-add="${slug}"] .mc-info`);
  await page.locator(".module-info-overlay").waitFor({ state: "visible" });
  const head = await page.textContent(".module-info-overlay .module-info-head");
  assert.ok(head.includes(slug), "弹窗里该是这一件：" + head);
  const devices = await page.evaluate(() => [...document.querySelectorAll(
    "#hwcheck-device-chips [data-remove]")].map((el) => el.dataset.remove));
  assert.ok(!devices.includes(slug), "点「说明」把这一件加进选择集了：" + devices.join(","));
  await page.keyboard.press("Escape");
  await page.locator(".module-info-overlay").waitFor({ state: "detached" });
});

test("单平台件在错平台上标「需切换平台」（替掉「器件挑选面按当前平台标记」那条源码串断言）", async () => {
  await freshTab();
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.waitForSelector("#hwcheck-device-grid .module-card");
  const off = await page.evaluate(() => [...document.querySelectorAll(
    "#hwcheck-device-grid .module-card.off")].map((el) => ({
    slug: el.dataset.add, text: el.textContent.replace(/\s+/g, " "),
  })));
  assert.ok(off.length > 0,
    "stm32 页面上应当有「本平台没有条目」的卡片（sr04 这类只有 mspm0 条目）");
  const bad = off.filter((c) => !c.text.includes("需切换平台"));
  assert.deepEqual(bad, [], "这些单平台件没标「需切换平台」：" + JSON.stringify(bad));
});

test("「我的器件」删掉一件时，它同时从这次检测的选择里去掉（替掉同名源码串断言）", async () => {
  await freshTab();
  await myDeviceFill({
    name: "删掉要连坐的件", bus: "i2c", address: "0x68", id: MY_DEVICE_ID,
  });
  await page.click("[data-my-device-save]");
  await page.waitForSelector(`[data-my-device-row="${MY_DEVICE_ID}"]`);
  await page.click(`[data-my-device-pick="${MY_DEVICE_ID}"]`);
  await page.waitForSelector(`#hwcheck-device-chips [data-remove="${MY_DEVICE_ID}"]`);

  await page.click(`[data-my-device-del="${MY_DEVICE_ID}"]`);
  // 先等一等（产品是"删完再对齐选择集"）：等不到不算通过，**下面的断言说了算**——
  // 直接让 waitForFunction 抛超时，红点就落在一句泛泛的 Timeout 上，读的人看不出是哪一步。
  await page.waitForFunction(
    (id) => !document.querySelector(`#hwcheck-device-chips [data-remove="${id}"]`),
    MY_DEVICE_ID, { timeout: 15000 }).catch(() => { /* 交给下面那句断言点名 */ });
  const chips = await page.evaluate(() => [...document.querySelectorAll(
    "#hwcheck-device-chips [data-remove]")].map((el) => el.dataset.remove));
  assert.ok(!chips.includes(MY_DEVICE_ID),
    "删掉之后 chips 里还挂着它（下次预览就是 400 未知模块）：" + chips.join(","));
  const listed = await page.evaluate(async () => {
    const body = await (await fetch("/api/my-devices")).json();
    return body.devices.map((d) => d.id);
  });
  assert.ok(!listed.includes(MY_DEVICE_ID), "服务端也该没有这件：" + listed.join(","));
});

test("生成检测工程时，上一次填的现象一起归零（替掉「生成新工程时清掉现象与建议」）", async () => {
  await freshTab();
  await setParent(parentDir);
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.fill("#hwcheck-symptom", "上一趟的现象：灯也不闪");
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });
  assert.equal(await page.inputValue("#hwcheck-symptom"), "",
    "生成新工程后，现象框该清空（那句话属于上一个工程）");
});

test("库数据里的说明文字零字面星号（配方 note / 模块简介 / 平台备注；工单 14）", async () => {
  // 12 号单把"零字面星号"的浏览器半**收窄到产品模板文案**，因为当场抓到一处既有缺陷：
  // 库数据里的 markdown 粗体标记经 esc() 原样进页面（配方 note 2434 处 / 74 个 manifest
  // 1844 处）。14 号单在渲染层支持 `**粗**` → <strong>，这一条就是**放开后的那一半**：
  // 判的是**库数据**渲染出来的说明文字。
  await freshTab();
  await page.click('[data-hwcheck-platform="stm32"]');

  // ① 配方说明：选上 adc（stm32/mspm0 两格的 note 里都有成对标记）→ 专精小节的说明行
  await page.fill("#hwcheck-device-search", "adc");
  await page.waitForSelector('#hwcheck-device-grid [data-add="adc"]');
  await page.click('#hwcheck-device-grid [data-add="adc"]');
  await page.waitForFunction(
    () => {
      const box = document.querySelector("#hwcheck-sections");
      return !!box && box.textContent.includes("本件必须接个已知电压才有意义");
    }, undefined, { timeout: 60000 });
  const sections = await page.textContent("#hwcheck-sections");
  const starsInSections = sections.indexOf("**");
  assert.equal(starsInSections, -1,
    "配方说明里的字面星号没转掉：…"
    + sections.slice(Math.max(0, starsInSections - 60), starsInSections + 60) + "…");
  assert.ok(sections.includes("本件必须接个已知电压才有意义"),
    "那句话本身还得在（转换不许把内容吃掉）");
  assert.ok(await page.evaluate(() => !!document.querySelector(
    "#hwcheck-sections .hwcheck-hint strong")),
    "成对标记该渲染成 <strong>（不是被剥掉了）");

  // ② 模块简介 + 平台备注：说明弹窗里的文本来自 manifest（vl53l0x 的 stm32 notes 有 44 处标记）
  await page.fill("#hwcheck-device-search", "vl53l0x");
  await page.waitForSelector('#hwcheck-device-grid [data-add="vl53l0x"] .mc-info');
  await page.click('#hwcheck-device-grid [data-add="vl53l0x"] .mc-info');
  await page.locator(".module-info-overlay").waitFor({ state: "visible" });
  const dialog = await page.textContent(".module-info-overlay");
  const starsInDialog = dialog.indexOf("**");
  assert.equal(starsInDialog, -1,
    "说明弹窗里的字面星号没转掉：…"
    + dialog.slice(Math.max(0, starsInDialog - 60), starsInDialog + 60) + "…");
  assert.ok(dialog.includes("备注："), "弹窗里该有平台备注那一行（否则这条判据面是空的）");
  await page.keyboard.press("Escape");
  await page.locator(".module-info-overlay").waitFor({ state: "detached" });

  // ③ 模块卡简介（正文 + title 属性两条路：正文转标签、属性只剥标记）
  const card = await page.evaluate(() => {
    const el = document.querySelector('#hwcheck-device-grid [data-add="vl53l0x"]');
    return el ? { text: el.querySelector(".mc-desc").textContent, title: el.getAttribute("title") } : null;
  });
  assert.ok(card, "找不到 vl53l0x 的卡片");
  assert.ok(!card.text.includes("**"), "卡片简介正文里有字面星号：" + card.text);
  assert.ok(!card.text.includes("<strong>"), "卡片简介正文里出现了**转义后的**标签字面量：" + card.text);
  assert.ok(!card.title.includes("**"), "卡片 title 属性里有字面星号：" + card.title);
  assert.ok(!card.title.includes("<strong>"), "title 属性里被塞了标签：" + card.title);
});

test("栏目里**产品自己写的**文案零字面星号（工单 02 的产物在浏览器这一层的那一半）", async () => {
  // 02 号单修的是"提示文案里写 `**加粗**`，到页面上就是两个字面星号"。
  // 前端门禁那一半是 `bold-marker-guard` 判据 ⑨（只判 JS 产品串）；真页面这一半此前没有。
  //
  // ⚠ 判据面 = **产品模板写出来的那几个容器**（下面逐个点名）：它们的文案住在 fx 里，
  // 判据 ⑨ 与这一条因此是同一件事的两半。**库数据**（配方 `note` / manifest 简介）里的
  // `**` 不在这条判据面里——本单实测那是一处**既有缺陷**（配方 2434 处 / 74 个 manifest
  // 1850 处，`esc()` 之后原样进页面），已另开工单记账，别在这里混着判。
  const PRODUCT_COPY = [
    "#hwcheck-unverified-note", "#hwcheck-channel-note", "#hwcheck-wiring",
    "#hwcheck-conflicts", "#hwcheck-order", "#hwcheck-console", "#hwcheck-console-note",
    "#hwcheck-custom", "#hwcheck-handoff", "#hwcheck-project", "#hwcheck-checklist",
    "#hwcheck-advice", "#hwcheck-device-missing", "#hwcheck-device-groups",
  ];
  await freshTab();
  await setParent(parentDir);
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });
  await page.waitForSelector("#hwcheck-device-grid .module-card");
  await page.click("#hwcheck-device-grid .module-card");
  await page.click("#btn-hwcheck-preview");
  await page.waitForSelector("[data-hwcheck-code]", { timeout: 60000 });

  const found = await page.evaluate((selectors) => selectors.flatMap((sel) => {
    const el = document.querySelector(sel);
    const text = el ? el.textContent : "";
    if (!text.includes("**")) return [];
    return [`${sel}：…${text.slice(Math.max(0, text.indexOf("**") - 60), text.indexOf("**") + 60)}…`];
  }), PRODUCT_COPY);
  assert.deepEqual(found, [],
    "产品文案里出现了字面星号（学生看到的是两个星号，不是加粗）：\n  " + found.join("\n  "));
});

test("地猛星双通道撞脚：修法说明与移脚提示里零字面星号（02 号单实测的那一处）", async () => {
  // 02 号单实测的五处里，这一处最容易撞上：地猛星默认双通道就撞脚，几乎必现。
  await freshTab();
  await page.click('[data-hwcheck-platform="mspm0"]');
  await page.waitForFunction(
    () => document.querySelector('[data-hwcheck-platform="mspm0"]').classList.contains("selected"));
  const note = await page.textContent("#hwcheck-channel-note");
  assert.ok(note.includes("不用你自己改"), "生成前引导没渲染出来：" + note);
  assert.ok(!note.includes("**"), "引导里出现了字面星号：" + note);
  await page.click("#btn-hwcheck-preview");
  await page.waitForSelector("[data-hwcheck-code]", { timeout: 60000 });
  const wiring = await page.textContent("#hwcheck-wiring");
  assert.ok(!wiring.includes("**"), "接线区出现了字面星号：\n" + wiring.slice(0, 400));
});

// ---------------------------------------------------------------------------
// 焦点与可达性（工单 hwcheck-hygiene/06）
//
// 为什么只有真浏览器能作证：`document.activeElement` 是**运行时**事实——源码里写了
// `.focus()` 不等于焦点真落在那一项上（整块 innerHTML 重绘会把节点换掉），
// 可访问名也只有在真 DOM 里查才算数。断言一律按**外部行为**：焦点在哪、按了键会怎样。
// ---------------------------------------------------------------------------

test("无障碍名：三个只有 placeholder 的输入都有可访问名（按可访问名断言）", async () => {
  await openTab();
  const names = await page.evaluate(() => {
    const read = (id) => {
      const el = document.getElementById(id);
      if (!el) return null;
      return el.getAttribute("aria-label")
        || (el.labels && el.labels.length ? el.labels[0].textContent.trim() : "");
    };
    return {
      search: read("hwcheck-device-search"),
      parent: read("hwcheck-parent"),
      symptom: read("hwcheck-symptom"),
    };
  });
  for (const [key, value] of Object.entries(names)) {
    assert.ok(value && value.trim().length > 0, `${key} 没有可访问名（只有 placeholder）：${value}`);
  }
});

test("焦点与可达性：勾选保焦点 / 器件卡键盘可加 / 状态位是 live region（工单 06）", async () => {
  // 这一条**自带前提**（本文件的用例共用一张页面，前面几条会清器件集 / 换平台）：
  // 自己生成一个新检测工程，再从干净状态验焦点与可达性。
  await openTab();
  await setParent(parentDir);
  await page.waitForSelector("#hwcheck-platforms .platform-card");
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });

  // ① 勾一项 → 焦点仍在那一项上（整块 innerHTML 重绘不许把焦点甩回 body）
  // 注意 `.hwcheck-check` 是**外层 label**，真正可聚焦的是它里面的 checkbox
  // （`[data-hwcheck-check]`）——焦点恢复的判据也落在那个 input 上。
  await page.waitForSelector("#hwcheck-checklist input[data-hwcheck-check]");
  const itemId = await page.evaluate(() => {
    const box = document.querySelector("#hwcheck-checklist input[data-hwcheck-check]");
    box.focus();
    return box.dataset.hwcheckCheck;
  });
  await page.locator("#hwcheck-checklist input[data-hwcheck-check]").first().click();
  await page.waitForFunction(
    (id) => {
      const el = document.querySelector(`input[data-hwcheck-check="${id}"]`);
      return !!el && document.activeElement === el;
    }, itemId, { timeout: 10000 });
  assert.notEqual(await page.evaluate(() => document.activeElement.tagName), "BODY",
    "重绘后焦点掉回 body 了");
  await page.locator("#hwcheck-checklist input[data-hwcheck-check]").first().click();   // 勾回去

  // ② 器件卡是键盘可达的按钮：Tab 走得到它，Enter / Space 与点它同义
  await page.waitForSelector("#hwcheck-device-grid .module-card");
  // 从搜索框（器件区里它前面最近的可聚焦元素）起按 Tab，走到第一张卡片为止——
  // 真按键盘、不自己 `.focus()`（自己聚焦等于把"够不够得着"那条判据绕过去了）
  await page.focus("#hwcheck-device-search");
  let tabbed = false;
  for (let i = 0; i < 12 && !tabbed; i += 1) {
    await page.keyboard.press("Tab");
    tabbed = await page.evaluate(() => {
      const el = document.activeElement;
      return !!el && el.classList && el.classList.contains("module-card");
    });
  }
  assert.ok(tabbed, "按 Tab 走不到器件卡（键盘用户到不了）");
  const slug = await page.evaluate(() => document.activeElement.dataset.add);
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("role")), "button",
    "器件卡不是可聚焦的按钮角色");
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    (s) => !!document.querySelector(`#hwcheck-device-chips [data-remove="${s}"]`),
    slug, { timeout: 30000 });
  // 加进去之后焦点落到**它的 chip** 上（卡片已从"还没选"的池子里消失，chip 才是这一件）
  await page.waitForFunction((s) => {
    const chip = document.querySelector(`#hwcheck-device-chips [data-remove="${s}"]`);
    return !!chip && document.activeElement === chip;
  }, slug, { timeout: 10000 });
  await page.keyboard.press(" ");
  await page.waitForFunction(
    (s) => !document.querySelector(`#hwcheck-device-chips [data-remove="${s}"]`),
    slug, { timeout: 30000 });
  // 移除之后焦点回到网格里那张卡（它刚回到"还没选"的池子）
  await page.waitForFunction((s) => {
    const card = document.querySelector(`#hwcheck-device-grid [data-add="${s}"]`);
    return !!card && document.activeElement === card;
  }, slug, { timeout: 10000 });

  // ③ 编译 / 烧录状态位是 live region（读屏会念）
  const regions = await page.evaluate(() => ["hwcheck-compile-status", "hwcheck-flash-status"]
    .map((id) => {
      const el = document.getElementById(id);
      return el ? { id, role: el.getAttribute("role"), live: el.getAttribute("aria-live") } : null;
    }));
  for (const region of regions) {
    assert.ok(region, "状态位应该存在（工程面板渲染后）");
    assert.ok(region.role === "status" || region.live,
      `${region.id} 不是 live region：${JSON.stringify(region)}`);
  }
});

test("动作进行中按钮禁用：预览按住时「预览」按钮是看得见的不可点（工单 06）", async () => {
  // 为什么单独一条、且要自己生成一遍工程：上一条留下的器件增删在途时会触发
  // `refreshHwcheckView` 的"在途排队"（那次预览会**立刻**返回，按钮的禁用窗口短到
  // 抓不住）——那是产品正确的行为（不重复发请求），不是缺陷。这条判据要的是
  // **真正在等的那一刻**，所以从"没有在途请求"的状态出发。
  await openTab();
  await setParent(parentDir);
  await page.waitForSelector("#hwcheck-platforms .platform-card");
  await page.click('[data-hwcheck-platform="stm32"]');
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });

  await page.route("**/api/hwcheck/preview", async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await page.click("#btn-hwcheck-preview");
  await page.waitForFunction(
    () => document.getElementById("btn-hwcheck-preview").disabled, undefined, { timeout: 10000 });
  await page.unroute("**/api/hwcheck/preview");
  await page.waitForFunction(
    () => !document.getElementById("btn-hwcheck-preview").disabled, undefined, { timeout: 30000 });
});

test("两个入口锚（工单 ui-density/04）：首屏就看得见，点了真跳到目标块并高亮一下", async () => {
  // 这一条为什么必须有：用户报的是「输入框点不动」，查下来**点击面没坏**——是
  // 「挑器件 / 登记我的器件」两块在卡片最下面，他往下翻了半天才找到。判据只能是
  // 真浏览器里的**几何**：① 不滚动就能看见；② 点了目标块真进视口（且在黏顶栏之下）；
  // ③ 高亮由 `:target` 那条 CSS 给出（不写 JS——原生锚点就够）。
  //
  // ⚠ **刻意不调 `openTab()`**（本文件其余用例都用它开新页）：这个文件共用一张 page，
  // 而一次整页 `goto` 会**打断上一条用例里尚未结算的路由桩**——实测：那会让本文件在收尾时
  // 抛 `route.continue: Route is already handled!`（unhandledRejection → **文件级**判红，
  // 而每条用例自己都是绿的，最容易被读成"随机红"）。这里只切页签 + 回顶部。
  if (!(await page.isVisible("#tab-hwcheck"))) {
    await page.click(HWCHECK_TAB);
    await page.waitForSelector("#tab-hwcheck", { state: "visible" });
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForSelector(".hwcheck-jump-row .hwcheck-jump");

  // ① 首屏可见（在黏顶栏之下、视口之内）
  const seen = await page.evaluate(() => {
    const headerBottom = document.querySelector("header").getBoundingClientRect().bottom;
    return [...document.querySelectorAll(".hwcheck-jump-row .hwcheck-jump")].map((a) => {
      const r = a.getBoundingClientRect();
      return { text: a.textContent.trim(),
        inView: r.top >= headerBottom && r.bottom <= innerHeight && r.height > 0 };
    });
  });
  assert.equal(seen.length, 2, "应有两个入口锚，实际：" + JSON.stringify(seen));
  for (const one of seen) {
    assert.ok(one.inView, `「${one.text}」应在首屏可见区内（用户不必往下翻）`);
  }

  // ② 点了真跳 + ③ 高亮由 `:target` 那条 CSS 给出（不写 JS——原生锚点就够）
  for (const [label, sel] of [["挑库内器件", "#hwcheck-device-search"],
    ["登记我的器件", "#my-devices"]]) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(150);
    await page.click(`.hwcheck-jump-row .hwcheck-jump:has-text("${label}")`);
    // ① 目标成为 URL 片段目标（`:target` 命中 = 浏览器确实把这一跳给了它）
    await page.waitForFunction((s) => {
      const el = document.querySelector(s);
      return !!el && el.matches(":target");
    }, sel, { timeout: 5000 });
    // ② 高亮规则真的作用在它身上（钉"规则命中"，不钉"动画跑过没有"——后者会看时序脸）
    const anim = await page.evaluate((s) => getComputedStyle(document.querySelector(s)).animationName, sel);
    assert.equal(anim, "hwcheck-flash", `${sel} 应有 :target 高亮，实测 animationName=${anim}`);
    // ③ 目标进视口，且**不被黏顶栏压住**（scroll-margin-top 那条规矩）
    await page.waitForFunction((s) => {
      const el = document.querySelector(s);
      if (!el) return false;
      const r = el.getBoundingClientRect();
      const headerBottom = document.querySelector("header").getBoundingClientRect().bottom;
      return r.top >= headerBottom - 2 && r.top < innerHeight - 40;
    }, sel, { timeout: 5000 });
  }
});
