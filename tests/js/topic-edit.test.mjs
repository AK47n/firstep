// 赛题编辑弹窗纯函数单测（工单 topic-library-ui/05）：topicEditHTML /
// topicEditValidate / topicEditPayload。extract 括号配平 + deps 注入范式。
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";
import { esc } from "../../src/contest_generator/static/js/fx/core.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const html = readFileSync(resolve(root, "src/contest_generator/static/index.html"), "utf8");

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

const topicEditHTML = extract("topicEditHTML", { esc });
const topicEditValidate = extract("topicEditValidate");
const topicEditPayload = extract("topicEditPayload");

const VOCAB = { "attitude-hold": "航向保持 / 姿态传感器", "gray-track": "8 路灰度传感器驱动" };
const ENTRY = {
  key: "2024H", year: "2024",
  problem_text: "巡线小车 2024H 题面",
  programs: ["C:/Users/luoji/Desktop/2021F/21F"],
  hint_module_groups: ["attitude-hold"],
};

test("编辑表单：只读编号行 + 年份行 + 题面 textarea + 程序逐行 + 保存按钮", () => {
  const out = topicEditHTML(ENTRY, VOCAB);
  assert.ok(out.includes("2024H"));
  assert.ok(out.includes("不可改")); // 身份不变量说明
  assert.ok(out.includes(">2024<")); // 年份单独只读展示
  assert.ok(out.includes("topic-edit-problem")); // 题面 textarea
  assert.ok(out.includes("巡线小车 2024H 题面")); // 原文填入
  assert.ok(out.includes("topic-edit-programs")); // 程序 textarea
  assert.ok(out.includes("C:/Users/luoji/Desktop/2021F/21F")); // 逐行填入
  assert.ok(out.includes('data-topic-save')); // 保存按钮
});

test("功能组勾选：词表组多选 + 当前值勾选态", () => {
  const out = topicEditHTML(ENTRY, VOCAB);
  assert.ok(out.includes('data-topic-group="attitude-hold"'));
  assert.ok(out.includes('data-topic-group="gray-track"'));
  assert.ok(out.includes('checked')); // attitude-hold 已勾
  assert.ok(out.includes("航向保持 / 姿态传感器"));
});

test("功能组：词表外当前值兜底显示并标注悬空（不静默丢弃）", () => {
  const out = topicEditHTML({ ...ENTRY, hint_module_groups: ["ghost-group"] }, VOCAB);
  assert.ok(out.includes('data-topic-group="ghost-group"'));
  assert.ok(out.includes("库内无此组")); // 标注
});

test("功能组：空词表仍显示当前值兜底", () => {
  const out = topicEditHTML({ ...ENTRY, hint_module_groups: ["attitude-hold"] }, {});
  assert.ok(out.includes('data-topic-group="attitude-hold"'));
  assert.ok(out.includes("库内无此组")); // 词表空 = 当前值全部悬空标注（编辑语境=显示兜底）
});

test("编辑表单转义：题面中的 & < > 不破坏结构", () => {
  const out = topicEditHTML({ ...ENTRY, problem_text: "a<b>c&d" }, VOCAB);
  assert.ok(out.includes("a&lt;b&gt;c&amp;d"));
});

test("topicEditValidate：题面非空（与后端同口径轻量前置）", () => {
  assert.equal(topicEditValidate({ problem_text: "题面" }).ok, true);
  assert.equal(topicEditValidate({ problem_text: "  " }).ok, false);
  assert.equal(topicEditValidate({ problem_text: "" }).ok, false);
  assert.ok(topicEditValidate({ problem_text: "" }).message.includes("题面"));
});

test("topicEditPayload：programs 逐行拆分（空行忽略 + trim）+ hint 勾选值", () => {
  const payload = topicEditPayload({
    problem_text: "新题面",
    programs: "  C:/a  \n\nC:/b\n  ",
    hint_module_groups: ["gray-track"],
  });
  assert.equal(payload.problem_text, "新题面");
  assert.deepEqual(payload.programs, ["C:/a", "C:/b"]);
  assert.deepEqual(payload.hint_module_groups, ["gray-track"]);
});

test("topicEditPayload：programs 全空 = 空清单（清空语义）", () => {
  const payload = topicEditPayload({ problem_text: "题面", programs: " \n \n", hint_module_groups: [] });
  assert.deepEqual(payload.programs, []);
  assert.deepEqual(payload.hint_module_groups, []);
});
