// probe-03-timeorigin.mjs — `performance.timeOrigin` 到底能不能当"这是新文档"的判据
// （工单 launcher-exit-race/04 的取证：验收用例里那道 reload 守卫靠它，先在真浏览器上量）。
//
// 用法：node .scratch/launcher-exit-race/probe-03-timeorigin.mjs
import { chromium } from "playwright";
import { tee } from "./tee.mjs";
import { startServer } from "../../tests/browser/server.mjs";

tee(process.argv[1], process.argv.slice(2));

const server = await startServer();                 // 非启动器模式：这条与退出无关
const browser = await chromium.launch();
const page = await browser.newPage();
const epoch = () => page.evaluate(() => performance.timeOrigin);

await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
await page.waitForFunction(
  () => document.querySelectorAll("#platforms .platform-card").length > 0,
  undefined, { timeout: 30000 });
const first = await epoch();

console.log(`首次加载：timeOrigin = ${first}`);
for (let i = 1; i <= 3; i++) {
  await page.reload({ waitUntil: "domcontentloaded" });
  const now = await epoch();
  console.log(`第 ${i} 次 reload：timeOrigin = ${now}`
    + `（与首次${now === first ? "**相同**（判据不可用）" : "不同 ✓"}；与上一次`
    + `${i > 1 ? "见上" : "—"}）`);
}
// 顺带量：`domcontentloaded` 到底等不等模块图（reload 返回时页面是不是真可用）
await page.reload({ waitUntil: "domcontentloaded" });
const cards = await page.evaluate(() => document.querySelectorAll("#platforms .platform-card").length);
console.log(`reload({waitUntil:"domcontentloaded"}) 返回瞬间：平台卡 ${cards} 个`
  + `（0 = DOMContentLoaded 早于模块图/init，用例必须再等一次 ready）`);

await browser.close();
await server.stop();
console.log("（服务已由本探针收掉）");
