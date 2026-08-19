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
      [{ slug: "k230", files: [] }, { slug: "coord_detect", files: ["code/coord_detect.c", "code/coord_detect.h"] }],
      [{ slug: "k230", output: "main.py" }]
    ),
    "k230(副产物 main.py)、coord_detect(code/coord_detect.c, code/coord_detect.h)"
  );
});

test("done 载荷带模板名 → 副产物摘要回显模板", () => {
  assert.equal(
    formatResModules(
      [{ slug: "k230", files: [] }],
      [{ slug: "k230", output: "main.py", template_id: "rect", template_name: "矩形识别" }]
    ),
    "k230(副产物 main.py（模板：矩形识别）)"
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
