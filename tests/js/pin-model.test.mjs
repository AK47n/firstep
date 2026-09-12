// tests/js/pin-model.test.mjs — 引脚判据模型的前端求值纯函数（工单 gen-chain-audit/05）。
//
// 判据单源：模型由后端 `/api/bindings/matrix` 下发（`pin_bindings.build_bindings_matrix`），
// 前端只做两件事——① 命中 `selectable`；② 求值谓词（`constraint` 单条 / `constraints`
// 并列多条，全部成立才可绑）。本文件钉这两件事，
// 以及「模型未到 → 退回类型级、不假拦」的降级口径。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  pinModelEntry, pinModelVerdict, pinSelectableByType, pinModelMissReason,
  pinRoleChannel, pinModelConstraints, pinConstraintHolds, pinPairFollow,
} from "../../src/contest_generator/static/js/fx/pin-model.js";

const MODEL = {
  roles: [
    {
      role: "step_motor.STEP_MOTOR_RST2", type: "gpio_out", default: "PB24",
      selectable: ["PA0", "PB24", "PB6"],
      constraint: { kind: "port", port: "B", reason: "该组走单端口宏" },
    },
    {
      role: "motor.PWMAB_C0", type: "pwm", default: "PA12",
      selectable: ["PA23", "PA12"],
      constraint: {
        kind: "instance", instances: ["TIMA0_C3N", "TIMG0_C1"], pair: "motor.PWMAB_C1",
        reason: "须与 motor.PWMAB_C1 同实例",
      },
    },
    {
      role: "huidu.L1", type: "gpio_in", default: "PA22",
      selectable: ["PA22", "PB6"], constraint: null,
    },
  ],
};

const BOARD = {
  pins: [
    { name: "PA0", kind: "io", capabilities: ["gpio_out", "pwm:TIMA0_C0", "pwm:TIMG8_C1"] },
    { name: "PB24", kind: "io", capabilities: ["gpio_out"] },
    { name: "PB6", kind: "io", capabilities: ["gpio_out", "gpio_in", "pwm:TIMG8_C0"] },
    { name: "PA23", kind: "io", capabilities: ["gpio_out", "pwm:TIMG8_C0", "pwm:TIMG0_C0"] },
    { name: "PA12", kind: "io", capabilities: ["pwm:TIMG0_C0", "pwm:TIMA0_C3"] },
    { name: "PA22", kind: "io", capabilities: ["gpio_in"] },
    { name: "PC13", kind: "gnd", capabilities: ["gpio_out"] },
  ],
};

const pin = (name) => BOARD.pins.find((p) => p.name === name);

test("pinModelEntry：按 <slug>.<role> 取条目；缺模型/缺条目返回 null", () => {
  assert.equal(pinModelEntry(MODEL, "huidu.L1").default, "PA22");
  assert.equal(pinModelEntry(null, "huidu.L1"), null);
  assert.equal(pinModelEntry({ roles: [] }, "huidu.L1"), null);
});

test("selectable 之外的脚一律不可绑（能力层由后端算）", () => {
  // PB6 在 RST2 的 selectable 里但端口 A/B 谓词... 此处先测「不在 selectable」的脚
  assert.equal(pinModelVerdict(MODEL, BOARD, "huidu.L1", pin("PB24")), false);
  // PA0 在 RST2 的 selectable 里，但端口谓词要求 B → 挡
  assert.equal(pinModelVerdict(MODEL, BOARD, "step_motor.STEP_MOTOR_RST2", pin("PA0")), false);
  // PB24 既在 selectable 也满足端口 B → 放行
  assert.equal(pinModelVerdict(MODEL, BOARD, "step_motor.STEP_MOTOR_RST2", pin("PB24")), true);
});

test("port 谓词：非 io 脚不放行（板图上的电源/固定脚）", () => {
  assert.equal(pinModelVerdict(MODEL, BOARD, "huidu.L1", pin("PC13")), false);
});

