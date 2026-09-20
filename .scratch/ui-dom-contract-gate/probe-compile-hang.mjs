// 鎺㈤拡锛氬畾浣嶃€屼笁涓?spec 杩炶窇鏃?hwcheck 鐨勭紪璇戠敤渚?180s 瓒呮椂銆嶃€?// 澶嶅埢杩炶窇鏃剁殑鍏抽敭鍓嶅簭锛堢湡 UV4 缂栬瘧杩囧悓涓€鐖剁洰褰曚笅鐨勫彟涓€涓伐绋嬶級锛屽苟閫愭鎶撹鏁般€?import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";
import { mkdtempSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const parentDir = mkdtempSync(join(tmpdir(), "probe-compile-"));
const server = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage();

const log = (...a) => console.log(`[${new Date().toISOString().slice(11, 19)}]`, ...a);
let serverExited = null;
server.proc.on("exit", (code, sig) => { serverExited = { code, sig }; });

try {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#hwcheck-platforms .platform-card", { state: "attached", timeout: 30000 });
  await page.click('nav button[data-tab="hwcheck"]');
  await page.waitForSelector("#tab-hwcheck", { state: "visible" });
  log("椤甸潰灏辩华");

  await page.fill("#hwcheck-parent", parentDir);
  await page.dispatchEvent("#hwcheck-parent", "change");
  await page.click("#btn-hwcheck-generate");
  await page.waitForSelector("[data-hwcheck-compile]", { timeout: 120000 });
  log("宸ョ▼鐢熸垚瀹屾垚 dir=", readdirSync(parentDir)[0]);

  // 鎶撶紪璇戣姹傜殑鍝嶅簲锛堣繖鏄叧閿鏁帮細鏈嶅姟绔埌搴曠瓟浜嗕粈涔堛€佸涔呯瓟鐨勶級
  page.on("response", async (r) => {
    if (!r.url().includes("/api/hwcheck/compile")) return;
    let body = "";
    try { body = (await r.text()).slice(0, 500); } catch (e) { body = `<璇讳笉鍒? ${e.message}>`; }
    log(`compile 鍝嶅簲 ${r.status()} body=${body}`);
  });
  page.on("requestfailed", (r) => log(`璇锋眰澶辫触 ${r.url()} ${r.failure()?.errorText}`));

  const btn = page.locator("[data-hwcheck-compile]");
  await btn.click();
  log("宸茬偣缂栬瘧鎸夐挳");
  try {
    await page.waitForSelector("#hwcheck-compile-status.ok", { timeout: 60000 });
    log("缂栬瘧缁匡細" + (await page.textContent("#hwcheck-compile-status")));
  } catch (e) {
    const st = await page.evaluate(() => ({
      status: (document.getElementById("hwcheck-compile-status") || {}).outerHTML || "锛堟棤姝ゅ厓绱狅級",
      errs: (document.getElementById("hwcheck-compile-errors") || {}).innerText || "",
      btn: (document.querySelector("[data-hwcheck-compile]") || {}).outerHTML || "锛堟棤鎸夐挳锛?,
      path: (document.querySelector(".hwcheck-path") || {}).innerText || "",
      health: null,
    }));
    log("缂栬瘧鏈豢锛岀幇鍦猴細", JSON.stringify(st, null, 2).slice(0, 1500));
    try {
      const r = await fetch(server.url + "/api/health", { signal: AbortSignal.timeout(5000) });
      log(`鍋ュ悍妫€鏌?${r.status}`);
    } catch (e2) {
      log("鍋ュ悍妫€鏌ュけ璐ワ細" + e2.message);
    }
    log("鏈嶅姟杩涚▼ exit =", JSON.stringify(serverExited));
    log("鏈嶅姟鏃ュ織灏鹃儴锛歕n" + server.log().slice(-2500));
  }
} finally {
  await browser.close();
  await server.stop();
  log("done");
}

