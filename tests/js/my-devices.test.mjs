// my-devices.test.mjs — 「我的器件」（库外件）的表单纯函数（工单 hwcheck-unknown-device/02）。
//
// 判据重点：
// ① **地址双向显示**——7 位值进，7 位 + 8 位读 / 写形式一起出（手册里 0x68 与
//    0xD0 两种写法都要能对上，这是填错地址最常见的一处坑）；
// ② 表单校验必须与后端**同一套规则**（`mine_` 前缀 + slug 文法、7 位地址区间、
//    expect 必须与 register 同行）——前端只是"别让用户白跑一趟"，判据本体在服务端；
// ③ 载荷形状 = 服务端要的那个 `{device: {...}}`（空的可选字段发 null，不是空串）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  MY_DEVICE_ID_PREFIX,
  MY_DEVICE_BUS_OPTIONS,
  myDeviceSlugFromName,
  myDeviceFormBlank,
  myDeviceFormFromPayload,
  myDeviceAddressForms,
  myDeviceFormCheck,
  myDevicePayload,
  myDeviceRowHTML,
  myDeviceListHTML,
  myDeviceEmptyHTML,
  myDeviceFormHTML,
  myDeviceAddressPreviewHTML,
  MY_DEVICE_ADDRESS_MIN,
  MY_DEVICE_ADDRESS_MAX,
} from "../../src/contest_generator/static/js/fx/my-devices.js";

const PAYLOAD = {
  id: "mine_gyro",
  name: "卖家给的六轴模块",
  bus: "i2c",
  bus_label: "I2C",
  address: 0x68,
  address_forms: { address7: "0x68", read8: "0xD1", write8: "0xD0" },
  register: 0x75,
  expect: 0x68,
  echo_only: false,
  notes: "卖家页写的 WHO_AM_I",
  created_at: "2026-09-22 16:40:05",
  updated_at: "2026-09-22 16:40:05",
};

// ---------------------------------------------------------------------------
// ① 地址双向显示
// ---------------------------------------------------------------------------

test("7 位地址派生 8 位读 / 写形式（0x68 → 读 0xD1 / 写 0xD0）", () => {
  assert.deepEqual(myDeviceAddressForms(0x68), {
    address7: "0x68", read8: "0xD1", write8: "0xD0",
  });
  assert.deepEqual(myDeviceAddressForms(0x76), {
    address7: "0x76", read8: "0xED", write8: "0xEC",
  });
  assert.deepEqual(myDeviceAddressForms("104"), {
    address7: "0x68", read8: "0xD1", write8: "0xD0",
  }, "表单里是字符串，解析成整数再派生");
  assert.deepEqual(myDeviceAddressForms(0x08).write8, "0x10");
  assert.deepEqual(myDeviceAddressForms(0x77).read8, "0xEF");
});

test("地址空 / 越界 / 不是数 → 三个空串（不编一个 0x00 出来）", () => {
  for (const bad of [null, undefined, "", "  ", "abc"]) {
    assert.deepEqual(myDeviceAddressForms(bad), {
      address7: "", read8: "", write8: "",
    }, String(bad));
  }
  assert.deepEqual(myDeviceAddressForms(0x07).address7, "", "0x07 越界（保留段）");
  assert.deepEqual(myDeviceAddressForms(0x78).address7, "", "0x78 越界（保留段）");
  assert.deepEqual(myDeviceAddressForms(0xD0).address7, "", "手册里的 8 位写法不该被当 7 位用");
});

test("地址预览同时说出 7 位与两种 8 位写法（填错地址的坑就在这儿）", () => {
  const html = myDeviceAddressPreviewHTML(0x68);
  assert.ok(html.includes("0x68"));
  assert.ok(html.includes("0xD0"), "写方向 8 位");
  assert.ok(html.includes("0xD1"), "读方向 8 位");
  assert.ok(/7\s*位/.test(html));
});

test("非 I2C 总线不显示地址预览（这一类压根没有地址）", () => {
  assert.equal(myDeviceAddressPreviewHTML(0x68, "spi"), "");
  assert.ok(myDeviceAddressPreviewHTML(0x68, "i2c").includes("0x68"));
});

test("地址区间常量与后端一致（7 位：0x08–0x77）", () => {
  assert.equal(MY_DEVICE_ADDRESS_MIN, 0x08);
  assert.equal(MY_DEVICE_ADDRESS_MAX, 0x77);
});

// ---------------------------------------------------------------------------
// ② 表单校验（与后端同一套规则）
// ---------------------------------------------------------------------------

test("空白表单不能提交（缺 id / 名称 / 地址）", () => {
  const error = myDeviceFormCheck(myDeviceFormBlank(), []);
  assert.ok(error, "空表单应报错");
  assert.ok(error.includes("id"));
});