test("instance 谓词：pwm 按实例**基名**比（互补通道也算）", () => {
  // C0 角色 × PA23（TIMG8_C0 / TIMG0_C0）：基名 {TIMG8,TIMG0} ∩ {TIMA0,TIMG0} = TIMG0 → 放行
  assert.equal(pinModelVerdict(MODEL, BOARD, "motor.PWMAB_C0", pin("PA23")), true);
  // PA12（TIMG0_C0 / TIMA0_C3）：基名 {TIMG0,TIMA0} ∩ {TIMA0,TIMG0} → 放行
  assert.equal(pinModelVerdict(MODEL, BOARD, "motor.PWMAB_C0", pin("PA12")), true);
});

test("pinRoleChannel：从角色键取 pwm 通道尾", () => {
  assert.equal(pinRoleChannel("motor.PWMAB_C0"), "C0");
  assert.equal(pinRoleChannel("step_motor.DCC_100_PWM2_C0"), "C0");
  assert.equal(pinRoleChannel("huidu.L1"), null);
  assert.equal(pinRoleChannel(""), null);
});

test("instance 谓词：pwm 两脚**各自按本脚通道过滤**后取基名比交集", () => {
  // C0 角色 × PA0（TIMA0_C0 / TIMG8_C1）：本脚过滤到 C0 → 基名 TIMA0；
  // 对脚 PWMAB_C1 默认 PA13 的实例 TIMA0_C3N / TIMG0_C1 过滤到 C1 → 基名 TIMG0
  // → 无交集 = 不可绑（后端同款判据；「TIMA0_C3N 算不算同实例」这条判据钉在这里）
  const model = {
    roles: [
      {
        role: "motor.PWMAB_C0", type: "pwm", default: "PA12",
        selectable: ["PA0", "PA23"],
        constraint: {
          kind: "instance", instances: ["TIMA0_C3N", "TIMG0_C1"],
          pair: "motor.PWMAB_C1", reason: "须与 motor.PWMAB_C1 同实例",
        },
      },
      {
        role: "motor.PWMAB_C1", type: "pwm", default: "PA13",
        selectable: ["PA13"],
        constraint: { kind: "instance", instances: ["TIMA0_C3", "TIMG0_C0"], pair: "motor.PWMAB_C0", reason: "" },
      },
    ],
  };
  const board = {
    pins: [
      { name: "PA0", kind: "io", capabilities: ["pwm:TIMA0_C0", "pwm:TIMG8_C1"] },
      { name: "PA23", kind: "io", capabilities: ["pwm:TIMG8_C0", "pwm:TIMG0_C0"] },
      { name: "PA13", kind: "io", capabilities: ["pwm:TIMG0_C1", "pwm:TIMA0_C3N"] },
    ],
  };
  const pinOf = (n) => board.pins.find((p) => p.name === n);
  assert.equal(pinModelVerdict(model, board, "motor.PWMAB_C0", pinOf("PA0")), false);
  assert.equal(pinModelVerdict(model, board, "motor.PWMAB_C0", pinOf("PA23")), true);
  assert.equal(pinModelVerdict(model, board, "motor.PWMAB_C1", pinOf("PA13")), true);
  assert.equal(pinModelVerdict(model, board, "motor.PWMAB_C1", pinOf("PA0")), false);
});

test("instance 谓词：非 pwm 角色按完整实例比（uart/i2c 同口径）", () => {
  const model = {
    roles: [{
      role: "x.TX", type: "uart_tx", default: "PA9", selectable: ["PA9", "PB10"],
      constraint: { kind: "instance", instances: ["UART1"], pair: "x.RX", reason: "同实例" },
    }],
  };
  const board = {
    pins: [
      { name: "PA9", kind: "io", capabilities: ["uart_tx:UART1"] },
      { name: "PB10", kind: "io", capabilities: ["uart_tx:UART3"] },
    ],
  };
  assert.equal(pinModelVerdict(model, board, "x.TX", board.pins[0]), true);
  assert.equal(pinModelVerdict(model, board, "x.TX", board.pins[1]), false);
});

