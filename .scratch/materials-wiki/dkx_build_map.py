# -*- coding: utf-8 -*-
"""地阔星 wiki 模块页 ↔ 库内模块 slug 映射表生成器（dkx-map.tsv）"""
import json, os, glob, re

PAGES = json.load(open(".scratch/materials-wiki/dkx-pages.json", encoding="utf-8"))

# 库侧：slug -> (stm32_entry Y/N, stm32_files 字符串, mspm0 source_url slug 或 "")
LIB = {}
for f in glob.glob("library/modules/*/manifest.json"):
    j = json.load(open(f, encoding="utf-8"))
    plats = j.get("platforms", {})
    stm = plats.get("stm32")
    msp = plats.get("mspm0")
    stm_entry = "Y" if stm else "N"
    stm_files = ",".join(stm.get("files", [])) if (stm and stm.get("files")) else ""
    if not stm_files and stm:
        stm_files = "（母版内嵌）"
    def url_slug(p):
        if not p or not p.get("source_url"):
            return ""
        m = re.search(r"/module/(?:[^/]+)/([^/]+)\.html", p["source_url"])
        return m.group(1) if m else ""
    LIB[j["slug"]] = {
        "stm_entry": stm_entry,
        "stm_files": stm_files,
        "urls": {url_slug(p) for p in (stm, msp) if url_slug(p)},
        "desc": (j.get("description") or "")[:180],
    }

