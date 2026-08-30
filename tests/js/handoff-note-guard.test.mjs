// tests/js/handoff-note-guard.test.mjs — Y4 交接提示词说明结构护栏
// （工单 newcomer-glossary/03）：静态断言第 12 步卡说明文案存在且位于
// #btn-handoff 上方、「去任务推进」按钮存在、ui/handoff.js 的 initHandoffNote
// 接线、ui/revise-tabs.js 导出 switchReviseTab、index.html 成对接入。
// 工单 beginner-gap-closure/02 扩展：「去任务推进」跳转单源迁至 ui/goto-tasks.js
// （第 9 步生成结果区与第 12 步交接卡共用），守卫锁住「一处定义、两处使用」。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const handoff = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/handoff.js", import.meta.url),
  "utf8"
);
const reviseTabs = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/revise-tabs.js", import.meta.url),
  "utf8"
);

/** goto-tasks.js 尚不存在时返回空串——red 态断言失败而非读文件抛错。 */
function gotoTasksSrc() {
  try {
    return readFileSync(
      new URL("../../src/contest_generator/static/js/ui/goto-tasks.js", import.meta.url),
      "utf8"
    );
  } catch {
    return "";
  }
}

test("第 12 步卡含 handoff-note 说明（含「一般」与「外部 AI」）", () => {
  const m = html.match(/<p class="handoff-note">([^<]+)<\/p>/);
  assert.ok(m, "缺 handoff-note");
  assert.ok(m[1].includes("一般"), "文案缺「一般」");
  assert.ok(m[1].includes("外部 AI"), "文案缺「外部 AI」");
});

test("「去任务推进」按钮存在且在 handoff-note 与 #btn-handoff 之间", () => {
  const noteAt = html.indexOf('class="handoff-note"');
  const goAt = html.indexOf('id="btn-goto-tasks"');
  const handoffAt = html.indexOf('id="btn-handoff"');
  assert.ok(noteAt >= 0 && goAt > noteAt && handoffAt > goAt,
    "顺序应为 handoff-note → btn-goto-tasks → btn-handoff");
});

test("ui/handoff.js 不再定义 goTaskProgress，改为从 goto-tasks.js 导入（单源）", () => {
  assert.match(handoff, /import \{ goTaskProgress \} from "\.\/goto-tasks\.js"/);
  assert.ok(!/export function goTaskProgress/.test(handoff), "handoff.js 不应再定义 goTaskProgress");
  assert.match(handoff, /export function initHandoffNote\(\)/);
});

test("ui/revise-tabs.js 仍导出 switchReviseTab（既有事实，防改名）", () => {
  assert.match(reviseTabs, /export function switchReviseTab\(key, opts\)/);
});

test("ui/goto-tasks.js 单源定义 goTaskProgress（滚动第 11 步 + 复用 switchReviseTab + 自动加载上下文）", () => {
  const g = gotoTasksSrc();
  assert.match(g, /export async function goTaskProgress\(\)/);
  assert.match(g, /import \{ \$ \} from "\/js\/app\.js"/);
  assert.match(g, /import \{ switchReviseTab \} from "\/js\/ui\/revise-tabs\.js"/);
  assert.match(g, /switchReviseTab\("tasks", \{ user: true \}\)/);
  assert.match(g, /card-revise/);
  assert.match(g, /reviseLoad/);   // ux-polish-02/04：自动加载上下文（主路径断点修复）
});

test("生成结果区「去任务推进」入口：按钮存在（compile-banner 之后）且文案一致", () => {
  const bannerAt = html.indexOf('id="compile-banner"');
  const btnAt = html.indexOf('id="btn-goto-tasks-result"');
  assert.ok(bannerAt >= 0 && btnAt > bannerAt, "结果区按钮应在编译横幅之后");
  const m = html.match(/id="btn-goto-tasks-result"[^>]*>([^<]+)</);
  assert.ok(m && m[1].includes("去任务推进"), "结果区按钮文案应含「去任务推进」");
});

test("生成结果区按钮接线：generate-core.js import goTaskProgress 并绑定", () => {
  const core = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/generate-core.js", import.meta.url),
    "utf8"
  );
  assert.match(core, /import \{ goTaskProgress \} from "\/js\/ui\/goto-tasks\.js"/);
  assert.match(core, /btn-goto-tasks-result/);
  assert.match(core, /addEventListener\("click", goTaskProgress\)/);
});

test("index.html 成对接入：import + initHandoffNote() 调用", () => {
  assert.match(html, /import \{ initHandoffNote \} from "\/js\/ui\/handoff\.js"/);
  assert.match(html, /initHandoffNote\(\);/);
});
