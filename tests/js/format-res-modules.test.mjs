// formatResModules 纯函数单测（工单 frontend-es-modules/08）：产物摘要
// 「模块文件」行——纯副产物模块（files 空 + python_artifact）在摘要里显示
// main.py，普通 C 模块显示文件清单，两者同列。直接 import fx/generate.js，
// 不碰 DOM / fetch。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import { formatResModules, frameworkNoteHTML } from "../../src/contest_generator/static/js/fx/generate.js";

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

test("done 载荷带 assets → 资产文件与副产物同列（工单 03）", () => {
  assert.equal(
    formatResModules(
      [{ slug: "k230", files: [] }],
      [{
        slug: "k230",
        output: "main.py",
        asset_paths: ["mp_deployment_source/model.kmodel", "mp_deployment_source/deploy_config.json"],
      }]
    ),
    "k230(副产物 main.py, 资产 mp_deployment_source/model.kmodel, 资产 mp_deployment_source/deploy_config.json)"
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

// ================= 题型框架注入提示（工单 topic-framework/04） =================

test("frameworkNoteHTML：injected=true → 带题型与来源的提示行", () => {
  const html = frameworkNoteHTML({
    topic_framework: { injected: true, topic_type: "line_follow", source: "21F-巡线送药决策例程" },
  });
  assert.match(html, /题型框架/);
  assert.match(html, /line_follow/);
  assert.match(html, /21F-巡线送药决策例程/);
});

test("frameworkNoteHTML：injected=false / 缺数据 → 空串（不渲染提示行）", () => {
  assert.equal(frameworkNoteHTML({ topic_framework: { injected: false } }), "");
  assert.equal(frameworkNoteHTML({}), "");
  assert.equal(frameworkNoteHTML(undefined), "");
});
