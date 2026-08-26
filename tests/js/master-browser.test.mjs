// 母版库浏览区纯函数组（工单 master-library-ui/03）：表格增强行 + 删除确认弹窗。
// extract 范式与 topic-browser.test.mjs / pdf-library.test.mjs 同款
// （括号配平 + deps 注入兄弟函数依赖；函数体不得引用模块级常量）。
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const html = readFileSync(resolve(root, "src/contest_generator/static/index.html"), "utf8");

// 括号配平提取（同 topic-browser.test.mjs 范式）；deps = 注入的兄弟函数依赖。
function extract(name, deps) {
  const start = html.indexOf("function " + name);
  assert.ok(start !== -1, "index.html 中未找到 " + name + " 函数体（改名了？）");
  let i = html.indexOf("(", start);
  assert.ok(i !== -1, name + " 函数缺少参数表");
  let pdepth = 0;
  for (; i < html.length; i++) {
    if (html[i] === "(") pdepth++;
    else if (html[i] === ")") { pdepth--; if (pdepth === 0) break; }
  }
  const open = html.indexOf("{", i);
  assert.ok(open !== -1, name + " 函数体缺少左花括号");
  let depth = 0;
  for (let j = open; j < html.length; j++) {
    if (html[j] === "{") depth++;
    else if (html[j] === "}") {
      depth--;
      if (depth === 0) {
        const fnSrc = html.slice(start, j + 1);
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
const masterTableRowHTML = extract("masterTableRowHTML", { esc });
const masterDeleteConfirmHTML = extract("masterDeleteConfirmHTML", { esc });

// 测试母本：与 /api/masters 列表响应同形状（platform_label / key_files 自工单 01）
const MASTER_STM32 = {
  platform: "stm32",
  sources: ["2026C", "21F"],
  warnings: [],
  platform_label: "STM32F103C8T6 最小系统板 · Keil5",
  key_files: [
    { path: "main.c", label: "模板 main.c", size_bytes: 909, exists: true },
    { path: "user/Project.uvprojx", label: "Keil 工程配置", size_bytes: 17606, exists: true },
  ],
};

test("masterTableRowHTML：平台展示名 + 来源 join(、) + 警告 join(；) + 双按钮", () => {
  const out = masterTableRowHTML(MASTER_STM32);
  assert.ok(out.includes("STM32F103C8T6 最小系统板 · Keil5"));
  assert.ok(out.includes("2026C、21F"));
  assert.ok(out.includes("—")); // 警告空 → 占位
  assert.ok(out.includes('data-master-detail="stm32"'));
  assert.ok(out.includes('data-master-del="stm32"'));
  assert.ok(out.includes("详情"));
  assert.ok(out.includes("删除"));
});

test("masterTableRowHTML：platform_label 缺失回退 platform；转义 HTML", () => {
  const out = masterTableRowHTML({ ...MASTER_STM32, platform_label: undefined });
  assert.ok(out.includes('class="slug">stm32</td>'));

  const evil = masterTableRowHTML({ ...MASTER_STM32, platform_label: '<img src=x>' });
  assert.ok(evil.includes("&lt;img src=x&gt;"));
  assert.ok(!evil.includes("<img src=x>"));
});

test("masterDeleteConfirmHTML：平台展示名 + 平台标识 + 不可恢复警告 + 双钮", () => {
  const out = masterDeleteConfirmHTML(MASTER_STM32);
  assert.ok(out.includes("STM32F103C8T6 最小系统板 · Keil5"));
  assert.ok(out.includes('class="mono">stm32'));
  assert.ok(out.includes("不可恢复"));
  assert.ok(out.includes("2026C、21F"));
  assert.ok(out.includes("2 项预览清单")); // key_files 条数
  assert.ok(out.includes('data-master-del-confirm'));
  assert.ok(out.includes("确认删除"));
  assert.ok(out.includes('data-master-del-cancel'));
  assert.ok(out.includes("取消"));
});

test("masterDeleteConfirmHTML：无 key_files 字段兜底 0 项 + 转义", () => {
  const out = masterDeleteConfirmHTML({ ...MASTER_STM32, key_files: undefined });
  assert.ok(out.includes("0 项预览清单"));

  const evil = masterDeleteConfirmHTML({ ...MASTER_STM32, platform_label: "<b>x</b>" });
  assert.ok(evil.includes("&lt;b&gt;x&lt;/b&gt;"));
  assert.ok(!evil.includes("<b>x</b>"));
});
