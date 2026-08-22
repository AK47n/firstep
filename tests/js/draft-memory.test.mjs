// draftState / draftSave / draftLoad / draftRestoreMeta 纯函数单测（工单 ui-polish-3/01）：
// 生成页草稿 localStorage 记忆——存取往返、损坏 JSON 兜底、非法字段裁剪。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

function extract(name) {
  const match = html.match(new RegExp("function " + name + "[\\s\\S]*?\\n\\}"));
  assert.ok(match, "index.html 中未找到 " + name + " 函数体（改名了？）");
  return new Function("return (" + match[0] + ")")();
}

const draftState = extract("draftState");
const draftSave = extract("draftSave");
const draftLoad = extract("draftLoad");
const draftRestoreMeta = extract("draftRestoreMeta");

// 假 storage：内存 Map，可模拟抛错
function fakeStorage(seed, { throwOnGet = false } = {}) {
  const map = new Map(Object.entries(seed || {}));
  return {
    setItem: (k, v) => map.set(k, String(v)),
    getItem: (k) => { if (throwOnGet) throw new Error("denied"); return map.has(k) ? map.get(k) : null; },
    removeItem: (k) => map.delete(k),
    _map: map,
  };
}

test("draftState 组装六字段；slugs 非数组 / 含非字符串被裁剪", () => {
  const s = draftState("题面", "2026C", "mspm0", ["led", 42, "beep", null], "int main(){}", "问：x 答：y");
  assert.deepEqual(s, {
    problem: "题面", topicId: "2026C", platform: "mspm0",
    slugs: ["led", "beep"], mainC: "int main(){}", qa: "问：x 答：y",
  });
  const empty = draftState(undefined, null, "", null, undefined, "");
  assert.deepEqual(empty, { problem: "", topicId: "", platform: "", slugs: [], mainC: "", qa: "" });
});

test("draftSave + draftLoad 往返一致", () => {
  const st = fakeStorage();
  const state = draftState("题面A", "2026C", "mspm0", ["led", "beep"], "int main(){}", "Q&A");
  assert.equal(draftSave(st, state), true);
  assert.deepEqual(draftLoad(st), state);
});

test("draftLoad 空存储返回 null", () => {
  assert.equal(draftLoad(fakeStorage()), null);
});

test("draftLoad 损坏 JSON 返回 null（不抛错）", () => {
  const st = fakeStorage({ "firstep.draft.v1": "{oops not json" });
  assert.equal(draftLoad(st), null);
});

test("draftLoad storage 抛错（隐私模式禁用）返回 null", () => {
  const st = fakeStorage({}, { throwOnGet: true });
  assert.equal(draftLoad(st), null);
});

test("draftRestoreMeta 非法字段裁剪：数字→空串、slugs 过滤非字符串", () => {
  const out = draftRestoreMeta({
    problem: 123, topicId: "2026C", platform: "mspm0",
    slugs: ["led", 42, "beep", null], mainC: 3.14, qa: "x", extra: "丢弃",
  });
  assert.deepEqual(out, {
    problem: "", topicId: "2026C", platform: "mspm0",
    slugs: ["led", "beep"], mainC: "", qa: "x",
  });
});

test("draftRestoreMeta 非对象（null / 数组 / 字符串）返回 null", () => {
  assert.equal(draftRestoreMeta(null), null);
  assert.equal(draftRestoreMeta("str"), null);
  assert.equal(draftRestoreMeta([1, 2]), null);
  assert.equal(draftRestoreMeta(undefined), null);
});

test("draftSave storage.setItem 抛错返回 false（不抛错）", () => {
  const st = fakeStorage();
  st.setItem = () => { throw new Error("quota"); };
  assert.equal(draftSave(st, draftState("x", "", "", [], "", "")), false);
});
