// formatResModules 纯函数单测（工单 k230-vision-copilot/04）：产物摘要
// 「模块文件」行——纯副产物模块（files 空 + python_artifact）在摘要里显示
// main.py，普通 C 模块显示文件清单，两者同列。照 collect-bindings 先例：
// 从 HTML 抽取函数体喂 node:test，不碰 DOM / fetch。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const match = html.match(/function formatResModules[\s\S]*?\n\}/);
assert.ok(match, "index.html 中未找到 formatResModules 函数体（改名了？）");
const formatResModules = new Function("return (" + match[0] + ")")();

test("k230（files 空 + 副产物）→ slug(副产物 main.py)", () => {
  assert.equal(
    formatResModules(
      [{ slug: "k230", files: [] }, { slug: "ball_detect", files: ["code/ball_detect.c", "code/ball_detect.h"] }],
      [{ slug: "k230", output: "main.py" }]
    ),
    "k230(副产物 main.py)、ball_detect(code/ball_detect.c, code/ball_detect.h)"
  );
});

test("无副产物选择 → 旧格式逐字不变（向后兼容）", () => {
  assert.equal(
    formatResModules(
      [{ slug: "dht11", files: ["stm32/src/dht11.c", "inc/dht11.h"] }],
      []
    ),
    "dht11(stm32/src/dht11.c, inc/dht11.h)"
  );
});

test("pythonArtifacts 缺省（undefined）不炸 → 只显示文件清单", () => {
  assert.equal(
    formatResModules([{ slug: "oled", files: ["oled.c"] }], undefined),
    "oled(oled.c)"
  );
});

test("空 files 且无副产物 → 只显示 slug（无空括号）", () => {
  assert.equal(formatResModules([{ slug: "led", files: [] }], []), "led");
});
