"""mspm0 syscfg 动态裁剪（工单 syscfg-prune/01）：按选中模块集裁掉未选实例。

契约：全选理论模块 == 母版逐字节；空选裁掉全部外设实例（Board/SYSCTL 保留）；
选 motor 只留 motor 消费的实例（PWMAB/MOTOR_PID/DC_MOTOR + Board/SYSCTL）；
共享实例任一消费模块选中即保留（选 key 留 DC_MOTOR/KEY；选 pid 留 HUIDU）。
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

from contest_generator.boards import board_for_platform
from contest_generator.library import list_modules
from contest_generator.pin_bindings import auto_assign_bindings, resolve_bindings
from contest_generator.syscfg_instances import INSTANCE_CONSUMERS
from contest_generator.syscfg_model import parse_syscfg
from contest_generator.syscfg_prune import (
    adc_slot_plan,
    prune_syscfg,
    syscfg_pin_conflict_report,
)
from contest_generator.selection import resolve_dependencies

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MASTER_SYSCFG = (
    LIBRARY_ROOT / "masters" / "mspm0" / "mspm0.syscfg"
).read_text(encoding="utf-8", newline="")


def test_prune_all_selected_is_byte_identical():
    selected = sorted({s for consumers in INSTANCE_CONSUMERS.values() for s in consumers})
    assert prune_syscfg(MASTER_SYSCFG, selected) == MASTER_SYSCFG


def _assert_instance_present(text: str, instance: str) -> None:
    assert re.search(rf"^\s*const\s+{instance}\s*=", text, re.M), instance
    assert re.search(rf"^\s*{instance}\.", text, re.M), instance


def _assert_instance_absent(text: str, instance: str) -> None:
    assert not re.search(rf"^\s*const\s+{instance}\s*=", text, re.M), instance
    assert not re.search(rf"^\s*{instance}\.", text, re.M), instance


def test_prune_empty_removes_all_peripheral_instances():
    out = prune_syscfg(MASTER_SYSCFG, [])
    for instance in INSTANCE_CONSUMERS:
        _assert_instance_absent(out, instance)
    assert "const Board = scripting.addModule" in out
    assert "SYSCTL" in out


def test_prune_motor_keeps_only_motor_instances():
    out = prune_syscfg(MASTER_SYSCFG, ["motor"])
    for keep in ("PWMAB", "DC_MOTOR"):
        _assert_instance_present(out, keep)
    for drop in ("DCC_100_PWM2", "MOTOR_PID", "NTB", "HUIDU", "KEY", "LED_BEEP",
                 "STEP_MOTOR", "IMU601", "DIGIT_UART", "DEBUG_UART", "UWB_UART", "OLED", "I2C_0"):
        _assert_instance_absent(out, drop)
    # 模块变量：GPIO 被 DC_MOTOR 使用，PWM 被 PWMAB 使用；MOTOR_PID 随旧
    # PID 逻辑剥离不再被 motor 消费，TIMER 一并裁掉
    assert "const TIMER" not in out and "const GPIO" in out and "const PWM" in out
    # 未使用的 UART / I2C 模块变量连 addModule 一起裁掉
    assert "const UART" not in out
    assert "const I2C" not in out


def test_prune_shared_instance_kept_by_any_consumer():
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["motor"]), "DC_MOTOR")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["key"]), "DC_MOTOR")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["key"]), "KEY")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["pid"]), "HUIDU")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["pid"]), "MOTOR_PID")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["xunji"]), "HUIDU")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["coord_detect"]), "DIGIT_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["debug_uart"]), "DEBUG_UART")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["uwb_uart"]), "DEBUG_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["zigbee_uart"]), "ZIGBEE_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["zigbee_uart_key"]), "ZIGBEE_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["zigbee_link"]), "ZIGBEE_UART")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["digit_uart"]), "ZIGBEE_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ir_beam"]), "IR_BEAM")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["key"]), "IR_BEAM")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "HC05_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "HC05")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["uwb_uart"]), "HC05_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["nrf24l01"]), "NRF24L01")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "NRF24L01")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ir_remote"]), "IR_REMOTE")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "IR_REMOTE")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["max7219"]), "MAX7219")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "MAX7219")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["lcd"]), "LCD")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "LCD")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["tp_xpt2046"]), "TP_XPT2046")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "TP_XPT2046")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["oled"]), "OLED_SPI")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "OLED_SPI")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["pca9685"]), "PCA9685")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "PCA9685")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ir_remote_tx"]), "IR_TX")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "IR_TX")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["jq8900"]), "JQ8900")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "JQ8900")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["syn6288"]), "SYN6288")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "SYN6288")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["rc522"]), "RC522")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "RC522")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["fingerprint"]), "FINGERPRINT_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["fingerprint"]), "FINGERPRINT")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "FINGERPRINT_UART")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "FINGERPRINT")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["sht20"]), "SHT20")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "SHT20")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["jy61p"]), "JY61P")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "JY61P")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["l298n"]), "L298N_PWM")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["l298n"]), "L298N")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "L298N_PWM")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "L298N")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["open_mv4"]), "OPENMV4_UART")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "OPENMV4_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["dht11"]), "DHT11")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "DHT11")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ds18b20"]), "DS18B20")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "DS18B20")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["sht30"]), "SHT30")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "SHT30")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["sgp30"]), "SGP30")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "SGP30")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ags10"]), "AGS10")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "AGS10")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ttp224"]), "TTP224")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "TTP224")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["human_ir"]), "HUMAN_IR")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "HUMAN_IR")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["microwave_radar"]), "MICROWAVE")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "MICROWAVE")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["bh1750"]), "BH1750")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "BH1750")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ads1115"]), "ADS1115")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "ADS1115")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["tcs34725"]), "TCS34725")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "TCS34725")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mlx90614"]), "MLX90614")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "MLX90614")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["at24c02"]), "AT24C02")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "AT24C02")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["us016"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ir_distance"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq2"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq135"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq5"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["flame"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["soil"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["photoresistance"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["rain"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["s12sd"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["gp2y1014au"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["gp2y1014au"]), "GP2Y1014")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "GP2Y1014")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["relay"]), "RELAY")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "RELAY")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["as32"]), "AS32_UART")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "AS32_UART")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["bmp180"]), "BMP180")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "BMP180")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ms5611"]), "MS5611")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "MS5611")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq3"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq4"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq6"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq7"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq8"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["mq9"]), "ADC12_0")
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["ms1100"]), "ADC12_0")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["hc05"]), "ADC12_0")


def test_every_master_instance_is_registered_in_consumer_map():
    """母版新增 UART/外设实例必须登记消费映射——漏登记靠 prune 防御保留会
    让「未选模块的实例不落盘」失效（本批 UWB/ZIGBEE 曾缺）。"""
    declared = {
        m.group(1)
        for line in MASTER_SYSCFG.splitlines()
        if (m := re.match(r"^\s*const\s+([A-Za-z_]\w*)\s*=\s*[A-Za-z_\w]+\.addInstance\(\);?\s*$", line))
    }
    assert declared
    assert declared <= set(INSTANCE_CONSUMERS), declared - set(INSTANCE_CONSUMERS)
    _assert_instance_present(prune_syscfg(MASTER_SYSCFG, ["uwb_uart"]), "UWB_UART")
    _assert_instance_absent(prune_syscfg(MASTER_SYSCFG, ["digit_uart"]), "UWB_UART")


def test_syscfg_prune_does_not_import_pinwriter():
    """反向 import 旧环已拆除（工单 syscfg-file-model/04）：syscfg_prune 曾只为
    拿文件名常量 import pinwriter——文件名常量单源在 syscfg_model，文件级裁剪
    挂钩并入 pinwriter.apply_pin_bindings，本模块不再 import pinwriter。"""
    module = importlib.import_module("contest_generator.syscfg_prune")
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    pinwriter_imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.split(".")[-1] == "pinwriter"
    ]
    assert pinwriter_imports == []


# ---------------------------------------------------------------------------
# 槽位级裁剪 + 落盘冲突报告（工单 hwcheck-pin-conflict-exit/01）
#
# 母版 ADC12_0 把 8 个 MEM 脚全占了，而实例粒度裁剪只到「选了 ADC12_0 就整段保留」
# ——没选中的模块（flame/soil/mq135…）的那几根脚照样落盘，冲突求解器看不见它们
# （角色「未登记」）。这组用例钉住：让位的只有真撞上的，且让位后不再有落点行。
# ---------------------------------------------------------------------------

ALL_MANIFESTS = list_modules(LIBRARY_ROOT / "modules")
MSPM0_BOARD = board_for_platform("mspm0")
_WITH_ADC = ["led", "delay", "debug_uart", "oled", "adc"]


def _manifests(slugs: list[str]):
    """依赖展开后的 manifest 集（与生成 / 检测页同一口径：xunji 会带出 motor）。"""
    by_slug = {m.slug: m for m in ALL_MANIFESTS}
    return resolve_dependencies(slugs, by_slug)


def _plan(slugs: list[str], bindings: dict[str, str] | None = None):
    return adc_slot_plan(_manifests(slugs), "mspm0", bindings or {})


def _report(
    slugs: list[str],
    bindings: dict[str, str] | None = None,
    master_syscfg: str | None = None,
    **kw,
):
    """落盘冲突报告（判据本体）。`master_syscfg` 缺省 = 真母版；造重名现场时传
    注入过的那一份（真母版 02 之后恒为 0 组，见 `collision_reverted_syscfg`）。"""
    return syscfg_pin_conflict_report(
        master_syscfg=MASTER_SYSCFG if master_syscfg is None else master_syscfg,
        manifests=_manifests(slugs),
        platform="mspm0",
        board=MSPM0_BOARD,
        bindings=bindings or {},
        **kw,
    )


def test_adc_slot_plan_claims_only_declared_slots():
    """claims = 本趟声明的 MEM 槽位（role id 尾 `_CH<N>`）；occupied = 已声明角色的生效脚。

    ⚠ `occupied` 里**没有** PA26 / PA14：它们是孤儿槽位的脚（本趟没有模块声明），
    所以「让位判据」要用 occupied 判**别人有没有要这根脚**，而不是判槽位归谁。
    """
    plan = _plan(_WITH_ADC)
    assert plan.claims == {"ADC12_0": frozenset({0})}
    assert {"PA22", "PA23", "PA24", "PA28"} <= plan.occupied
    assert "PA26" not in plan.occupied and "PA14" not in plan.occupied
    assert _plan(["led", "delay"]).claims == {}


def test_slot_prune_relocates_only_the_colliding_orphan_slot():
    """adc 单选：MEM6（PA22）撞上 debug_uart RX → 让位共读；MEM1（PA26）没撞上 → 原样。"""
    text = prune_syscfg(
        MASTER_SYSCFG, ["led", "delay", "debug_uart", "adc"],
        plan=_plan(["led", "delay", "debug_uart", "adc"]),
    )
    assert 'ADC12_0.peripheral.adcPin3.$assign = "PA24";' in text, "自己的槽位不动"
    assert 'ADC12_0.peripheral.adcPin1.$assign  = "PA26";' in text, (
        "没撞上的孤儿槽位保持原样（少动是硬要求：adc 配方第二路读的就是 MEM1）"
    )
    assert "ADC12_0.peripheral.adcPin7.$assign" not in text, "撞上的槽位撤掉落点行"
    assert 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_3";' in text, (
        "让位 = 与已声明槽位共读同一通道（只删落点行不够：SysConfig 会按 chansel 认回脚）"
    )
    assert '未让位前 = "PA22"' in text, "产物里留痕，读工程的人看得出这根脚动过"


def test_slot_prune_keeps_all_slots_when_nobody_collides():
    """只选 adc（无输出通道）：一根都不动（没人撞 = 不动）。"""
    slugs = ["led", "delay", "adc"]
    text = prune_syscfg(MASTER_SYSCFG, slugs, plan=_plan(slugs))
    assert text.count("ADC12_0.peripheral.adcPin") == 8


def test_slot_relocation_preserves_line_endings():
    """让位只换那一行的内容，**行尾原样**（母版 CRLF；混一行 LF 会让逐字节契约名存实亡）。"""
    slugs = ["led", "delay", "debug_uart", "adc"]
    assert "\r\n" in MASTER_SYSCFG, "母版是 CRLF（这条判据的前提）"
    text = prune_syscfg(MASTER_SYSCFG, slugs, plan=_plan(slugs))
    assert "未让位前" in text
    assert [line for line in text.split("\r\n") if "\n" in line] == []


def test_slot_prune_without_plan_is_the_old_instance_granularity():
    """不给 plan = 整实例粒度（旧行为逐字节，独立调用方与测试仍走这条）。"""
    slugs = ["led", "delay", "debug_uart", "adc"]
    assert "ADC12_0.peripheral.adcPin7" in prune_syscfg(MASTER_SYSCFG, slugs)


def test_slot_prune_follows_the_leader_rebind():
    """已声明槽位改绑换通道 → 跟着它共读的孤儿槽位跟着换。

    不跟着换就会指回一个**没有显式落点行**的通道——那个脚由 SysConfig 隐式分配，
    静态门禁看不见（真机上可能又撞回别的模块）。
    """
    slugs = ["led", "delay", "debug_uart", "adc"]
    manifests = _manifests(slugs)
    plan = adc_slot_plan(manifests, "mspm0", {})
    resolved = resolve_bindings(
        manifests, "mspm0", MSPM0_BOARD, {"adc.ADC_CH0": "PA26"}
    )
    model = parse_syscfg(MASTER_SYSCFG).prune(slugs, adc_plan=plan)
    assert model.adc_followers, "让位过的槽位要记进跟随表"
    text = model.rewrite(resolved).to_text()
    assert 'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_1";' in text
    assert 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_1";' in text, (
        "孤儿槽位跟着已声明槽位换通道"
    )
    assert 'ADC12_0.peripheral.adcPin1.$assign = "PA26";' in text
    assert "adcPin3" not in text


def test_conflict_report_clears_after_slot_relocation():
    """让位之后那根脚不再被两只实例抢（门禁与检测页共吃的判据）。"""
    assert _report(["led", "delay", "debug_uart", "adc"]).pin_count == 0
    # 对照：不给槽位级裁剪的旧口径下，这根脚正是「角色未登记」的挡路者
    from contest_generator.syscfg_model import parse_syscfg as _parse

    manifests = _manifests(["led", "delay", "debug_uart", "adc"])
    by_pin: dict[str, list[str]] = {}
    for assign in _parse(MASTER_SYSCFG).prune(
        [m.slug for m in manifests]
    ).rewrite(()).assigns:
        by_pin.setdefault(assign.pin, []).append(assign.path)
    assert any(path.endswith("adcPin7") for path in by_pin["PA22"]), (
        "旧口径下 PA22 上有 ADC12_0 的孤儿落点（本单要修的就是它）"
    )


def test_conflict_report_catches_duplicate_pin_names(collision_reverted_syscfg):
    """**同名引脚符号**也要报（工单 11 的判据，工单 02 之后改在注入现场上判）：
    `SCL`/`SDA` 这类 `$name` 是 SysConfig 的另一条全局唯一约束，`$assign` 判据
    看不见它。

    现场怎么造：工单 `hwcheck-acceptance/02` 已把母版 14 组同名符号全部改名
    （`SCL` → `OLED_SPI_SCL` 这种），**真母版今天一组重名都没有**——判据不会自己
    红。所以这里用 `collision_reverted_syscfg`：真母版 + 把 OLED_SPI 那两个符号
    **撤回**成 `SCL`/`SDA`，等价于"将来又有一件模块把引脚起成同名"。判据必须在这
    份现场上抓住它（真母版上则必须 `name_count == 0`，见
    `test_master_pin_symbols_are_globally_unique`）。

    形态取真库上最日常的一组：地猛星 + 板子活着 + 调试串口 + OLED + JY61P
    （**一个自建件都不需要**），并按用户实际动作先点一次「自动配置」
    （`auto_assign_bindings(resolve_default_conflicts=True)`）——那一跳解得开
    **同脚**冲突（PA22 那条），于是剩下的就只有这一根轴。

    判据三条腿：① 引脚冲突被自动配置解得干干净净（**同一个脚**没人抢）；
    ② 同名冲突报出来；③ 报的那一行点到两件模块的名字（学生据此去掉一件）。
    """
    manifests = _manifests(["led", "delay", "debug_uart", "oled", "jy61p"])
    solved = auto_assign_bindings(
        manifests, "mspm0", MSPM0_BOARD, {}, resolve_default_conflicts=True
    )
    report = syscfg_pin_conflict_report(
        master_syscfg=collision_reverted_syscfg, manifests=manifests,
        platform="mspm0", board=MSPM0_BOARD, bindings=solved.bindings,
        diagnosis_bindings={},
    )
    assert report.pin_count == 0, (
        "这一组没有人抢同一个脚（自动配置解得开）——本单要抓的是另一轴：\n"
        + "\n".join(report.lines)
    )
    assert report.name_count > 0, (
        "OLED_SPI 与 JY61P 的 SCL/SDA 同名，必须报出来（工单 11 之前它静默放行）"
    )
    text = "\n".join(report.name_lines)
    for slug in ("oled", "jy61p"):
        assert slug in text, f"要点名两件模块（学生据此去掉一件）：{text}"
    assert "SCL" in text and "SDA" in text, text


def test_master_pin_symbols_are_globally_unique():
    """**构建期守卫**（工单 hwcheck-acceptance/02）：母版 `mspm0.syscfg` 的引脚
    符号名必须全局唯一。

    判据复用既有的落盘冲突报告（`manifests=()` = 产物复核形态：不 prune、不
    rewrite，直接判传进来的全文），所以**新加一个与既有实例同名的引脚符号，这条
    用例当场红**——不必等谁去生成一次工程、更不必等 CCS 报
    `Duplicate name`。02 之前母版有 14 组这样的同名（`SCL` 一组就 18 个实例）。

    为什么这条判据能立起来：02 把撞名的符号改成了 `<实例名>_<原符号>`
    （生成宏因此是 `<实例>_<实例>_<符号>_<后缀>` 形态，见 CONTEXT.md
    「syscfg 文件模型」），母版从此满足"全局唯一"这一条不变量。
    """
    report = syscfg_pin_conflict_report(
        master_syscfg=MASTER_SYSCFG, manifests=(), platform="mspm0",
        board=None, bindings=None,
    )
    assert report.name_count == 0, (
        "母版引脚符号又撞名了——SysConfig 会报 Duplicate name、工程编不过。"
        "新加实例时把 `$name` 起成 `<实例名>_<原名>`：\n"
        + "\n".join(report.name_lines)
    )


def test_duplicate_pin_names_are_judged_after_pruning(collision_reverted_syscfg):
    """判据看**裁剪后**的模型：没选中的实例被裁掉，就不该因为它报冲突。

    现场必须用撤回改名的那份母版：真母版在工单 `hwcheck-acceptance/02` 之后
    **恒为 0 组**，拿它跑这条用例会退化成恒绿空断言（判全文也过）。

    判据两条腿（同一份母版、同一天）：① `oled + jy61p` **两件都选** → 报出来
    （撞名是实打实的，不是判据在猜）；② 只选 `oled` → 一条都不报
    （`JY61P` 那个实例已被裁掉，它那份 `SCL` 不该再算数）。
    """
    both = _report(
        ["led", "delay", "debug_uart", "oled", "jy61p"],
        master_syscfg=collision_reverted_syscfg,
    )
    assert both.name_count > 0, "两件都选中 → 重名必须报出来（对照腿）"
    only_oled = _report(
        ["led", "delay", "debug_uart", "oled"],
        master_syscfg=collision_reverted_syscfg,
    )
    assert only_oled.name_count == 0, "只选 oled：JY61P 已被裁掉，不该再报"


def test_conflict_report_reports_remaining_and_diagnosis_baseline():
    """装不下时：逐脚点名 + 容量诊断以**用户原始选择**为基准（不是自动搬过的增量）。"""
    slugs = ["led", "oled", "debug_uart", "key", "beep", "sr04", "jy61p",
             "xunji", "ml_mpu6050"]
    manifests = _manifests(slugs)
    solved = auto_assign_bindings(
        manifests, "mspm0", MSPM0_BOARD, {}, resolve_default_conflicts=True
    )
    report = syscfg_pin_conflict_report(
        master_syscfg=MASTER_SYSCFG, manifests=manifests, platform="mspm0",
        board=MSPM0_BOARD, bindings=solved.bindings, diagnosis_bindings={},
    )
    assert report.pin_count > 0 and all("·" in line for line in report.lines)
    assert "可解开 2 组" in report.capacity, (
        "诊断基准是用户原始选择（这一组本来能解开 2 组）"
    )
    # 反例（本单实测撞到过）：拿已经搬过的增量当基准 → 那些角色被当成「用户显式
    # 绑定」不可再让位 → 读成「可解开 0 组」，与事实相反。
    wrong = syscfg_pin_conflict_report(
        master_syscfg=MASTER_SYSCFG, manifests=manifests, platform="mspm0",
        board=MSPM0_BOARD, bindings=solved.bindings,
    )
    assert "可解开 0 组" in wrong.capacity