test("constraint=null：selectable 命中即放行（混端口组 / 单角色）", () => {
  assert.equal(pinModelVerdict(MODEL, BOARD, "huidu.L1", pin("PB6")), true);
});

// ---- constraints 数组（多条谓词**并存**，工单 mspm0-slot-conflict/04）------
// 谓词是「并列的独立门禁」而不是「选一条」：`as32.AS32_UART_TX` 既有 uart 对脚
// （instance 谓词），又与 `zigbee_link.ZIGBEE_UART_TX` 默认同 PA26（slot 谓词）。
// 全部成立才可绑；原因给第一条不成立的（与求值的短路顺序一致）。
const BOTH_MODEL = {
  roles: [
    {
      role: "as32.AS32_UART_TX", type: "uart_tx", default: "PA26",
      selectable: ["PA26", "PB2", "PB6"],
      constraint: {
        kind: "instance", instances: ["UART3"], pair: "as32.AS32_UART_RX",
        reason: "须与 as32.AS32_UART_RX 同实例",
      },
      constraints: [
        {
          kind: "instance", instances: ["UART3"], pair: "as32.AS32_UART_RX",
          reason: "须与 as32.AS32_UART_RX 同实例",
        },
        {
          kind: "slot", pin: "PA26", peers: ["zigbee_link.ZIGBEE_UART_TX"],
          reason: "与 zigbee_link.ZIGBEE_UART_TX 共用同一槽位（默认引脚 PA26）",
        },
      ],
    },
  ],
};

const BOTH_BOARD = {
  pins: [
    { name: "PA26", kind: "io", capabilities: ["uart_tx:UART3"] },
    { name: "PB2", kind: "io", capabilities: ["uart_tx:UART3"] },
    { name: "PB6", kind: "io", capabilities: ["uart_tx:UART1"] },
  ],
};
const bothPin = (n) => BOTH_BOARD.pins.find((p) => p.name === n);

test("constraints 数组：**全部**成立才可绑（并行门禁，任一条挡即挡）", () => {
  // PA26：instance ✓ + slot ✓ → 放行
  assert.equal(pinModelVerdict(BOTH_MODEL, BOTH_BOARD, "as32.AS32_UART_TX", bothPin("PA26")), true);
  // PB2：instance ✓（UART3）+ slot ✗（同伴在 PA26）→ 挡（旧单条字段口径会放行）
  assert.equal(pinModelVerdict(BOTH_MODEL, BOTH_BOARD, "as32.AS32_UART_TX", bothPin("PB2")), false);
  // PB6：instance ✗ + slot ✗ → 挡
  assert.equal(pinModelVerdict(BOTH_MODEL, BOTH_BOARD, "as32.AS32_UART_TX", bothPin("PB6")), false);
});

test("constraints 数组：pinModelMissReason 给**第一条**不成立的原因", () => {
  // PB2：第一条（instance）成立、第二条（slot）不成立 → 给 slot 的原因
  assert.equal(
    pinModelMissReason(BOTH_MODEL, BOTH_BOARD, "as32.AS32_UART_TX", bothPin("PB2")),
    "与 zigbee_link.ZIGBEE_UART_TX 共用同一槽位（默认引脚 PA26）",
  );
  // PB6：第一条就不成立 → 给 instance 的原因
  assert.equal(
    pinModelMissReason(BOTH_MODEL, BOTH_BOARD, "as32.AS32_UART_TX", bothPin("PB6")),
    "须与 as32.AS32_UART_RX 同实例",
  );
  assert.equal(
    pinModelMissReason(BOTH_MODEL, BOTH_BOARD, "as32.AS32_UART_TX", bothPin("PA26")),
    "",
  );
});