# 手工判定表：page_slug -> dict(lib, basis, action, note)
# basis: "①" source_url 同 slug / "②" 短版·器件·语义 / "③" 无对应（B 新模块）
D = {
 "16-ch-servo-drive-module": ("pca9685","①","","source_url 同 slug（dmx 版页面同名 16-ch-servo-drive-module；PCA9685 16 路舵机驱动板）"),
 "at24c02-eeprom-memory": ("at24c02","①","","source_url 同 slug（AT24C02 EEPROM IIC）"),
 "jq8900-voice-broadcast-module": ("jq8900","①","","source_url 同 slug（JQ8900 串口语音播报）"),
 "l298n-motor-drive-module": ("l298n","①","","source_url 同 slug（L298N 双 H 桥驱动）"),
 "relay-module": ("relay","①","","source_url 同 slug（继电器 GPIO 通断）；【F4 嫌疑】页面代码块见 RCC_AHB1PeriphClockCmd/GPIO_OType 风格（×3），移植 F103 需甄别"),
 "sg90-steering-engine": ("servo","②","","标题/器件匹配：SG90 舵机 = 库 servo（0.5-2.5ms/20ms 脉宽 0-180° 同 API）；【F4 嫌疑】页面见 GPIO_OType（×1）"),
 "syn6288-speech-synthesis-broadcast-module": ("syn6288","①","","source_url 同 slug（SYN6288 语音合成串口）"),
 "tb6612-motor-drive-module": ("motor","②","","器件匹配：TB6612 双路直流电机驱动 = 库 motor（描述「TB6612 双路直流电机驱动」逐字对应；PA6/TIM3_CH1 PWM 同库 API 域）"),
 "two-axis-keystroke-rocker-module": ("joystick","①","","source_url 同 slug（双轴摇杆 = 库 joystick；mspm0 与 adc MEM1 共享通道）"),
 "ws2812-color-rgb-led": ("ws2812","①","","source_url 同 slug（WS2812 彩灯驱动）"),
 "Infrared-decoding-coding-module": ("ir_remote_tx","①","","source_url 同 slug（红外遥控编码/发送 = ir_remote_tx）"),
 "as32-lora-wireless-communication-module": ("as32","①","","source_url 同 slug（AS32 LoRa 串口通信）"),
 "ec01g-nbiot-gps-module": ("（新）ec01g","③","","库无 NB-IoT/GPS 模块：无线族 as32/nrf24l01/hc05/zigbee_* 器件协议均不同 → 独立新模块（AT 指令串口协议）"),
 "esp01s-wifi-module": ("（新）esp01s","③","","库无 WiFi 模块：ESP01S AT 指令 WiFi，与 LoRa/2.4G/蓝牙无重叠 → 独立新模块"),
 "hc05-bluetooth-module": ("hc05","①","","source_url 同 slug（HC05 蓝牙串口透传）"),
 "infrared-receiving-module": ("ir_remote","①","","source_url 同 slug（红外接收解码 = ir_remote）"),
 "neo-6m-gps-module": ("（新）neo_6m","③","","库无 GPS 模块：NEO-6M UART 协议帧解析，与 imu_uart/open_mv4 仅「UART 帧解析」结构相似、器件协议不同 → 独立新模块"),
 "nrf24l01-2-4-g-control-module": ("nrf24l01","①","","source_url 同 slug（NRF24L01 2.4G 无线）"),
 "rc522-rf-ic-card-identification-module": ("rc522","①","","source_url 同 slug（RC522 射频 IC 卡）"),
 "0-91-color-screen": ("oled","②","","页面实为 0.91 寸 SSD1306 128×32 单色 OLED（标题「彩屏」系 wiki 命名）；库 oled 已支持 0.91 变体 oled_set_res(OLED_RES_128X32) → 归 oled 而非 lcd"),
 "0-96-color-screen": ("lcd","①","","source_url 同 slug（0.96 寸 ST7735 彩屏 = lcd 六合一 0.96 变体）；【F4 嫌疑】页面代码块见 RCC_AHB1PeriphClockCmd（×3）"),
 "0-96-iic-single-screen": ("oled","②","","SSD1306 I2C 128×64 = 库 oled 默认形态；库 notes「0.96 IIC 与库内同家族仅核对不提炼」"),
 "0-96-single-spi-screen": ("oled","②","","SSD1306 SPI 128×64 = 库 oled SPI 总线变体（批次 12/07 决策 B，软 SPI 5 脚已并入）；【F4 嫌疑】见 RCC_AHB1PeriphClockCmd（×3）"),
 "1-14-color-screen": ("（新）st7789_para","③","","ST7789V 135×240 8 位并口：控制器与 lcd 的 ST7789V2/V3 同族，但 lcd 全系软 SPI 位操作 6 脚，并口 8 数据线驱动结构不同 → 判独立（若 lcd 未来支持并口可并入变体）"),
 "1-28-round-color-screen": ("lcd","②","","GC9A01 240×240 圆屏 = 库 lcd 六合一 1.28 变体（描述明确覆盖）"),
 "1-3-color-screen": ("lcd","②","","ST7789V2 240×240 带字库 = 库 lcd 1.3 变体（库 notes 明确并入；外置字库芯片 zk.c 未入库，需另议）"),
 "1-3-single-oled-screen": ("oled","②","","1.3 寸 SH1106 128×64 单色 OLED = 库 oled 显示家族（notes「ZJY130S0700WG01 同家族仅核对不提炼」）；SH1106 与 SSD1306 同族初始化序列略异 → 并入 oled 变体"),
 "1-47-color-screen": ("lcd","②","","ST7789V3 172×320 = 库 lcd 六合一 1.47 变体（描述明确覆盖）；【F4 嫌疑】见 RCC_AHB1PeriphClockCmd（×3）"),
 "1-69-color-screen": ("lcd","②","","ST7789V2 240×280 = 库 lcd 六合一 1.69 变体（描述明确覆盖）"),
 "1-8-touch-color-screen": ("tp_xpt2046","①","","source_url 同 slug（tp_xpt2046 的 dmx 页即本页）；页面同时含 1.8 寸 ST7735S 屏驱动 = lcd 1.8 变体（屏侧归 lcd，触摸侧归 tp_xpt2046，两件零耦合）"),
 "2-8-and-3-2-color-sreen": ("（新）ili9341","③","","ILI9341 320×240 SPI：库 lcd 六合一仅 ST7735/GC9A01/ST7789V2/V3/ST7735S，控制器不在其列 → 独立；页面触摸为 XPT2046 与 tp_xpt2046 同芯可复用（半重叠）"),
 "3-5-ili9488-color-screen": ("（新）ili9488","③","","ILI9488 320×480 SPI：不在 lcd 变体组 → 独立；触摸 XPT2046 与 tp_xpt2046 同芯可复用（半重叠）"),
 "8-bit-led-tube": ("max7219","①","","source_url 同 slug（8 位数码管 = max7219 BCD 数码管形态）"),
 "max7219-matrix-display": ("max7219","②","","同芯片双形态：库 max7219 描述「同一芯片双显示形态——8 位数码管 BCD 与 4合1 点阵 max7219_write_matrix（1-4 片级联）」，source_url 指向同模块 8-bit-led-tube"),
 "4x4-keyboard": ("（新）key_matrix","③","","库 key = N 路独立按键 GPIO 读取（上拉低电平，多实例 start/stop/mode/set），本页 = 4 行输出+4 列输入行列扫描 16 键（key_scan 0/1-16），扫描机制不同 → 独立（仅同属「按键输入」大类，非重叠）"),
 "Infrared-distance-sensor": ("ir_distance","①","","source_url 同 slug（大小写一致：Infrared-distance-sensor；红外模拟量测距 = ir_distance，mspm0 与 adc MEM3 共享通道）"),
 "Infrared-tracking-sensor": ("huidu","②","","器件/语义匹配：TCRT5000 红外反射黑线检测（DO=1 黑线）与库 huidu「黑线检测（1=黑线）」逐字对应（8 路灰度模块常为 TCRT5000）；页面单通道示例；与 xunji 邻接（xunji=读值+巡线核心），黑线检测页归 huidu"),
 "ads1115-multichannel-a-to-d-sensor": ("ads1115","①","","source_url 同 slug（ADS1115 四通道 16bit 外扩 ADC = 库 ads1115，软 I2C 驱动）"),
 "ags10-harmful-gas-sensor": ("ags10","①","","source_url 同 slug（AGS10 有害气体 IIC）"),
 "aht10-temp-humi-sensor": ("aht10","①","","source_url 同 slug（AHT10 温湿度软 I2C）"),
 "bh1750-light-intensity-sensor": ("bh1750","①","","source_url 同 slug（BH1750 光照强度 IIC）"),
 "bmp180-pressure-sensor": ("bmp180","①","","source_url 同 slug（BMP180 气压 IIC）"),
 "dht11": ("dht11","②","","同名短版：页面 slug=dht11 = 库 slug dht11（库 mspm0 source_url 为 dmx 页 dht11-temp-humi-sensor 同器件）；单总线位时序"),
 "ds18b20-temp-sensor": ("ds18b20","①","","source_url 同 slug（DS18B20 单总线温度）"),
 "ec11": ("（新）ec11","③","","库无旋转编码器模块（无 encoder slug）；与 ntb_time（系统毫秒时间戳 SysTick/NTB）无语义重叠，与 key（独立按键）机制不同（A/B 相正交脉冲），motor 的编码器读数为电机测速闭环属另一域 → 独立新模块"),
 "fingerprint-recognition-sensor": ("fingerprint","①","","source_url 同 slug（指纹识别 UART 帧）"),
 "flame-sensor": ("flame","①","","source_url 同 slug（火焰检测 GPIO/ADC）"),
 "gp2y1014au-dust-sensor": ("gp2y1014au","①","","source_url 同 slug（GP2Y1014AU 粉尘模拟量）"),
 "grayscale-sensor": ("xunji","②","","单路模拟灰度读值（灰度百分比）→ 库 xunji「8 路灰度读取（位图）+ 加权质心巡线核心」读值域与巡线域覆盖本页用途；与 huidu（纯 8 路灰度读值黑线检测）邻接——TCRT5000 黑线检测页已归 huidu，本节按灰度读值+巡线域归 xunji（二选一，仅读值场景亦可归 huidu）"),
 "human-body-infrared-sensor": ("human_ir","①","","source_url 同 slug（人体红外 GPIO）"),
 "hx711-weighing-sensor": ("hx711","①","","source_url 同 slug（HX711 称重）"),
 "microwave-doppler-radar-sensor": ("microwave_radar","①","","source_url 同 slug（微波多普勒雷达 GPIO）"),
 "mlx90614-non-contact-temp-sensor": ("mlx90614","①","","source_url 同 slug（MLX90614 非接触测温软 I2C）"),
 "mpu6050-six-axis-sensor": ("ml_mpu6050","②","","标题匹配：MPU6050 六轴 = 库 ml_mpu6050（库 mspm0/stm32 双平台均有；source_url 为采购链接非 wiki 页，故非 ①）"),
 "mq-135-sensor": ("mq135","①","","source_url 同 slug（MQ-135 空气质量 ADC）"),
 "mq-2-sensor": ("mq2","①","","source_url 同 slug（MQ-2 烟雾 ADC）"),
 "mq-3-sensor": ("mq3","①","","source_url 同 slug（MQ-3 酒精 ADC）；【F4 嫌疑】页面代码块见 RCC_AHB1PeriphClockCmd（×2）"),
 "mq-4-sensor": ("mq4","①","","source_url 同 slug（MQ-4 甲烷 ADC）"),
 "mq-5-sensor": ("mq5","①","","source_url 同 slug（MQ-5 液化气 ADC）"),
 "mq-6-sensor": ("mq6","①","","source_url 同 slug（MQ-6 丙烷 ADC）"),
 "mq-7-sensor": ("mq7","①","","source_url 同 slug（MQ-7 一氧化碳 ADC）"),
 "mq-8-sensor": ("mq8","①","","source_url 同 slug（MQ-8 氢气 ADC）"),
 "mq-9-sensor": ("mq9","①","","source_url 同 slug（MQ-9 可燃气体 ADC）"),
 "ms1100-gas-sensor": ("ms1100","①","","source_url 同 slug（MS1100 气体 ADC）"),
 "ms5611-pressure-sensor": ("ms5611","①","","source_url 同 slug（MS5611 气压软 I2C）"),
 "photoresistance-sensor": ("photoresistance","①","","source_url 同 slug（光敏电阻 ADC）"),
 "rain-sensor": ("rain","①","","source_url 同 slug（雨滴检测 ADC/GPIO）"),
 "s12sd-uv-sensor": ("s12sd","①","","source_url 同 slug（S12SD 紫外线模拟量）"),
 "sgp30-gas-sensor": ("sgp30","①","","source_url 同 slug（SGP30 气体 IIC）"),
 "sht20-temp-humi-sensor": ("sht20","①","","source_url 同 slug（SHT20 温湿度软 I2C）"),
 "sht30-temp-humi-sensor": ("sht30","①","","source_url 同 slug（SHT30 温湿度软 I2C；库 slug 为短版 sht30）"),
 "soil-moisture-sensor": ("soil","①","","source_url 同 slug（土壤湿度 ADC）"),
 "sr04-ultrasonic-ranging-sensor": ("sr04","①","","source_url 同 slug（SR04 超声测距 GPIO 时序）"),
 "tcs34725-color-recognition-sensor": ("tcs34725","①","","source_url 同 slug（TCS34725 颜色识别 IIC）"),
 "ttp224-touch-sensor": ("ttp224","①","","source_url 同 slug（TTP224 电容触摸 GPIO）"),
 "us-016-ultrasonic-ranging-sensor": ("us016","①","","source_url 同 slug（US-016 超声模拟量测距，mspm0 与 adc MEM0 共读同槽）"),
 "vl53l0x-laser-distance-sensor": ("（新）vl53l0x","③","","库无 ToF 激光测距：与 ir_distance（红外反射模拟量 ADC 测距，同以「测距」命名）原理不同（飞行时间 I2C vs 模拟电压），器件协议互异 → 独立新模块（页面仅 1 代码块，资料最简）"),
}

