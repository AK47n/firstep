// probe-08-clear-race.mjs — 工单 hwcheck-hygiene/08 的**定点复现器**：把浏览器用例里那一步
// （「点掉 chip → 器件集变空」）压到最紧，看它会不会漏。
//
// 为什么要有它（而不是继续连跑整条 spec）：整条 spec 一轮 2 分钟、复现率 0（本轮 23 轮零命中），
// **没有反馈回路就没法诊断**。这里改成"把出问题的那一步单独拿出来压测"：
//
//   加一件 → 立刻按产品的真实路径点掉 → 数 chip → 重复 N 轮，
//   每轮记录**最多等多久才清空**、以及"永远清不掉"的次数。
//
// 判据不是"整条用例绿不绿"，而是这条更细的问题：
// **"点掉 chip" 这一步会不会丢**（派发时机早于重绘 / 重绘把节点连事件一起换掉 / 某状态下按钮不渲染）。
//
// 用法：
//     node .scratch/hwcheck-hygiene/probe-08-clear-race.mjs            # 默认 30 轮
//     node .scratch/hwcheck-hygiene/probe-08-clear-race.mjs 60
//     node .scratch/hwcheck-hygiene/probe-08-clear-race.mjs 40 --slow=6   # 压慢 6 倍（逼近 CI）
//     node .scratch/hwcheck-hygiene/probe-08-clear-race.mjs 40 --variants # 每轮换一种前置动作
//     node .scratch/hwcheck-hygiene/probe-08-clear-race.mjs 60 --single --chips=2
//       ← **量"那一次派发会不会丢"的正确形状**（评审抓到的第一版漏洞：每轮只加一件，
//         而机制要求同时有多件——点第 1 件的重绘会把第 2 件的节点从文档里摘掉，
//         第 2 件那次 click 才真的白点）。
// 读数直接打印（stdout），由调用方重定向落盘（python 侧收全量，见 readings.py 的同类纪律）。

import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const argv = process.argv.slice(2);
const rounds = Number(argv.find((a) => /^\d+$/.test(a)) || 30);
const slow = Number((argv.find((a) => a.startsWith("--slow=")) || "--slow=1").slice(7));
const variants = argv.includes("--variants");
const single = argv.includes("--single");
// 每轮先加**几件**再清（默认 1 = 第一版的形状）。≥2 才是夹具那个失败模式的必要条件：
// 同一拍里点第 1 件 → 产品重绘 chips → 第 2 件的节点已不在文档里，它那次 click 白点。
const chipsPerRound = Number((argv.find((a) => a.startsWith("--chips="))
  || "--chips=1").slice(8));
// 逐轮记录：清空用了多少毫秒（null = 10 秒内没清掉 = 丢事件）
const waitMs = [];
let stuck = 0;

const server = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage();

if (slow > 1) {
  // 压慢 CPU（CDP 的 rate 是"降速倍数"）：CI 的 windows-latest 比本机慢，
  // 而这类丢事件的缺陷**只在慢机器上**露头——不造这个前提就等于没测。
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: slow });
  console.log(`# CPU 压慢 ${slow}×`);
}

// 与 spec 同款的"这一页在说什么"读数：chip 上的 data-remove 就是器件集的可视投影
const chipSlugs = () => page.evaluate(() =>
  [...document.querySelectorAll("#hwcheck-device-chips [data-remove]")]
    .map((el) => el.dataset.remove));

// 产品的"点掉"路径 = 往容器派发一个冒泡 click（容器上挂着事件委托）。
// 返回派发前后的 chip 数——"派发后还是 1"本身就是"这一拍白点了"的直接读数。
//
// `single=true`（`--single`）= **只派发一次、不等重试**：这是本单要量的那个量
// ——"一次派发够不够"。夹具曾经就是一次派发 + 一次等待（`ci-gate-fixes/11` 之前），
// 所以这个数直接回答"当年的偶发是产品不收敛，还是那一次派发被重绘吃掉了"。
const dispatchRemove = (single) => page.evaluate((oneShot) => {
  const before = document.querySelectorAll("#hwcheck-device-chips [data-remove]").length;
  for (const chip of document.querySelectorAll("#hwcheck-device-chips [data-remove]")) {
    chip.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  }
  if (!oneShot) {
    for (const chip of document.querySelectorAll("#hwcheck-device-chips [data-remove]")) {
      chip.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    }
  }
  const after = document.querySelectorAll("#hwcheck-device-chips [data-remove]").length;
  return `派发前 chips=${before} / 派发后 chips=${after}`;
}, single);