test("合法表单通过校验（真库 slug 集里没有同名）", () => {
  const form = myDeviceFormFromPayload(PAYLOAD);
  assert.equal(myDeviceFormCheck(form, ["oled", "led", "i2c_probe"]), "");
});

test("id 必须是 mine_ 前缀 + slug 文法（与后端同规则）", () => {
  for (const bad of ["gyro", "mine gyro", "mine_", "mine/../evil", "Mine_gyro", "mine_陀螺仪"]) {
    const error = myDeviceFormCheck({ ...myDeviceFormBlank(), id: bad, name: "x", address: "0x68" }, []);
    assert.ok(error, `${bad} 应被拒`);
    assert.ok(error.includes("mine_"), `${bad} → ${error}`);
  }
  assert.equal(MY_DEVICE_ID_PREFIX, "mine_");
  for (const ok of ["mine_gyro", "mine_a", "mine_gyro-2", "mine_1"]) {
    assert.equal(
      myDeviceFormCheck({ ...myDeviceFormBlank(), id: ok, name: "x", address: "0x68" }, []),
      "", ok,
    );
  }
});

test("id 撞库内 slug / 撞已有自建件 → 提交前就拦住（同一句话）", () => {
  const form = { ...myDeviceFormBlank(), id: "mine_oled", name: "x", address: "0x68" };
  const clash = myDeviceFormCheck(form, ["mine_oled"]);
  assert.ok(clash.includes("mine_oled"));
  assert.ok(clash.includes("改名"));
  assert.equal(myDeviceFormCheck(form, ["oled"]), "", "库里没有 mine_oled 就不算撞");
  const dup = myDeviceFormCheck(form, [], ["mine_oled"]);
  assert.ok(dup.includes("已经有一件"), dup);
});

test("编辑自己那一件时不算撞已有件（否则「保存这件」永远灰着，编辑功能整个用不了）", () => {
  // 本单浏览器验收当场抓到的 bug：改一件已有器件的名字时，它的 id 必然出现在
  // `existingIds` 里——不把"正在编辑的那一件"排除掉，保存按钮就一直是灰的。
  const form = { ...myDeviceFormBlank(), id: "mine_gyro", name: "改过的名字", address: "0x68" };
  const own = ["mine_gyro", "mine_other"];
  assert.ok(myDeviceFormCheck(form, [], own).includes("已经有一件"),
    "新建时同名照旧拦住（那条判据不许被这条修没）");
  assert.equal(myDeviceFormCheck(form, [], own, "mine_gyro"), "",
    "编辑自己那件 = 同名覆盖它，这是编辑想要的语义");
  // 编辑时改成**别人**的 id：仍然拦住（别把两件合成一件）
  const moved = { ...form, id: "mine_other" };
  assert.ok(myDeviceFormCheck(moved, [], own, "mine_gyro").includes("已经有一件"),
    "编辑时改成别人的 id 仍要拦");
  // 编辑时撞库内 slug：照旧拦住
  assert.ok(myDeviceFormCheck({ ...form, id: "mine_库内" }, [], own, "mine_gyro"));
});

test("7 位地址区间与 expect-without-register 在表单侧也拦（不白跑一趟）", () => {
  const base = { ...myDeviceFormBlank(), id: "mine_x", name: "x" };
  assert.ok(myDeviceFormCheck({ ...base, address: "0xD0" }, []).includes("7 位"));
  assert.ok(myDeviceFormCheck({ ...base, address: "0x07" }, []).includes("7 位"));
  assert.ok(myDeviceFormCheck({ ...base, address: "0x78" }, []).includes("7 位"));
  assert.equal(myDeviceFormCheck({ ...base, address: "0x77" }, []), "");
  const noAddr = myDeviceFormCheck({ ...base, address: "" }, []);
  assert.ok(noAddr.includes("地址"));
  const expectOnly = myDeviceFormCheck(
    { ...base, address: "0x68", expect: "0x58" }, []);
  assert.ok(expectOnly.includes("寄存器"), expectOnly);
});

test("非 i2c 不要求地址，但填了地址就报错（地址是 I2C 的事实）", () => {
  const base = { ...myDeviceFormBlank(), id: "mine_x", name: "x", bus: "spi" };
  assert.equal(myDeviceFormCheck(base, []), "");
  const withAddr = myDeviceFormCheck({ ...base, address: "0x68" }, []);
  assert.ok(withAddr.includes("i2c"), withAddr);
});

test("总线词表与后端一致（含 other），并有中文展示名", () => {
  assert.deepEqual(
    MY_DEVICE_BUS_OPTIONS.map((o) => o.value),
    ["i2c", "spi", "uart", "onewire", "analog", "gpio", "other"],
  );
  for (const option of MY_DEVICE_BUS_OPTIONS) {
    assert.ok(option.label, `${option.value} 应有展示名`);
  }
});

