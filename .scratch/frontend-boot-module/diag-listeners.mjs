// diag-listeners.mjs — 诊断：`INPUT#change` 这批监听器是谁绑的、现在还在不在
// （一次性工具，工单 frontend-boot-module/03 排查用）。
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import { startServer } from "../../tests/browser/server.mjs";

tee(fileURLToPath(import.meta.url), process.argv.slice(2));

const server = await startServer();
let browser;
try {
  browser = await chromium.launch();
  const page = await browser.newPage();
  await page.addInitScript(() => {
    window.__anon = [];
    const orig = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type) {
      try {
        const t = this;
        const anon = t && t.tagName && !t.id && !(typeof t.className === "string" && t.className);
        if (anon && type === "change") {
          const stack = (new Error().stack || "").split("\n").slice(1, 6).join(" | ");
          window.__anon.push(stack);
        }
      } catch (e) { /* ignore */ }
      return orig.apply(this, arguments);
    };
  });
  await page.goto(server.url, { waitUntil: "load" });
  await page.waitForTimeout(2000);
  const facts = await page.evaluate(() => ({
    anonCount: window.__anon.length,
    callers: [...new Set(window.__anon.map((s) => (s.match(/[\w./-]+\.js:\d+:\d+/) || [s.slice(0, 90)])[0]))].slice(0, 10),
    moduleCards: document.querySelectorAll("#module-grid > *").length,
    poolCards: document.querySelectorAll("#module-pool > *").length,
    checkboxes: document.querySelectorAll('input[type="checkbox"]').length,
    platforms: document.querySelectorAll("#platforms .platform-card").length,
  }));
  console.log(JSON.stringify(facts, null, 2));
} finally {
  if (browser) await browser.close();
  await server.stop();
}
