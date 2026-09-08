"""工单 preselect-visibility/05：器件模块映射补齐（类别条目 + 词项 + 映射）。

策略：一个器件类别一条参考条目（素材 = 该类别的 lckfb 移植手册原文；无手册的
少数件取库内模块代码切片），条目内按模块分目录；`MODULE_PERIPHERAL_TERMS` 的
新映射统一指向该类别词项。幂等：同标题条目已存在则跳过。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    add_reference,
    list_references,
    module_kit_vocabulary,
)

MANUALS = ROOT / "sources" / "materials" / "lckfb-地猛星移植手册"
REFERENCES = ROOT / "library" / "references"
MODULES = ROOT / "library" / "modules"

# (标题, 简介, [(条目内文件名, 手册文件名)…], [无手册的模块 slug（取代码切片）…])
ENTRIES: tuple[tuple[str, str, tuple[tuple[str, str], ...], tuple[str, ...]], ...] = (
    (
        "气体传感器器件手册合集（气体）",
        "气体检测器件移植手册合集：MQ 系列（2/3/4/5/6/7/8/9/135）、MS1100、AGS10、"
        "SGP30——引脚、时序与读数换算，骨架阶段选中气体类模块时的器件级例程参考。",
        (
            ("mq-2.md", "sensor--mq-2-sensor.md"),
            ("mq-3.md", "sensor--mq-3-sensor.md"),
            ("mq-4.md", "sensor--mq-4-sensor.md"),
            ("mq-5.md", "sensor--mq-5-sensor.md"),
            ("mq-6.md", "sensor--mq-6-sensor.md"),
            ("mq-7.md", "sensor--mq-7-sensor.md"),
            ("mq-8.md", "sensor--mq-8-sensor.md"),
            ("mq-9.md", "sensor--mq-9-sensor.md"),
            ("mq-135.md", "sensor--mq-135-sensor.md"),
            ("ms1100.md", "sensor--ms1100-gas-sensor.md"),
            ("ags10.md", "sensor--ags10-harmful-gas-sensor.md"),
            ("sgp30.md", "sensor--sgp30-gas-sensor.md"),
        ),
        (),
    ),
    (
        "温湿度传感器器件手册合集（温湿度）",
        "温湿度器件移植手册合集：DHT11、DS18B20、SHT20、SHT30、AHT10——单总线与 "
        "I2C 两种形态，骨架阶段选中温湿度类模块时的器件级例程参考。",
        (
            ("dht11.md", "sensor--dht11-temp-humi-sensor.md"),
            ("ds18b20.md", "sensor--ds18b20-temp-sensor.md"),
            ("sht20.md", "sensor--sht20-temp-humi-sensor.md"),
            ("sht30.md", "sensor--sht30-temp-humi-sensor.md"),
            ("aht10.md", "sensor--aht10-temp-humi-sensor.md"),
        ),
        (),
    ),
    (
        "气压传感器器件手册合集（气压）",
        "气压/海拔器件移植手册合集：BMP180、MS5611——I2C 读取与温度补偿，"
        "骨架阶段选中气压类模块时的器件级例程参考。",
        (
            ("bmp180.md", "sensor--bmp180-pressure-sensor.md"),
            ("ms5611.md", "sensor--ms5611-pressure-sensor.md"),
        ),
        (),
    ),
    (
        "光照与颜色传感器器件手册合集（光照 / 颜色）",
        "光照与颜色器件移植手册合集：BH1750、光敏电阻、S12SD 紫外、TCS34725 颜色、"
        "MLX90614 红外测温——骨架阶段选中光照/颜色类模块时的器件级例程参考。",
        (
            ("bh1750.md", "sensor--bh1750-light-intensity-sensor.md"),
            ("photoresistance.md", "sensor--photoresistance-sensor.md"),
            ("s12sd.md", "sensor--s12sd-uv-sensor.md"),
            ("tcs34725.md", "sensor--tcs34725-color-recognition-sensor.md"),
            ("mlx90614.md", "sensor--mlx90614-non-contact-temp-sensor.md"),
        ),
        (),
    ),
    (
        "测距传感器器件手册合集（测距）",
        "测距器件移植手册合集：HC-SR04、US-016 超声波、红外测距——触发/回波与模拟量"
        "换算，骨架阶段选中测距类模块时的器件级例程参考。",
        (
            ("sr04.md", "sensor--sr04-ultrasonic-ranging-sensor.md"),
            ("us016.md", "sensor--us-016-ultrasonic-ranging-sensor.md"),
            ("ir_distance.md", "sensor--Infrared-distance-sensor.md"),
        ),
        (),
    ),
    (
        "姿态传感器器件手册合集（姿态）",
        "姿态器件移植手册合集：MPU6050 六轴、JY61P——I2C/UART 读取与姿态解算素材，"
        "骨架阶段选中姿态类模块时的器件级例程参考。",
        (
            ("mpu6050.md", "sensor--mpu6050-six-axis-sensor.md"),
            ("jy61p.md", "sensor--jy61p-measurement-sensor.md"),
        ),
        (),
    ),
    (
        "称重与模数采集器件手册合集（称重）",
        "称重与模数采集器件移植手册合集：HX711 称重（24 位串行 ADC）、ADS1115 "
        "四通道外扩 ADC——骨架阶段选中称重/外扩采集类模块时的器件级例程参考。",
        (
            ("hx711.md", "sensor--hx711-weighing-sensor.md"),
            ("ads1115.md", "sensor--ads1115-multichannel-a-to-d-sensor.md"),
        ),
        (),
    ),
    (
        "指纹与语音器件手册合集（指纹 / 语音）",
        "指纹与语音器件移植手册合集：AS608 指纹、JQ8900 语音播报、SYN6288 语音合成"
        "——串口协议与引脚，骨架阶段选中指纹/语音类模块时的器件级例程参考。",
        (
            ("fingerprint.md", "sensor--fingerprint-recognition-sensor.md"),
            ("jq8900.md", "control--jq8900-voice-broadcast-module.md"),
            ("syn6288.md", "control--syn6288-speech-synthesis-broadcast-module.md"),
        ),
        (),
    ),
    (
        "触摸与摇杆器件手册合集（触摸 / 摇杆）",
        "触摸与摇杆器件移植手册合集：TTP224 电容触摸、双轴按键摇杆——骨架阶段"
        "选中触摸/摇杆类模块时的器件级例程参考。",
        (
            ("ttp224.md", "sensor--ttp224-touch-sensor.md"),
            ("joystick.md", "control--two-axis-keystroke-rocker-module.md"),
        ),
        (),
    ),
    (
        "彩屏与数码管器件手册合集（彩屏 / 数码管）",
        "彩屏与数码管器件移植手册合集：中景园 IPS 彩屏族（ST7735/GC9A01/ST7789 等）、"
        "ILI9341、ILI9488、MAX7219 点阵——骨架阶段选中彩屏/数码管类模块时的器件级"
        "例程参考。",
        (
            ("lcd-0-96-color.md", "screen--0-96-color-screen.md"),
            ("lcd-1-3-color.md", "screen--1-3-color-screen.md"),
            ("lcd-1-47-color.md", "screen--1-47-color-screen.md"),
            ("lcd-1-69-color.md", "screen--1-69-color-screen.md"),
            ("lcd-1-28-round-color.md", "screen--1-28-round-color-screen.md"),
            ("max7219.md", "screen--max7219-matrix-display.md"),
        ),
        (),
    ),
    (
        "灯带与执行器件手册合集（灯带）",
        "执行器件移植手册合集：WS2812 幻彩灯带、1 路继电器、L298N 电机驱动、"
        "PCA9685 16 路舵机驱动——骨架阶段选中灯带/执行类模块时的器件级例程参考。",
        (
            ("ws2812.md", "control--ws2812-color-rgb-led.md"),
            ("relay.md", "control--relay-module.md"),
            ("l298n.md", "control--l298n-motor-drive-module.md"),
            ("pca9685.md", "control--16-ch-servo-drive-module.md"),
        ),
        (),
    ),
    (
        "无线通信器件手册合集（无线数传 / 蓝牙 / lora）",
        "无线通信器件移植手册合集：AS32 LoRa 数传、HC-05 蓝牙、NRF24L01 2.4G、"
        "RC522 射频卡——骨架阶段选中无线类模块时的器件级例程参考。",
        (
            ("as32.md", "rf--as32-lora-wireless-communication-module.md"),
            ("hc05.md", "rf--hc05-bluetooth-module.md"),
            ("nrf24l01.md", "rf--nrf24l01-2-4-g-control-module.md"),
            ("rc522.md", "rf--rc522-rf-ic-card-identification-module.md"),
        ),
        (),
    ),
    (
        "人体感应与雷达器件手册合集（人体感应 / 雷达）",
        "人体感应与雷达器件移植手册合集：HC-SR501 人体红外、HB100 微波多普勒雷达"
        "——骨架阶段选中人体感应/雷达类模块时的器件级例程参考。",
        (
            ("human_ir.md", "sensor--human-body-infrared-sensor.md"),
            ("microwave_radar.md", "sensor--microwave-doppler-radar-sensor.md"),
        ),
        (),
    ),
    (
        "烟雾与环境检测器件手册合集（烟雾 / 环境）",
        "环境检测器件移植手册合集：火焰、粉尘、人体红外、微波雷达、雨滴、土壤湿度"
        "——骨架阶段选中环境检测类模块时的器件级例程参考。",
        (
            ("flame.md", "sensor--flame-sensor.md"),
            ("gp2y1014au.md", "sensor--gp2y1014au-dust-sensor.md"),
            ("human_ir.md", "sensor--human-body-infrared-sensor.md"),
            ("microwave_radar.md", "sensor--microwave-doppler-radar-sensor.md"),
            ("rain.md", "sensor--rain-sensor.md"),
            ("soil.md", "sensor--soil-moisture-sensor.md"),
        ),
        (),
    ),
    (
        "存储与编码器件手册合集（存储 / 编码）",
        "存储与旋转编码器件移植手册合集：AT24C02 EEPROM、EC11 旋转编码器、4×4 矩阵"
        "键盘（库内模块代码切片）——骨架阶段选中这几类模块时的例程参考。",
        (),
        ("ec11", "at24c02", "key_matrix"),
    ),
)


def _code_files(slug: str) -> dict[str, str]:
    """无手册模块的代码切片（manifest 声明的文件原文，按模块分目录）。"""
    manifest_dir = MODULES / slug
    files: dict[str, str] = {}
    for path in sorted(manifest_dir.rglob("*")):
        if not path.is_file() or path.suffix not in (".c", ".h"):
            continue
        files[f"{slug}/{path.name}"] = path.read_text(encoding="utf-8", errors="replace")
    return files


def main() -> int:
    existing = {entry.title for entry in list_references(REFERENCES)}
    kit_vocabulary = module_kit_vocabulary(MODULES)
    created: list[str] = []
    for title, description, sources, code_slugs in ENTRIES:
        if title in existing:
            print(f"跳过（已存在）：{title}")
            continue
        files: dict[str, str] = {}
        for name, manual in sources:
            files[name] = (MANUALS / manual).read_text(encoding="utf-8", errors="replace")
        for slug in code_slugs:
            files.update(_code_files(slug))
        entry = add_reference(
            REFERENCES,
            title=title,
            type="器件手册",
            description=description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            files=files,
            kit_vocabulary=kit_vocabulary,
            platform="any",
        )
        created.append(entry.id)
        print(f"入库：{entry.id}（{len(files)} 个文件）")
    print(f"\n新建 {len(created)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