test("pinModelConstraints：数组优先，否则单条 constraint（读取口径单源）", () => {
  assert.equal(pinModelConstraints(BOTH_MODEL.roles[0]).length, 2);
  assert.equal(pinModelConstraints(MODEL.roles[0]).length, 1);
  assert.equal(pinModelConstraints(SLOT_MODEL.roles[0]).length, 1);
  assert.deepEqual(pinModelConstraints({ constraint: null }), []);
  assert.deepEqual(pinModelConstraints({ constraint: null, constraints: [] }), []);
  assert.deepEqual(pinModelConstraints(null), []);
});

// ---- slot 谓词（工单 mspm0-slot-conflict/02）-----------------------------
// 语义：候选脚必须 == 同槽位同伴**当前有效脚**（后端 `_check_slot_conflicts` /
// `_mspm0_same_slot` 同判据下发）；前端只比引脚名相等，不含任何后端规则。
const SLOT_MODEL = {
  roles: [
    {
      role: "huidu.R3", type: "gpio_in", default: "PB6",
      selectable: ["PA0", "PB6", "PA7"],
      constraint: {
        kind: "slot", pin: "PB6", peers: ["pid.GRAY_D7"],
        reason: "与 pid.GRAY_D7 共用同一槽位（默认引脚 PB6）",
      },
    },
  ],
};

test("slot 谓词：候选脚必须等于同槽位同伴的有效脚", () => {
  // 同伴此刻在 PB6 → 只有 PB6 可绑；PA0/PA7 当场挡（这正是工单 01 那条缝）
  assert.equal(pinModelVerdict(SLOT_MODEL, BOARD, "huidu.R3", pin("PB6")), true);
  assert.equal(pinModelVerdict(SLOT_MODEL, BOARD, "huidu.R3", pin("PA0")), false);
  // 同伴搬到别处 → pin 跟着变（谓词随观测绑定走）
  const moved = {
    roles: [{
      ...SLOT_MODEL.roles[0],
      constraint: { ...SLOT_MODEL.roles[0].constraint, pin: "PA0" },
    }],
  };
  assert.equal(pinModelVerdict(moved, BOARD, "huidu.R3", pin("PA0")), true);
  assert.equal(pinModelVerdict(moved, BOARD, "huidu.R3", pin("PB6")), false);
});

test("slot 谓词：selectable 之外的脚仍先被能力层挡住；无该角色条目降级放行", () => {
  assert.equal(pinModelVerdict(SLOT_MODEL, BOARD, "huidu.R3", pin("PA22")), false);
  // 模型未到 / 无该角色 → 不假拦（降级口径与 port/instance 一致）
  assert.equal(pinModelVerdict(null, BOARD, "huidu.R3", pin("PA0")), true);
  assert.equal(pinModelVerdict(SLOT_MODEL, BOARD, "pid.GRAY_D7", pin("PA0")), true);
});

test("pinModelMissReason：slot 挡住时给后端逐字原因", () => {
  assert.equal(
    pinModelMissReason(SLOT_MODEL, BOARD, "huidu.R3", pin("PA0")),
    "与 pid.GRAY_D7 共用同一槽位（默认引脚 PB6）",
  );
  assert.equal(pinModelMissReason(SLOT_MODEL, BOARD, "huidu.R3", pin("PB6")), "");
});

test("模型未到（null / 无该角色）→ 退回类型级口径：不假拦", () => {
  // 模型缺失 = 判据没到，不参与判定（前端另有 pinListsType 兜菜单第一层）
  assert.equal(pinModelVerdict(null, BOARD, "huidu.L1", pin("PB24")), true);
  assert.equal(pinModelVerdict({ roles: [] }, BOARD, "huidu.L1", pin("PB24")), true);
  assert.equal(pinModelVerdict(null, BOARD, "huidu.L1", pin("PA0")), true);
  // 菜单第一层仍由前端类型过滤把住（不列没该类型 token 的角色）
  assert.equal(pinSelectableByType(pin("PA22"), "gpio_out"), false);
  assert.equal(pinSelectableByType(pin("PA22"), "gpio_in"), true);
});

