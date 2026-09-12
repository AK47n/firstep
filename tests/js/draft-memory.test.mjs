// draftState / draftSave / draftLoad / draftRestoreMeta 纯函数单测（工单 frontend-es-modules/07）：
// 生成页草稿 localStorage 记忆——存取往返、损坏 JSON 兜底、非法字段裁剪。
// 直接 import fx/draft.js（不再字符串提取）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  draftState, draftSave, draftLoad, draftRestoreMeta,
} from "../../src/contest_generator/static/js/fx/draft.js";

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

test("draftState 组装八字段（含 groupChoices）；slugs 非数组 / 含非字符串被裁剪；outputDir 兜底空串", () => {
  // groupChoices（工单 group-choice-required/01）：{组 id: 成员 slug}——刷新后仍是「我点的」；
  // 形状闸只留非空字符串键值，损坏形态 → {}
  const s = draftState("题面", "2026C", "mspm0", ["led", 42, "beep", null], "int main(){}", "问：x 答：y", "D:\\proj", { "attitude-hold": "imu_uart", bad: 3, "": "x" });
  assert.deepEqual(s, {
    problem: "题面", topicId: "2026C", platform: "mspm0",
    slugs: ["led", "beep"], mainC: "int main(){}", qa: "问：x 答：y", outputDir: "D:\\proj",
    groupChoices: { "attitude-hold": "imu_uart" },
  });
  const empty = draftState(undefined, null, "", null, undefined, "", undefined);
  assert.deepEqual(empty, {
    problem: "", topicId: "", platform: "", slugs: [], mainC: "", qa: "", outputDir: "",
    groupChoices: {},
  });
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

test("draftRestoreMeta 非法字段裁剪：数字→空串、slugs 过滤非字符串、outputDir 白名单", () => {
  const out = draftRestoreMeta({
    problem: 123, topicId: "2026C", platform: "mspm0",
    slugs: ["led", 42, "beep", null], mainC: 3.14, qa: "x", outputDir: 99, extra: "丢弃",
  });
  assert.deepEqual(out, {
    problem: "", topicId: "2026C", platform: "mspm0",
    slugs: ["led", "beep"], mainC: "", qa: "x", outputDir: "",
    groupChoices: {},   // 旧草稿无该字段 → {}（= 未选，仍要求用户点一次）
  });
  const ok = draftRestoreMeta({ mainC: "int main(){}", outputDir: "D:\\proj" });
  assert.deepEqual(ok, {
    problem: "", topicId: "", platform: "", slugs: [], mainC: "int main(){}", qa: "", outputDir: "D:\\proj",
    groupChoices: {},
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