# 校验：① 判定必须真实存在 source_url 同 slug
urldb = {}
for slug, v in LIB.items():
    for u in v["urls"]:
        urldb.setdefault(u, []).append(slug)
errors = []
for p in PAGES:
    d = D.get(p["slug"])
    if not d:
        errors.append("missing decision: " + p["slug"]); continue
    lib, basis, act, note = d
    if basis == "①" and lib not in urldb.get(p["slug"], []):
        errors.append(f"① mismatch: {p['slug']} -> {lib} (urls={urldb.get(p['slug'])})")
    if basis == "②" and lib.startswith("（新）"):
        errors.append(f"② cannot be new: {p['slug']}")
    if basis == "③" and not lib.startswith("（新）"):
        errors.append(f"③ must be new: {p['slug']}")
if errors:
    print("== ERRORS =="); [print(e) for e in errors]; raise SystemExit(1)

# 生成 TSV
rows = []
for p in PAGES:
    lib, basis, act, note = D[p["slug"]]
    if lib.startswith("（新）"):
        lib_slug, stm_entry, stm_files, action = lib, "-", "-", "B"
    else:
        li = LIB[lib]
        lib_slug, stm_entry, stm_files = lib, li["stm_entry"], li["stm_files"]
        action = "C" if stm_entry == "Y" else "A"
    note_full = f"匹配依据 {basis}：{note}"
    rows.append([p["file"], p["cat"], p["slug"], p["title"], lib_slug, stm_entry,
                 stm_files, action, p["f4"], str(p["code_blocks"]), note_full])

