import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("C:/Users/luoji/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright");

const browser = await chromium.launch({ headless: true, executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const page = await browser.newPage();
await page.goto("http://127.0.0.1:8814/", { waitUntil: "domcontentloaded" });
await page.waitForSelector("#platforms .platform-card:not(.disabled)");
await page.click("#platforms .platform-card:not(.disabled)");
await page.waitForSelector("#module-grid .module-card[data-add='led']");
await page.click("#module-grid .module-card[data-add='led']");
await page.waitForSelector("#card-instance-config:not(.hidden)");
const info = await page.evaluate(() => {
  const row = document.querySelector("#instance-config .instance-row");
  const sel = row.querySelector("select");
  const inputs = [...row.querySelectorAll("input")].map((i) => ({
    tag: i.tagName,
    type: i.getAttribute("type"),
    list: i.getAttribute("list"),
    w: Math.round(i.getBoundingClientRect().width),
  }));
  return {
    html: row.outerHTML,
    selectCount: row.querySelectorAll("select").length,
    options: sel ? [...sel.options].length : -1,
    inputs,
  };
});
console.log(JSON.stringify(info, null, 2));
await browser.close();
