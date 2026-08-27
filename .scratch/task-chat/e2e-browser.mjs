// E2E 冒烟：任务卡序号 + 每卡「和 AI 商量」对话区 + 采纳闭环（工单 task-chat/03）
// 前置：webapp 起在 8000（python -m contest_generator.webapp）；桌面 2021F 工程已拆解。
// 关键：/api/tasks/discuss 走 route 拦截（mock reply，不打真 LLM）；
// /api/tasks/dialog-adopt 走真实端点（真写盘）——验证刷新后采纳徽章仍在；
// 收尾取消采纳（text=""）恢复用户工程原状。
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const BASE = "http://127.0.0.1:8000";
const DIR = "C:/Users/luoji/Desktop/2021F_Smart_Medicine_Car_STM32";
const MOCK_REPLY = "可行。左轮不转多半是驱动方向误配：建议把 TB6612 左右轮方向位互换，再检查占空比是否初始化非零。";

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
});
const page = await browser.newPage();
const failures = [];
const check = (cond, msg) => {
  console.log((cond ? "ok   " : "FAIL ") + msg);
  if (!cond) failures.push(msg);
};

// mock /api/tasks/discuss（多轮继续聊也返回同一回复，形状一致）
await page.route("**/api/tasks/discuss", async (route) => {
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ reply: MOCK_REPLY }) });
});

await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForSelector("#btn-revise-load-dir", { timeout: 15000 });
await page.evaluate(() => {
  const card = document.getElementById("card-revise");
  if (card.classList.contains("collapsed")) card.classList.remove("collapsed");
});
await page.fill("#revise-dir-input", DIR);
await page.click("#btn-revise-load-dir");
await page.waitForFunction(
  () => document.getElementById("revise-load-status").textContent === "加载完成",
  { timeout: 15000 },
);
await page.waitForFunction(
  () => document.querySelectorAll("#tasks-grid .item").length > 0,
  { timeout: 10000 },
);

// ① 序号 + 声明行
const header = await page.evaluate(() => {
  const first = document.querySelector("#tasks-grid .item .head .slug");
  const gridText = document.getElementById("tasks-grid").textContent;
  return { firstSlug: first ? first.textContent : "", hasOrderDecl: gridText.includes("建议按序号从上往下做"), hasNoForce: gridText.includes("不强制") };
});
console.log("首卡标题:", JSON.stringify(header.firstSlug));
check(/\d+ 步/.test(header.firstSlug) && header.firstSlug.includes("第 1 步"), "首卡标题带「第 1 步」序号");
check(header.hasOrderDecl && header.hasNoForce, "网格顶部建议顺序声明（不强制，可跳着做）");

// ② 打开对话区
const dialogBtnCount = await page.locator("#tasks-grid .btn-task-dialog").count();
check(dialogBtnCount > 0, "存在「和 AI 商量」按钮 count=" + dialogBtnCount);
await page.locator("#tasks-grid .btn-task-dialog").first().click();
await page.waitForSelector("#tasks-grid .task-dialog-box", { timeout: 5000 });
const placeholder = await page.locator("#tasks-grid .task-dialog-box input").first().getAttribute("placeholder");
check(!!placeholder && placeholder.includes("想法或纠正"), "对话区展开（输入框占位含「想法或纠正」）");

// ③ 发送 → AI 回复 + 采纳按钮
const input = page.locator("#tasks-grid .task-dialog-box input").first();
await input.fill("左轮不转，是不是方向配错了？");
await page.locator("#tasks-grid .btn-task-dialog-send").first().click();
await page.waitForSelector("#tasks-grid .btn-task-dialog-adopt", { timeout: 10000 });
const replyText = await page.locator("#tasks-grid .sugg-msg.ai").first().textContent();
console.log("AI 回复:", JSON.stringify(replyText.trim().slice(0, 40)));
check(replyText.includes("方向位互换"), "AI 回复渲染（mock 内容）");

// ④ 采纳 → 徽标（真实 dialog-adopt 写盘）
await page.locator("#tasks-grid .btn-task-dialog-adopt").first().click();
await page.waitForSelector("#tasks-grid .item .badge.ok", { timeout: 8000 }).catch(() => {});
await page.waitForFunction(
  () => document.getElementById("tasks-grid").textContent.includes("已采纳对话结论"),
  { timeout: 8000 },
);
console.log("已点击采纳，等待徽标…");
check(true, "「已采纳对话结论」徽标出现在卡上");
const adoptedBadge = await page.evaluate(() => {
  const b = [...document.querySelectorAll("#tasks-grid .badge")].find((x) => x.textContent === "已采纳对话结论");
  return { present: !!b, card: b ? b.closest(".item").querySelector(".head .slug").textContent : "" };
});
console.log("采纳徽标所在卡:", JSON.stringify(adoptedBadge));
check(adoptedBadge.present, "采纳徽标定位成功");

// ⑤ 刷新 → 重新加载 → 采纳徽章仍在（真实落盘）
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector("#btn-revise-load-dir", { timeout: 15000 });
await page.evaluate(() => {
  const card = document.getElementById("card-revise");
  if (card.classList.contains("collapsed")) card.classList.remove("collapsed");
});
await page.fill("#revise-dir-input", DIR);
await page.click("#btn-revise-load-dir");
await page.waitForFunction(
  () => document.getElementById("revise-load-status").textContent === "加载完成",
  { timeout: 15000 },
);
await page.waitForFunction(
  () => document.querySelectorAll("#tasks-grid .item").length > 0,
  { timeout: 10000 },
);
const afterReload = await page.evaluate(() => ({
  adopted: document.getElementById("tasks-grid").textContent.includes("已采纳对话结论"),
  clearBtn: document.querySelectorAll("#tasks-grid .btn-task-dialog-clear").length,
}));
console.log("刷新后:", JSON.stringify(afterReload));
check(afterReload.adopted && afterReload.clearBtn === 1, "刷新后采纳徽标仍在（真实落盘）+ 取消采纳按钮存在");

// ⑥ 取消采纳 → 徽标消失（恢复用户工程原状，零残留）
await page.locator("#tasks-grid .btn-task-dialog-clear").first().click();
await page.waitForFunction(
  () => !document.getElementById("tasks-grid").textContent.includes("已采纳对话结论"),
  { timeout: 8000 },
);
const afterClear = await page.evaluate(() => ({
  adopted: document.getElementById("tasks-grid").textContent.includes("已采纳对话结论"),
}));
console.log("取消采纳后:", JSON.stringify(afterClear));
check(!afterClear.adopted, "取消采纳后徽标消失（工程已恢复原状）");

await page.screenshot({ path: ".scratch/task-chat/e2e-shot-task-chat.png", fullPage: false });
console.log(failures.length ? "FAILURES: " + failures.length : "ALL PASS");
await browser.close();
process.exit(failures.length ? 1 : 0);
