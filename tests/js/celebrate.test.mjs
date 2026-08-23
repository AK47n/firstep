// attachCelebrate 纯逻辑单测（工单 ui-polish-8/02）：步骤完成庆祝动画的
// 类加/移除契约——animationend 后自清理。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const match = html.match(/function attachCelebrate[\s\S]*?\n\}/);
assert.ok(match, "index.html 中未找到 attachCelebrate 函数体（改名了？）");
const attachCelebrate = new Function("return (" + match[0] + ")")();

function fakeCard() {
  const classes = new Set();
  let handler = null;
  return {
    classes,
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
    },
    addEventListener: (ev, fn) => { if (ev === "animationend") handler = fn; },
    removeEventListener: (ev, fn) => { if (ev === "animationend" && handler === fn) handler = null; },
    fireAnimationEnd: () => { if (handler) handler(); },
    hasHandler: () => handler !== null,
  };
}

test("attachCelebrate 添加 celebrate 类", () => {
  const c = fakeCard();
  attachCelebrate(c);
  assert.ok(c.classes.has("celebrate"));
});

test("animationend 后移除 celebrate 类并解除监听", () => {
  const c = fakeCard();
  attachCelebrate(c);
  c.fireAnimationEnd();
  assert.ok(!c.classes.has("celebrate"));
  assert.ok(!c.hasHandler());
});

test("重复 animationend 不再有监听（只清一次）", () => {
  const c = fakeCard();
  attachCelebrate(c);
  c.fireAnimationEnd();
  c.fireAnimationEnd();  // handler 已空，无异常
  assert.ok(!c.classes.has("celebrate"));
});

test("空对象 / 缺 classList 安全返回", () => {
  attachCelebrate(null);
  attachCelebrate(undefined);
  attachCelebrate({});
});

test("无 addEventListener 的伪对象也能加类（动画清理走不到）", () => {
  const classes = new Set();
  attachCelebrate({ classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c) } });
  assert.ok(classes.has("celebrate"));
});