test("pinSelectableByType：类型 token 命中（旧口径，降级路径用）", () => {
  assert.equal(pinSelectableByType(pin("PA0"), "gpio_out"), true);
  assert.equal(pinSelectableByType(pin("PA0"), "pwm"), true);      // pwm:TIMA0_C0
  assert.equal(pinSelectableByType(pin("PA22"), "gpio_out"), false);
  assert.equal(pinSelectableByType(pin("PA22"), "uart_tx"), false);
});

test("pinModelMissReason：谓词挡住时给后端原文；未挡住/无模型返回空串", () => {
  const reason = pinModelMissReason(MODEL, BOARD, "step_motor.STEP_MOTOR_RST2", pin("PA0"));
  assert.equal(reason, "该组走单端口宏");
  assert.equal(pinModelMissReason(MODEL, BOARD, "step_motor.STEP_MOTOR_RST2", pin("PB24")), "");
  assert.equal(pinModelMissReason(null, BOARD, "step_motor.STEP_MOTOR_RST2", pin("PA0")), "");
  // 不在 selectable 的脚：不是谓词挡的（原因归能力层），返回空串
  assert.equal(pinModelMissReason(MODEL, BOARD, "huidu.L1", pin("PB24")), "");
});

// ---- 成对联动搬（工单 mspm0-slot-conflict/05）-----------------------------
// 后端 `_check_paired_role_instances` 的语义 = 成对角色（uart TX/RX、i2c SCL/SDA、
// pwm C0/C1）两脚**有效实例集交集非空**，看的是整份 bindings，所以「只搬一脚」
// 必 400。补齐的口径：`pinPairFollow` 给「对脚该跟到哪」（确定落点），
// `pinModelVerdict` 把「对脚跟得上」也算成立；两脚由 `ui/generate-pins.js` 的
// `bindRole` 在同一次提交里写（判据本体一字未动）。
const REAL_MSPM0 = JSON.parse(readFileSync(
  new URL("../../src/contest_generator/boards/mspm0-dimx.json", import.meta.url), "utf8",
));
const REAL_STM32 = JSON.parse(readFileSync(
  new URL("../../src/contest_generator/boards/stm32-min-system.json", import.meta.url), "utf8",
));
const realPin = (board, name) => board.pins.find((p) => p.name === name);