hdr = "page_file\tcat\twiki_slug\twiki_title\tlib_slug\tstm32_entry\tstm32_files\taction\tf4_suspect\tcode_blocks\t备注"
os.makedirs(".scratch/materials-wiki", exist_ok=True)
with open(".scratch/materials-wiki/dkx-map.tsv", "w", encoding="utf-8", newline="\n") as f:
    f.write(hdr + "\n")
    for r in rows:
        f.write("\t".join(r) + "\n")

# 统计
A = [r for r in rows if r[7] == "A"]
B = [r for r in rows if r[7] == "B"]
C = [r for r in rows if r[7] == "C"]
F4 = [r for r in rows if r[8] == "Y"]
D2 = [s for s, v in LIB.items() if s not in {r[4].replace("（新）", "") for r in rows if not r[4].startswith("（新）")} and not s.startswith("（新）")]
print(f"total={len(rows)} A={len(A)} B={len(B)} C={len(C)}")
print("== B（新模块）==")
for r in B: print(f"  {r[2]}\t{r[3]}\t{r[4]}")
print("== C（已有 stm32-核对）==")
for r in C: print(f"  {r[2]}\t{r[3]}\t-> {r[4]}")
print("== F4 嫌疑 ==")
for r in F4: print(f"  {r[2]}\t{r[3]}")
print("== D（库模块无地阔星页面）==")
for s in D2:
    v = LIB[s]
    print(f"  {s}\tstm32={v['stm_entry']}\t{v['stm_files']}\t{'' if v['urls'] else '无wiki来源'}")
# D 附表
with open(".scratch/materials-wiki/dkx-d-appendix.tsv", "w", encoding="utf-8", newline="\n") as f:
    f.write("lib_slug\tstm32_entry\tstm32_files\tmspm0_wiki_source\t库侧描述(截取)\n")
    for s in D2:
        v = LIB[s]
        src = ",".join(sorted(v["urls"])) or "-"
        f.write("\t".join([s, v["stm_entry"], v["stm_files"], src, v["desc"]]) + "\n")
json.dump({"A": [r[2] for r in A], "B": [r[2] for r in B], "C": [r[2] for r in C],
           "F4": [r[2] for r in F4], "D": D2},
          open(".scratch/materials-wiki/dkx-stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("written: .scratch/materials-wiki/dkx-map.tsv / dkx-d-appendix.tsv / dkx-stats.json")
