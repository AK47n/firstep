// 同脚多角色 共享/冲突 判据纯函数单测（工单 pin-share-rule/01）：与后端
// pin_bindings._shared_groups 同口径——同一 I2C 总线 / 同一 UART 实例 /
// 同一 syscfg 器件实例 = 合法共享；其余同脚 = 物理冲突。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import { pinRoleResourceKeys, pinShareClass } from "../../src/contest_generator/static/js/fx/generate.js";

const BOARD = {
  pins: [
    { name: "PA9", capabilities: ["gpio_out", "gpio_in", "uart_tx:UART_1", "uart_rx:UART_2"] },
    { name: "PB10", capabilities: ["gpio_out", "gpio_in", "uart_tx:UART_3", "uart_rx:UART_3"] },
    { name: "PA1", capabilities: ["gpio_out", "gpio_in", "i2c_scl:I2C0", "i2c_sda:I2C0", "pwm:TIMA0_C1"] },
    { name: "PB12", capabilities: ["gpio_out", "gpio_in", "adc:ADC_Channel_2"] },
    { name: "PA22", capabilities: ["gpio_out", "gpio_in", "uart_rx:UART_2"] },
  ],
};
const INSTANCE_MAP = {
  huidu: ["HUIDU"],
  pid: ["HUIDU", "MOTOR_PID"],
  config: [],
  key: ["KEY"],
};
const role = (slug, id, type) => ({ key: `${slug}.${id}`, slug, decl: { id, type } });

test("I2C 总线多挂（MPU6050 + 磁力计同挂 SCL/SDA）→ 合法共享", () => {
  const cls = pinShareClass(
    [role("ml_mpu6050", "I2C_0_SCL", "i2c_scl"), role("hmc5883l", "MAG_SCL", "i2c_scl")],
    "PA1", BOARD, INSTANCE_MAP,
  );
  assert.equal(cls.kind, "share");
  assert.match(cls.reason, /I2C 总线共享/);
});

test("同一 UART 实例（zigbee 家族共 UART_3）→ 合法共享", () => {
  const cls = pinShareClass(
    [role("zigbee_uart", "ZIGBEE_UART_TX", "uart_tx"), role("zigbee_link", "ZIGBEE_UART_TX", "uart_tx")],
    "PB10", BOARD, INSTANCE_MAP,
  );
  assert.equal(cls.kind, "share");
  assert.match(cls.reason, /串口链路/);
});

test("不同 UART 实例同脚 → 冲突", () => {
  const cls = pinShareClass(
    [role("digi", "DIGIT_UART_TX", "uart_tx"), role("uwb", "UWB_UART_RX", "uart_rx")],
    "PA9", BOARD, INSTANCE_MAP,
  );
  assert.equal(cls.kind, "conflict");
  assert.match(cls.reason, /外设/);
});

test("同一器件实例（灰度 8 路）→ 合法共享；混入 UART 同脚 → 冲突", () => {
  const gray = pinShareClass(
    [role("huidu", "R2", "gpio_in"), role("pid", "GRAY_D6", "gpio_in")],
    "PA22", BOARD, INSTANCE_MAP,
  );
  assert.equal(gray.kind, "share");
  const mixed = pinShareClass(
    [role("huidu", "L1", "gpio_in"), role("debug", "DEBUG_UART_RX", "uart_rx")],
    "PA22", BOARD, INSTANCE_MAP,
  );
  assert.equal(mixed.kind, "conflict");
});

test("同型同脚但分属不同外设（DIP 拨码 × 灰度）→ 冲突", () => {
  const cls = pinShareClass(
    [role("config", "DIP0", "gpio_in"), role("pid", "GRAY_D1", "gpio_in")],
    "PB12", BOARD, INSTANCE_MAP,
  );
  assert.equal(cls.kind, "conflict");
});

test("pwm 与 adc 同脚 → 冲突（两路外设不可并）", () => {
  const cls = pinShareClass(
    [role("motor", "MOTOR_A_PWM", "pwm"), role("adc", "ADC_CH0", "adc")],
    "PA1", BOARD, INSTANCE_MAP,
  );
  assert.equal(cls.kind, "conflict");
});

test("单角色 / 空列表 → none", () => {
  assert.equal(pinShareClass([role("a", "X", "gpio_in")], "PA1", BOARD, INSTANCE_MAP).kind, "none");
  assert.equal(pinShareClass([], "PA1", BOARD, INSTANCE_MAP).kind, "none");
});

test("pinRoleResourceKeys：uart/i2c 取能力实例，gpio 取实例映射，其余为空", () => {
  assert.deepEqual(
    pinRoleResourceKeys(role("zigbee_uart", "T", "uart_tx"), "PB10", BOARD, INSTANCE_MAP),
    ["UART_3"],
  );
  assert.deepEqual(
    pinRoleResourceKeys(role("ml_mpu6050", "S", "i2c_scl"), "PA1", BOARD, INSTANCE_MAP),
    ["I2C0"],
  );
  assert.deepEqual(
    pinRoleResourceKeys(role("pid", "GRAY_D1", "gpio_in"), "PA22", BOARD, INSTANCE_MAP),
    ["HUIDU", "MOTOR_PID"],
  );
  assert.deepEqual(
    pinRoleResourceKeys(role("config", "DIP0", "gpio_in"), "PA22", BOARD, INSTANCE_MAP),
    [],
  );
  assert.deepEqual(
    pinRoleResourceKeys(role("motor", "M", "pwm"), "PA1", BOARD, INSTANCE_MAP),
    [],
  );
});