test("成对跟随：uart TX 单脚搬必 400 → 模型不给绑（工单 04 记录的交互缺口）", () => {
  // `debug_uart` 默认 TX=PA23 / RX=PA22（UART2），点 TX → PA28（UART0）：
  // 对脚不在观测里 → 跟随只认默认脚 PA22（UART2）→ 两脚无交集 → 挡
  const model = {
    roles: [
      {
        role: "debug_uart.DEBUG_UART_TX", type: "uart_tx", default: "PA23",
        selectable: ["PA23", "PA28"],
        constraint: {
          kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_RX",
          reason: "须与 debug_uart.DEBUG_UART_RX 同实例",
        },
      },
    ],
  };
  assert.equal(
    pinModelVerdict(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", realPin(REAL_MSPM0, "PA28"), {}),
    false,
  );
  assert.equal(
    pinPairFollow(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", realPin(REAL_MSPM0, "PA28"), {}),
    null,
  );
  assert.equal(
    pinModelMissReason(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", realPin(REAL_MSPM0, "PA28"), {}),
    "须与 debug_uart.DEBUG_UART_RX 同实例",
  );
});

test("成对跟随：对脚给得出落点 → 放行，并给出落点（板定义序，优先同实例集）", () => {
  // 对脚在模型里（`selectable` = 全部 uart_rx 脚）：TX 点 PA28（UART0 的 TX 脚）
  // → 对脚须落到 UART0 的 RX 脚（PA1 / PA31），取板定义序首个 = PA1
  const model = {
    roles: [
      {
        role: "debug_uart.DEBUG_UART_TX", type: "uart_tx", default: "PA23",
        selectable: ["PA23", "PA28"],
        constraint: {
          kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_RX",
          reason: "须与 debug_uart.DEBUG_UART_RX 同实例",
        },
      },
      {
        role: "debug_uart.DEBUG_UART_RX", type: "uart_rx", default: "PA22",
        selectable: ["PA22", "PA1", "PA31"],
        constraint: {
          kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_TX",
          reason: "须与 debug_uart.DEBUG_UART_TX 同实例",
        },
      },
    ],
  };
  const tx = realPin(REAL_MSPM0, "PA28");
  assert.equal(pinModelVerdict(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", tx, {}), true);
  assert.equal(pinModelMissReason(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", tx, {}), "");
  assert.deepEqual(
    pinPairFollow(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", tx, {}),
    {
      same: false, mate: "debug_uart.DEBUG_UART_RX",
      from: null, to: "PA1", bound: false,
    },
  );
  // 对脚已绑在 PA31（UART0，与候选脚 PA28 同实例）→ 对脚**原地不动**就成立，
  // 这一步只写本脚（`bindRole` 不写第二个 key）
  assert.deepEqual(
    pinPairFollow(
      model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", tx,
      { "debug_uart.DEBUG_UART_RX": "PA31" },
    ),
    {
      same: true, mate: "debug_uart.DEBUG_UART_RX",
      from: "PA31", to: "PA31", bound: true,
    },
  );
  // 对脚绑在**别的实例**（PA22 = UART2）→ 必须跟到 UART0 的 RX 脚
  assert.deepEqual(
    pinPairFollow(
      model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", tx,
      { "debug_uart.DEBUG_UART_RX": "PA22" },
    ),
    {
      same: false, mate: "debug_uart.DEBUG_UART_RX",
      from: "PA22", to: "PA1", bound: true,
    },
  );
});

test("成对跟随：对脚原地不动就成立 → same（不写第二个 key）", () => {
  const model = {
    roles: [
      {
        role: "debug_uart.DEBUG_UART_TX", type: "uart_tx", default: "PA23",
        selectable: ["PA23", "PA28"],
        constraint: {
          kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_RX",
          reason: "同实例",
        },
      },
      {
        role: "debug_uart.DEBUG_UART_RX", type: "uart_rx", default: "PA22",
        selectable: ["PA22", "PA1", "PA24"],
        constraint: { kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_TX", reason: "" },
      },
    ],
  };
  // 对脚绑定在 PA24（UART2）→ 把 TX 绑到 PA23（UART2）：交集非空，对脚不用动
  const follow = pinPairFollow(
    model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", realPin(REAL_MSPM0, "PA23"),
    { "debug_uart.DEBUG_UART_RX": "PA24" },
  );
  assert.equal(follow.same, true);
  assert.equal(follow.to, "PA24");
  assert.equal(
    pinModelVerdict(
      model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", realPin(REAL_MSPM0, "PA23"),
      { "debug_uart.DEBUG_UART_RX": "PA24" },
    ),
    true,
  );
});

test("成对跟随：对脚落点被别的角色占着 → 换下一只；全被占 → 不放行", () => {
  const model = {
    roles: [
      {
        role: "debug_uart.DEBUG_UART_TX", type: "uart_tx", default: "PA23",
        selectable: ["PA23", "PA28"],
        constraint: { kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_RX", reason: "同实例" },
      },
      {
        role: "debug_uart.DEBUG_UART_RX", type: "uart_rx", default: "PA22",
        selectable: ["PA22", "PA1", "PA31"],
        constraint: { kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_TX", reason: "" },
      },
    ],
  };
  const tx = realPin(REAL_MSPM0, "PA28");
  // PA1 被别的角色占着（不是本次这对）→ 落到下一只 PA31（同样 UART0）
  assert.equal(
    pinPairFollow(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", tx, { "led.LED": "PA1" }).to,
    "PA31",
  );
  // PA1 与 PA31 都被占 → 无落点 → 挡（不制造「搬了 TX 却让 RX 挪不走」的中间态）
  const occupied = { "led.LED": "PA1", "beep.BEEP": "PA31" };
  assert.equal(pinPairFollow(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", tx, occupied), null);
  assert.equal(pinModelVerdict(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", tx, occupied), false);
});

test("成对跟随：对脚自己的**其它**谓词照常求值（槽位/端口组不许被踩）", () => {
  const model = {
    roles: [
      {
        role: "debug_uart.DEBUG_UART_TX", type: "uart_tx", default: "PA23",
        selectable: ["PA23", "PA28"],
        constraint: { kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_RX", reason: "同实例" },
      },
      {
        role: "debug_uart.DEBUG_UART_RX", type: "uart_rx", default: "PA22",
        selectable: ["PA22", "PA1", "PA31"],
        // 对脚还压着一条槽位谓词：只能落在 PA31
        constraints: [
          { kind: "instance", instances: ["UART2"], pair: "debug_uart.DEBUG_UART_TX", reason: "同实例" },
          { kind: "slot", pin: "PA31", peers: ["pid.GRAY_D0"], reason: "与 pid.GRAY_D0 共用同一槽位" },
        ],
      },
    ],
  };
  assert.equal(
    pinPairFollow(model, REAL_MSPM0, "debug_uart.DEBUG_UART_TX", realPin(REAL_MSPM0, "PA28"), {}).to,
    "PA31",
  );
});

test("成对跟随：stm32 三对 uart 脚（每实例只有一对 → 原地即唯一解）", () => {
  // stm32 `debug_uart` 默认 TX=PA2 / RX=PA3（UART_2）；TX 点 PB10（UART_3）
  // → 对脚须落到 PB11
  const model = {
    roles: [
      {
        role: "debug_uart.DEBUG_UART_TX", type: "uart_tx", default: "PA2",
        selectable: ["PA2", "PB10"],
        constraint: { kind: "instance", instances: ["UART_2"], pair: "debug_uart.DEBUG_UART_RX", reason: "同实例" },
      },
      {
        role: "debug_uart.DEBUG_UART_RX", type: "uart_rx", default: "PA3",
        selectable: ["PA3", "PA10", "PB11"],
        constraint: { kind: "instance", instances: ["UART_2"], pair: "debug_uart.DEBUG_UART_TX", reason: "同实例" },
      },
    ],
  };
  const tx = realPin(REAL_STM32, "PB10");
  assert.equal(pinModelVerdict(model, REAL_STM32, "debug_uart.DEBUG_UART_TX", tx, {}), true);
  const follow = pinPairFollow(model, REAL_STM32, "debug_uart.DEBUG_UART_TX", tx, {});
  assert.equal(follow.to, "PB11");
  // 反向：TX 回 PA2 时对脚原地不动（PA3 已在 UART_2）
  const back = pinPairFollow(
    model, REAL_STM32, "debug_uart.DEBUG_UART_TX", realPin(REAL_STM32, "PA2"),
    { "debug_uart.DEBUG_UART_RX": "PA3" },
  );
  assert.equal(back.same, true);
});

test("成对跟随：无对脚 / 非成对角色 / 无模型 → null（不动既有行为）", () => {
  assert.equal(pinPairFollow(MODEL, BOARD, "huidu.L1", pin("PB6"), {}), null);
  assert.equal(pinPairFollow(null, BOARD, "huidu.L1", pin("PB6"), {}), null);
  // 对脚不在模型里（模型只下发了本角色）→ 找不到落点 → 不放行（保守）
  const lone = {
    roles: [{
      role: "x.TX", type: "uart_tx", default: "PA9", selectable: ["PA9", "PB10"],
      constraint: { kind: "instance", instances: ["UART1"], pair: "x.RX", reason: "同实例" },
    }],
  };
  assert.equal(pinPairFollow(lone, BOARD, "x.TX", BOARD.pins[0], {}), null);
  // 既有的实例谓词用例不受影响：非成对场景（对脚条目缺失）照旧按谓词判
  assert.equal(pinModelVerdict(lone, BOARD, "x.TX", BOARD.pins[0], {}), false);
});