// ---------------------------------------------------------------------------
// ③ 载荷形状
// ---------------------------------------------------------------------------

test("myDevicePayload：只发服务端要的字段，空可选字段发 null", () => {
  const payload = myDevicePayload(myDeviceFormFromPayload(PAYLOAD));
  assert.deepEqual(payload, {
    device: {
      id: "mine_gyro",
      name: "卖家给的六轴模块",
      bus: "i2c",
      address: 104,
      register: 117,
      expect: 104,
      notes: "卖家页写的 WHO_AM_I",
    },
  });
  const blank = myDevicePayload({ ...myDeviceFormBlank(), id: "mine_x", name: "n", address: "0x68" });
  assert.equal(blank.device.register, null);
  assert.equal(blank.device.expect, null);
  assert.equal(blank.device.notes, "");
  assert.equal(blank.device.address, 0x68);
});

test("myDeviceFormFromPayload：服务端事实 → 表单（地址回填成 7 位十六进制）", () => {
  const form = myDeviceFormFromPayload(PAYLOAD);
  assert.equal(form.id, "mine_gyro");
  assert.equal(form.address, "0x68");
  assert.equal(form.register, "0x75");
  assert.equal(form.expect, "0x68");
  assert.equal(form.bus, "i2c");
  const spi = myDeviceFormFromPayload({ ...PAYLOAD, bus: "spi", address: null, register: null, expect: null });
  assert.equal(spi.address, "");
  assert.equal(spi.register, "");
  assert.equal(spi.expect, "");
});

test("myDeviceSlugFromName：中文名派生不出合法 slug 时给一个能用的 id", () => {
  assert.equal(myDeviceSlugFromName("BH1750 光照模块"), "mine_bh1750");
  assert.equal(myDeviceSlugFromName("My Gyro!"), "mine_my_gyro");
  assert.equal(myDeviceSlugFromName("卖家给的六轴模块"), "mine_device");
  assert.equal(myDeviceSlugFromName(""), "mine_device");
  assert.equal(myDeviceSlugFromName("9轴"), "mine_9");
  assert.ok(myDeviceSlugFromName("x".repeat(80)).length <= 40);
});

// ---------------------------------------------------------------------------
// ④ 渲染
// ---------------------------------------------------------------------------

test("列表行：名称 + 地址三种写法 + 总线 + 编辑 / 删除按钮", () => {
  const html = myDeviceRowHTML(PAYLOAD);
  assert.ok(html.includes("卖家给的六轴模块"));
  assert.ok(html.includes("0x68") && html.includes("0xD0"));
  assert.ok(html.includes('data-my-device-edit="mine_gyro"'));
  assert.ok(html.includes('data-my-device-del="mine_gyro"'));
  assert.ok(html.includes("I2C"));
});

test("列表行：加选按钮两态（没选上 = 「加进这次检测」；选上 = 「已在这次检测里」）", () => {
  // 工单验收第 6 条「能选」的渲染面：两态必须**看得出区别**（按钮文案 + 行上的
  // picked 标记），否则学生不知道这件到底进没进这一趟。
  const off = myDeviceRowHTML(PAYLOAD, false);
  assert.ok(off.includes('data-my-device-pick="mine_gyro"'), off);
  assert.ok(off.includes("加进这次检测"), off);
  assert.ok(!off.includes("hwcheck-my-device picked"), off);
  const on = myDeviceRowHTML(PAYLOAD, true);
  assert.ok(on.includes('data-my-device-pick="mine_gyro"'), on);
  assert.ok(on.includes("已在这次检测里"), on);
  assert.ok(on.includes("hwcheck-my-device picked"), on);
});

test("myDeviceListHTML：选中集按 id 传下去（选中态由 state 决定，不由渲染顺序猜）", () => {
  const other = { ...PAYLOAD, id: "mine_other", name: "另一件" };
  const html = myDeviceListHTML([PAYLOAD, other], ["mine_other"]);
  const firstRow = html.slice(0, html.indexOf("mine_other"));
  assert.ok(firstRow.includes("加进这次检测"), "没选的那件应是「加进」：" + firstRow);
  assert.ok(html.slice(html.indexOf("mine_other")).includes("已在这次检测里"), html);
  assert.ok(myDeviceListHTML([PAYLOAD], null).includes("加进这次检测"), "选中集缺省 = 都没选");
});

test("空态那句话要说清怎么把件加进这一趟（不然「能选」没人找得到）", () => {
  assert.ok(myDeviceEmptyHTML().includes("加进这次检测"), myDeviceEmptyHTML());
});