try {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#hwcheck-platforms .platform-card",
    { state: "attached", timeout: 30000 });
  await page.click('nav button[data-tab="hwcheck"]');
  await page.waitForSelector("#tab-hwcheck", { state: "visible" });
  await page.click('[data-hwcheck-platform="stm32"]');

  // 三个 slug 轮着来：库内件（led / ml_mpu6050）与"未专精件"（photoresistance）
  // 的渲染路径不同（专精小节 vs 通用小节），轮换能顺带覆盖两条重绘路径。
  const slugs = ["led", "ml_mpu6050", "photoresistance"];
  const platforms = ["stm32", "mspm0"];

  for (let i = 0; i < rounds; i++) {
    const slug = slugs[i % slugs.length];
    let extra = "";
    // ⓪ 上一轮要是真的漏了一件（就是要量这个），先**用带重试的那条路**清干净再进本轮
    //    ——否则"那一件还在选择集里"会让下一轮的加选卡在网格里（卡仍显示为已选），
    //    整轮跑不下去，读数就只能停在第一轮（第一版当场撞上）。
    if ((await chipSlugs()).length) {
      await dispatchRemove(false);
    }
    if (variants) {
      // 四种前置动作轮换——它们各自会触发一次**整块重绘**（平台切换 / 搜索 / 预览 / 清单），
      // 而重绘正是"派发打在旧节点上"的必要条件。
      const mode = i % 4;
      if (mode === 1) {
        await page.click(`[data-hwcheck-platform="${platforms[i % 2]}"]`);
        extra = `切平台→${platforms[i % 2]}`;
      } else if (mode === 2) {
        await page.fill("#hwcheck-device-search", "s");
        extra = "搜索=s";
      } else if (mode === 3) {
        await page.click("#btn-hwcheck-preview");
        extra = "点了预览";
      }
    }
    // ① 加：走网格卡（产品的真实加选路径）——`--chips=N` 时连加 N 件（N≥2 才对得上
    //    夹具 clearDevices 那个"一次 evaluate 点掉所有 chip"的形状）
    const added = [];
    for (let k = 0; k < chipsPerRound; k++) {
      const one = slugs[(i + k) % slugs.length];
      if (added.includes(one)) continue;
      await page.fill("#hwcheck-device-search", one);
      await page.waitForSelector(`#hwcheck-device-grid [data-add="${one}"]`,
        { timeout: 15000 });
      await page.evaluate((s) => {
        document.querySelector(`#hwcheck-device-grid [data-add="${s}"]`)
          .dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      }, one);
      await page.waitForSelector(`#hwcheck-device-chips [data-remove="${one}"]`,
        { timeout: 15000 });
      added.push(one);
    }

    // ② 清：**不等任何东西**，同一拍里点掉所有 chip（照夹具 `clearDevices` 的形状）。
    //    `--single` 时只派发一次、不补点；`--chips=N`(N≥2) 时"第 1 件点完的重绘会把
    //    第 2 件的节点从文档里摘掉"——第 2 件那次 click 就是那个**白点**。
    const started = Date.now();
    const roundMsg = await dispatchRemove(single);
    try {
      await page.waitForFunction(
        () => document.querySelectorAll("#hwcheck-device-chips [data-remove]").length === 0,
        undefined, { timeout: 10000 });
      waitMs.push(Date.now() - started);
      if (i % 5 === 0 || i === rounds - 1) {
        console.log(`轮 ${i + 1}/${rounds} [${added.join("+")}]：清空用了 `
          + `${Date.now() - started}ms（${roundMsg}${extra ? " / " + extra : ""}）`);
      }
    } catch {
      stuck += 1;
      waitMs.push(null);
      const left = await chipSlugs();
      console.log(`轮 ${i + 1}/${rounds} [${added.join("+")}]：⚠ 10 秒没清掉，剩 `
        + `${left.join(",")}（${roundMsg}${extra ? " / " + extra : ""}）`);
    }
    await page.fill("#hwcheck-device-search", "");
  }
} finally {
  const nums = waitMs.filter((v) => v !== null);
  nums.sort((a, b) => a - b);
  const pct = (p) => (nums.length ? nums[Math.min(nums.length - 1,
    Math.floor(nums.length * p))] : -1);
  console.log("");
  console.log(`=== ${rounds} 轮${slow > 1 ? `（CPU ${slow}×）` : ""}`
    + `${variants ? "（每轮换前置动作）" : ""}${single ? "（只派发一次）" : ""}`
    + `：清不掉 ${stuck} 轮；清空耗时 `
    + `p50=${pct(0.5)}ms p90=${pct(0.9)}ms max=${nums[nums.length - 1] ?? -1}ms ===`);
  await browser.close();
  await server.stop();
}
