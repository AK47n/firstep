// 模块库表格行渲染纯函数单测（工单 module-library-ui/01）：
// moduleRowHTML（模块数据 → 表格行 HTML）。只测外部行为（渲染结果），
// 子串断言防脆。后续工单（详情 / 编辑 / 悬空警示）在本文件扩展。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 module-info-dialog.test.mjs 范式）；deps = 注入的兄弟函数依赖
function extract(name, deps) {
  const start = html.indexOf("function " + name);
  assert.ok(start !== -1, "index.html 中未找到 " + name + " 函数体（改名了？）");
  const open = html.indexOf("{", start);
  assert.ok(open !== -1, name + " 函数体缺少左花括号");
  let depth = 0;
  for (let i = open; i < html.length; i++) {
    if (html[i] === "{") depth++;
    else if (html[i] === "}") {
      depth--;
      if (depth === 0) {
        const fnSrc = html.slice(start, i + 1);
        if (deps && Object.keys(deps).length) {
          return new Function(...Object.keys(deps), "return (" + fnSrc + ")")(
            ...Object.values(deps)
          );
        }
        return new Function("return (" + fnSrc + ")")();
      }
    }
  }
  throw new Error("未找到 " + name + " 函数体结束花括号");
}

const esc = extract("esc");
const moduleBadges = extract("moduleBadges", { esc });
const pythonArtifactSummary = extract("pythonArtifactSummary", { esc });
const moduleRowHTML = extract("moduleRowHTML", { esc, moduleBadges, pythonArtifactSummary });

const base = {
  slug: "ultrasonic",
  description: "超声波测距模块，返回厘米距离",
  dependencies: ["delay"],
  platforms: { stm32: { files: ["src/ultra.c"], verified: true, hardware_bound: false } },
};

test("moduleRowHTML 骨干结构：slug 等宽类、简介截断类 + title 全文、操作按钮", () => {
  const out = moduleRowHTML(base);
  assert.ok(out.includes('<td class="slug">ultrasonic</td>'));
  assert.ok(out.includes('<td class="desc-cell" title="超声波测距模块，返回厘米距离">'));
  assert.ok(out.includes("超声波测距模块，返回厘米距离"));
  assert.ok(out.includes('<button data-edit-desc="ultrasonic">改简介</button>'));
  assert.ok(out.includes('<button data-del="ultrasonic" class="danger">删除</button>'));
});

test("moduleRowHTML 简介含特殊字符：单元格与 title 双转义", () => {
  const out = moduleRowHTML({ ...base, description: 'a<b>&"c\'' });
  assert.ok(out.includes('title="a&lt;b&gt;&amp;&quot;c&#39;"'));
  assert.ok(out.includes("a&lt;b&gt;&amp;&quot;c&#39;"));
  assert.ok(!out.includes("<b>&"));
});

test("moduleRowHTML 依赖列：有依赖按顿号连接，无依赖回退 —", () => {
  assert.ok(moduleRowHTML(base).includes('<td class="muted">delay</td>'));
  const noDep = moduleRowHTML({ ...base, dependencies: [] });
  assert.ok(noDep.includes('<td class="muted">—</td>'));
});

test("moduleRowHTML 副产物摘要嵌入依赖列（python_artifact 模块）", () => {
  const out = moduleRowHTML({
    ...base,
    python_artifact: { templates: [{ id: "default", name: "CanMV", description: "K230 侧脚本", template: "py/main.py.tpl", output: "main.py" }], default: "default" },
  });
  assert.ok(out.includes("副产物模板"));
  assert.ok(out.includes("CanMV"));
});

test("moduleRowHTML 平台徽章：已验证 / 硬件绑定 / 未验证 / 内嵌母版", () => {
  const ok = moduleRowHTML({ ...base, platforms: { stm32: { files: ["a.c"], verified: true, hardware_bound: false } } });
  assert.ok(ok.includes("badge plat ok"));
  const hw = moduleRowHTML({ ...base, platforms: { stm32: { files: ["a.c"], verified: false, hardware_bound: true } } });
  assert.ok(hw.includes("badge plat hw"));
  const un = moduleRowHTML({ ...base, platforms: { stm32: { files: ["a.c"], verified: false, hardware_bound: false } } });
  assert.ok(un.includes("badge plat unverified"));
  const master = moduleRowHTML({ ...base, platforms: { stm32: { files: [], verified: true, hardware_bound: false } } });
  assert.ok(master.includes("内嵌母版"));
});

test("moduleRowHTML 无平台：徽章区为空、行仍完整", () => {
  const out = moduleRowHTML({ slug: "empty", description: "无平台模块", platforms: {} });
  assert.ok(out.includes('<td class="slug">empty</td>'));
  assert.ok(!out.includes("badge"));
});