test("非 I2C 的行：标明这一版不出探测程序（如实说，不假装）", () => {
  const html = myDeviceRowHTML({
    ...PAYLOAD, bus: "spi", bus_label: "SPI", address: null,
    address_forms: { address7: "", read8: "", write8: "" },
    register: null, expect: null, notes: "",
  });
  assert.ok(html.includes("只对 I2C 器件生成探测程序"), html);
  assert.ok(html.includes("不假装测过"), html);
  assert.ok(!html.includes("0x68"), "非 I2C 的行不该出现地址");
  assert.ok(!html.includes("身份寄存器"), "没填寄存器就不该印这一行");
});

test("空列表给一句人话（不是空白，也不是错误）", () => {
  assert.ok(myDeviceListHTML([]).includes("还没有"));
  assert.equal(myDeviceListHTML([]), myDeviceEmptyHTML());
  assert.ok(myDeviceListHTML([PAYLOAD]).includes("mine_gyro"));
});

test("表单：字段齐全 + 总线下拉来自词表 + 保存 / 取消按钮", () => {
  const form = { ...myDeviceFormBlank(), id: "mine_x", name: "n" };
  const html = myDeviceFormHTML(form, "");
  for (const field of ["id", "name", "bus", "address", "register", "expect", "notes"]) {
    assert.ok(html.includes(`data-my-device-field="${field}"`), field);
  }
  assert.ok(html.includes('data-my-device-save'));
  assert.ok(html.includes('data-my-device-cancel'));
  assert.ok(html.includes(">I2C<"), "总线下拉要有中文展示名");
  assert.ok(!html.includes("disabled"), "空白表单的 id/名称还没填，此时不该说校验不过");
  const blocked = myDeviceFormHTML(form, myDeviceFormCheck(myDeviceFormBlank(), []));
  assert.ok(blocked.includes("disabled"), "校验不过时保存按钮置灰（点了没反应最难查）");
});

test("表单：值全部走转义（用户填的东西进 innerHTML）", () => {
  const html = myDeviceFormHTML(
    { ...myDeviceFormBlank(), id: "mine_x", name: '<img src=x onerror="alert(1)">' }, "");
  assert.ok(!html.includes("<img"), "名称必须转义");
  assert.ok(html.includes("&lt;img"));
});

test("表单：校验不过时把理由印在按钮旁边（不是静默置灰）", () => {
  const html = myDeviceFormHTML(myDeviceFormBlank(), "请填地址（必填）");
  assert.ok(html.includes("请填地址"));
});

test("表单 HTML 里带上地址预览容器（ui 侧边打字边更新它）", () => {
  const html = myDeviceFormHTML({ ...myDeviceFormBlank(), id: "mine_x", name: "n" }, "");
  assert.ok(html.includes("data-my-device-address-preview"), "预览容器要有稳定的选择器");
});

// ---------------------------------------------------------------------------
// ⑤ 前端源码与后端规则同源（跨语言镜像守卫）
// ---------------------------------------------------------------------------

test("总线词表与后端 BUS_VOCABULARY 逐字一致（读真源码对账）", () => {
  const py = readFileSync(
    new URL("../../src/contest_generator/my_devices.py", import.meta.url), "utf8");
  const match = py.match(/^BUS_VOCABULARY = \(([\s\S]*?)^\)/m);
  assert.ok(match, "my_devices.py 里应有 BUS_VOCABULARY 字面量");
  // ⚠ 词条里有 `i2c` 这种**带数字**的：只认 [a-z] 会把第一条悄悄漏掉（本单实测踩到）
  const pyWords = [...match[1].matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]);
  assert.equal(pyWords.length, 7, `解析出的词表条目数不对：${pyWords}`);
  assert.deepEqual(MY_DEVICE_BUS_OPTIONS.map((o) => o.value), pyWords);
});

test("id 前缀与地址区间与后端逐字一致（读真源码对账）", () => {
  const py = readFileSync(
    new URL("../../src/contest_generator/my_devices.py", import.meta.url), "utf8");
  const prefix = py.match(/DEVICE_ID_PREFIX\s*=\s*"([^"]+)"/);
  assert.ok(prefix);
  assert.equal(MY_DEVICE_ID_PREFIX, prefix[1]);
  const lo = py.match(/ADDRESS7_MIN\s*=\s*(0x[0-9A-Fa-f]+)/);
  const hi = py.match(/ADDRESS7_MAX\s*=\s*(0x[0-9A-Fa-f]+)/);
  assert.ok(lo && hi);
  assert.equal(MY_DEVICE_ADDRESS_MIN, Number(lo[1]));
  assert.equal(MY_DEVICE_ADDRESS_MAX, Number(hi[1]));
});
