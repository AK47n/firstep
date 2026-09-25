# -*- coding: utf-8 -*-
"""把工单 08（批次 F）的八格配方写进 `library/hwcheck_recipes.json`（一次性落地脚本）。

事实底稿 = `recon-02-…md` §2 的 `hx711` 小节 + `recon-03-actuators.md` §1–§5；
**每条结论都回驱动源码 / syscfg / pin_config 核过一遍**（recon 是二手来源）：

  * `hx711.h:30-45` / `hx711_stm32.h:34-48` —— `hx711_init()` void（**它内部先读一次去皮**）；
    `hx711_read_raw()` 返回 uint32_t（0 = 20ms 超时）；`HX711_GAP_VALUE` 是 **float 宏**
    （207.00f），**不能进整数读数**。
  * mspm0 引脚 = `mspm0.syscfg:329-338`：SCK=**PA28** / DT=**PA31**（引脚绑定单源）。
    ⚠ **模块头注释 `hx711.h:14-16` 写的是 PB24/PB8，已过期**（历史读数；manifest 与 syscfg
    都是 PA28/PA31）——**本单不改库**，记账进 backlog。
  * `joystick.c:16-18` —— `JOYSTICK_ADC_MAX` / `JOYSTICK_ADC_SAMPLES` 定义在 **.c** 里
    ⇒ mspm0 侧配方引用不到；stm32 侧在 `joystick_stm32.h:31,35`。
    mspm0 的 ADC12_0 是 **8 槽 sequence**（`mspm0.syscfg:1268` 一带），X = MEM1 / Y = MEM2。
  * `servo.h:37-38` —— `servo_init(servo_id, channel)` **双参**、`servo_set_angle` 双参；
  * `servo_mspm0.c:11-28` —— 周期 = `SERVO_PWM_INST_CLK_FREQ / 50`（≠ 20ms 的既有缺陷，
    周期 640000 超 16 位量程 ⇒ mspm0 这一格**不扫 180°**）；`relay.c:23-27` /
    `relay_stm32.c:32-37` —— `relay_set(1)` 吸合 / `relay_set(0)` 断开、`RELAY_ON_LEVEL` = 0。
  * `ml_gpio.c:13-56` —— `gpio_init(OUT_PP)` **只写 CRL/CRH、不写 ODR** ⇒ relay × stm32
    上电瞬间那几拍是低电平（= 吸合）——学生最容易被吓到的现象，note 必须写。
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 共享候选池（工单 07 起每条配方都带；本批四件**按工单逐件给的候选在前**、池子补在后面兜底）
POOL = ["n", "z", "i", "0", "1", "2", "3"]


def candidates(*specific):
    """工单给的那几个候选在前，共享池补在后面（去重保序）。

    ⚠ **顺序有意义**：让位是按声明顺序找第一个空闲字符，工单给的那几个是"更想用的
    助记字符"，池子只在它们都被占时才轮到。两套顺序都实测过 `|S| <= 6` 全子集
    零撞车（`.scratch/hwcheck-specialize/probe-console-combos.py`）。
    """
    return list(dict.fromkeys([*specific, *POOL]))


UNBOARDED = (
    "**未上板**：本格的结论只到「编译矩阵绿 + 驱动实现的返回码判据」，真机上板验证还没做"
    "（与库内 manifest 的口径一致）。实测差异优先于本页参考值。"
)
# ⚠ servo 的 manifest **没有**「未上板」这句（评审核对过）——它的如实口径只能到"没有上板记录"
UNBOARDED_SERVO = (
    "**未上板**：库内 servo 的 manifest **没有上板验证记录**，本格同样只到「编译矩阵绿 + "
    "驱动换算常量与实现一致」——**舵机到底能不能转，本页证不了**（纯写执行件，见上）。"
    "实测差异优先于本页参考值。"
)

# ---------------------------------------------------------------------------
# hx711 × stm32 / mspm0
# ---------------------------------------------------------------------------
HX_READ = {
    "items": [
        {"expression": "raw",
         "unit": "24bit 偏移值（≈8388608 = 零点；**不是克数**）"},
        {"expression": "(int)raw - 8388608",
         "unit": "有符号计数（加砝码应单调变化；与上面那行是同一个采样）"},
    ]
}
HX_NOTE_COMMON = (
    "**探头到底证明了什么**：探头 = **`hx711_read_raw()` 读回一个非 0 的数**，含义是"
    "「**DT 数据就绪通路是活的 + 一次采样真的出来了**」。它**不证明重量准**——克换算要"
    "先**去皮**再按每只秤的传感器曲线标定（`HX711_GAP_VALUE`，默认 207.00 只是立创的"
    "示例值），所以本页**故意不显示克数**。"
)
HX_NOTE_TIMING = (
    "⚠ **本件最硬的一条：同一节里 `hx711_read_raw()` 只能读一次**。驱动只等 **20ms**"
    "（2000×10us），而模块默认 **10SPS = 100ms** 才出一个新数据：读完 24 位 + 第 25 个脉冲后"
    "DOUT 立刻回高，**下一次读必然超时返 0**。而 `hx711_init()` **内部就先读一次**（空秤去皮）"
    "⇒ **init 之后紧接着读 = 必 FAIL**。所以本格的形状是「先等够时间、再读一次、"
    "把那次采样存进 `raw` 给读数两行复用」——**读数段不再调 `read_raw()` / `get_gram()`**"
    "（再调就是又一次超时返 0）。"
)
HX_CONSOLE = {
    "command": "w",
    "candidates": candidates("n", "z"),
    "description": "HX711 称重：重读原始计数（空秤≈8388608；每次读相隔≥100ms）",
}
HX_NOTE_STM32 = [
    HX_NOTE_COMMON,
    HX_NOTE_TIMING,
    "判 FAIL 时按返回码排查：**`raw == 0`** = 20ms 内没等到 DT 拉低，按嫌疑从大到小——"
    "① 没接 / 线断 / SCK·DT 插反；② **刚上电 400ms 内**（模块自己也要启动）；"
    "③ **上一次读还没过 100ms**（10SPS 的转换周期）。⚠ 探头判 FAIL 会 **return**，"
    "后面的读数就不打印了。",
    "**0 是个歧义词**（本单不修的驱动缺陷）：`count ^ 0x800000` 在 `count == 0x800000` 时也返 0，"
    "与超时的 0 **不可分**——所以「读到 0」既可能是没接，也可能是秤正好在转换中点。"
    "本格用 `(raw != 0) ? 1 : 0` 当判据，等于承认这个含糊：**能拿到非 0 就说明通路活着**。",
    "正常范围参考：**空秤 ≈ 8388608**（上面第一行），第二行是相对零点的有符号计数（空秤≈0）；"
    "加砝码应**单调变化**、噪声在 **±几百~几千计数**之间；**手指按一下秤盘**计数就会明显地动。"
    "想把读数换算成克：先 `hx711_tare()` 去皮，再按实测标定改 `HX711_GAP_VALUE`"
    "（**float 宏，不能进整数读数**，所以本页不给克数）。",
    "接线坑：默认 **SCK = PB5 / DT = PB0**；SCK 空闲低、DT 空闲高（模块内部上拉）。"
    "PB5 与 `motor` 的编码器 A 相、PB0 与电机方向脚默认重叠（同选经引脚绑定消解）。",
    "**本单不修的驱动缺陷（如实提示，只记录不改库）**：① 20ms 超时**短于** 10SPS 的 100ms "
    "转换周期，而 init/tare 都是「消费一次采样」的读却**没有任何节流 / 重试**（recon-02 §4-5）；"
    "② 上面说的「0 是歧义词」（§4-6）。",
    UNBOARDED,
]
HX_NOTE_MSPM0 = [
    HX_NOTE_COMMON,
    HX_NOTE_TIMING,
    "判 FAIL 时按返回码排查：**`raw == 0`** = 20ms 内没等到 DT 拉低——① 没接 / 线断 / 插反；"
    "② 刚上电 400ms 内；③ 上一次读还没过 100ms。⚠ 探头判 FAIL 会 **return**，读数就不打印了。",
    HX_NOTE_STM32[3],
    "**平台差异 / 接线（本格的形状就是被它逼出来的）**：引脚 = SysConfig 实例 HX711："
    "**SCK = PA28 / DT = PA31**（DT 内部上拉；SCK 空闲低、DT 空闲高）。"
    "⚠ **PA28 / PA31 与 `jy61p` / IMU601 / `sht30` / FINGERPRINT 的默认脚重叠**"
    "（低频采集池共用这两根线）——同一个物理脚只能接一件器件，同选经引脚绑定消解。"
    "⚠ 模块头注释 `hx711.h` 里写的 PB24/PB8 是**过期读数**（那是历史默认），"
    "以 syscfg / manifest 的 **PA28/PA31** 为准（本单不改库，已记账）。"
    "⚠ 本平台（mspm0）**母版没有 .h**：`delay_ms` 出现在 `init` / `probe` / `read` 的**任何一处"
    "都是构建期红**，唯一放行它的是 **`prereq`**——所以本格把「调 init 去皮 → 等 500ms → 读一次」"
    "整条序列放进 `prereq`、`init` 段留空（`bh1750` 同款先例）。代价如实说：**冷启动那一次 "
    "`hx711_init()` 本身可能超时**（`s_tare` 留 0 ⇒ 克换算不可用），**第一遍可能读到 0 —— "
    "敲一次复测字符再看**。",
    HX_NOTE_STM32[5],
    UNBOARDED,
]

HX711 = {
    "stm32": {
        "include": {"headers": ["hx711_stm32.h", "pin_config.h", "ml_delay.h"]},
        "locals": {"declarations": ["uint32_t raw = 0"]},
        "init": {"calls": ["hx711_init()"]},
        "probe": {"calls": ["(delay_ms(500), raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"],
                  "expect": "1"},
        "read": HX_READ,
        "console": HX_CONSOLE,
        "note": {"lines": HX_NOTE_STM32},
    },
    "mspm0": {
        "include": {"headers": ["hx711.h"]},
        "locals": {"declarations": ["uint32_t raw = 0"]},
        "prereq": {"calls": ["hx711_init()", "delay_ms(500)"]},
        "probe": {"calls": ["(raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"], "expect": "1"},
        "read": HX_READ,
        "console": HX_CONSOLE,
        "note": {"lines": HX_NOTE_MSPM0},
    },
}

# ---------------------------------------------------------------------------
# joystick × stm32 / mspm0（照 key 先例：**没有探头**）
# ---------------------------------------------------------------------------
JOY_READ = {
    "items": [
        {"expression": "joystick_read_x_percent()",
         "unit": "X 轴 0-100%（不推杆应≈50；推到左右两端应接近 0 / 100）"},
        {"expression": "joystick_read_y_percent()",
         "unit": "Y 轴 0-100%（不推杆应≈50；推到上下两端应接近 0 / 100）"},
        {"expression": "joystick_read_sw()",
         "unit": "摇杆帽按键：1 = 按下 / 0 = 松开（按住它再复读一次应看到 1）"},
    ]
}
JOY_CONSOLE = {
    "command": "i",
    "candidates": candidates("n", "t"),
    "description": "双轴摇杆：重读 X/Y 百分比与按键（推一下摇杆看数变）",
}
JOY_NO_PROBE = (
    "**本件没有读取型探头，这是如实记账、不是漏测**：摇杆既没有身份寄存器，也没有"
    "「恒等于某值」的状态位——唯一的数字量 SW 是**按键**（与库内 `key` 同一口径："
    "「人按才有意义」的输入，学生一上手就按着、或接线把 SW 拉低，静态电平探头就会**假 FAIL**）。"
    "所以照 `key` 的先例**不写 `probe` 段**：板上会记一笔「未判定」，测量动作照跑、读数照打，"
    "结论按下面几条自己判。"
)
JOY_PHENOMENON = (
    "渲染器会给没探头的件打一句通用话术（「本件没有可读的身份 / 状态寄存器…（灯闪 / 屏亮）」）"
    "——**本件既没灯也没屏，那句话在这里就是「看读数」**：推摇杆看两个百分比跟不跟着变、"
    "按住摇杆帽看按键那行变不变 1。"
)
JOY_NOTE_STM32 = [
    JOY_NO_PROBE,
    JOY_PHENOMENON,
    "判「有没有坏」的实操：**推杆看数**——X/Y 两行应随推杆单调变化，松手回中；"
    "推到一端应接近 **0 或 100**；按住摇杆帽，按键那行应变 **1**。三样都对 = 这根摇杆是好的。"
    "⚠ **中点的 50% 是「页面 / 厂商口径的理论值」，库内明确写着没实测**（本件 manifest 末句"
    "「未上板」，stm32 条目还写着「中心值 / 死区真机校准留后续」）——所以**别拿「读 48 还是 52」"
    "当故障**，两只摇杆的中点和死区本来就不一样。",
    "失败模式四条：**恒 0** —— 读到 0 有两种可能：真的把杆推到端点（合法读数），或者模拟通路"
    "没工作（见下条 stm32 的 0 与 mspm0 的 0 含义不同）；**恒定值** —— 推杆时数字一动不动 "
    "= X/Y 那两路没接对（或接到了别的脚）；**超时** —— 本平台 `adc_get` 没有显式超时（母版实现），"
    "读不出来就是读不出来，不会报错；**上电第一遍失败** —— 无判定可失败，但第一遍读数抖动属正常。",
    "**平台差异**：stm32 = **X = PA1（ADC_Channel_1）/ Y = PA0（ADC_Channel_0）/ SW = PA10**；"
    "mspm0 = **X = PA26（ADC12_0 MEM1）/ Y = PA25（MEM2）/ SW = PA9**——**引脚与通道号完全不同，"
    "两边的配方段不能照抄**。⚠ 本平台 PA0/PA1 **同时是 `motor` 的两路 PWM 主脚**（TIM2_CH1/CH2）、"
    "PA10 与十来件共享：**同一个物理脚只能接一件器件**，同选经引脚绑定消解。"
    "⚠ 还与 `adc` 模块共用 ADC1 的 CH0/CH1 —— 与 Y/X 是**同一对物理脚**（顺序调用不串）。",
    UNBOARDED,
]
JOY_NOTE_MSPM0 = [
    JOY_NO_PROBE,
    JOY_PHENOMENON,
    JOY_NOTE_STM32[2],
    "失败模式四条：**恒 0** —— ⚠ **本平台有一个已知缺陷会让 X/Y 读数很可能恒 0**（见下条），"
    "而 **0% 恰好又是「杆推到端点」的合法读数** ⇒ **学生分不清「坏了」和「推到端点」**；"
    "**恒定值** —— 推杆时数字一动不动 = X/Y 那两路没接对或接到了别的脚；**超时** —— 见下条；"
    "**上电第一遍失败** —— 无判定可失败，第一遍读数抖动属正常。",
    "**平台差异**：mspm0 = **X = PA26（ADC12_0 的 MEM1）/ Y = PA25（MEM2）/ SW = PA9**；"
    "stm32 = X = PA1 / Y = PA0 / SW = PA10——**引脚与通道号完全不同**。"
    "本平台的 ADC12_0 是 **8 槽 sequence（startAdd=0 / endAdd=7，槽位用满）**，"
    "摇杆只占 MEM1/MEM2；引脚配置归 **SysConfig 实例**（ADC12_0 + JOYSTICK）+ `SYSCFG_DL_init()`。"
    "⚠ PA26 / PA25 / PA9 各自与十来件默认脚重叠（含 `huidu` / `xunji` / `pid` / 无线串口等），"
    "**同一个物理脚只能接一件器件**。⚠ 本平台（mspm0）**母版没有 .h**：`init` / `probe` / `read` 里"
    "**只能出现本模块头里的名字**——`JOYSTICK_ADC_MAX` / `JOYSTICK_ADC_SAMPLES` 这类只在 `.c` 里"
    "定义的名字、以及 `delay_ms` / `gpio_get` / `DL_*`，写进这三段都会**构建期红**。",
    "**本单不修的驱动缺陷（如实提示，只记录不改库）**：本平台的 ADC 忙等超时判据用的是"
    "**「自旋圈数」而不是时间**（50 圈寄存器轮询 ≈ 几微秒，而一次转换要 ≈1ms）⇒ 第一次采样"
    "就会提前返回，`joystick_read_x/y()` **很可能恒 0**（推断，需上板复核，D2）。"
    "同实例的 `adc` 模块用的是无超时忙等，它的读数是好的——**这不是板子坏，是这一个驱动的超时口径问题**。"
    "另：三处文档对 sequence 槽数的说法互不相同（manifest / 头注释写四通道、syscfg 是 8 槽），"
    "本页按 **syscfg 的事实**写。",
    UNBOARDED,
]

JOYSTICK = {
    "stm32": {
        "include": {"headers": ["joystick_stm32.h", "pin_config.h"]},
        "init": {"calls": ["joystick_init()"]},
        "read": JOY_READ,
        "console": JOY_CONSOLE,
        "note": {"lines": JOY_NOTE_STM32},
    },
    "mspm0": {
        "include": {"headers": ["joystick.h"]},
        "init": {"calls": ["joystick_init()"]},
        "read": JOY_READ,
        "console": JOY_CONSOLE,
        "note": {"lines": JOY_NOTE_MSPM0},
    },
}

# ---------------------------------------------------------------------------
# servo × stm32 / mspm0（纯写执行件：只有动作，没有判定）
# ---------------------------------------------------------------------------
SERVO_READ = {
    "items": [
        {"expression": "SERVO_ANGLE_MAX",
         "unit": "角度满量程 度（越界自动钳到端点；**常量回显，不是测量值**）"},
        {"expression": "SERVO_FREQ_HZ",
         "unit": "控制频率 Hz（50 = 20ms 周期；**常量回显**）"},
        {"expression": "SERVO_PULSE_US(90)",
         "unit": "中位脉宽 µs（500 = 0° / 1500 = 90° / 2500 = 180°；**换算表回显**）"},
    ]
}
SERVO_CONSOLE = {
    "command": "d",
    "candidates": candidates("v", "i"),
    "description": "舵机：重跑一遍角度扫描（盯着舵机臂动没动）",
}
SERVO_NO_PROBE = (
    "**本件没有读取型探头，这是如实记账、不是漏测**：舵机是**纯写执行件**——驱动只有 "
    "`servo_init` / `servo_set_angle` 两个 void 接口，没有读回；定时器 / 比较寄存器也不是"
    "身份寄存器。所以 `probe` 段放的是**不带期望值的动作**（照 `xunji` / `sr04` 先例）："
    "板上会记一笔「未判定」，动作照跑。**它转没转，只有眼睛看舵机臂。**"
)
SERVO_READ_CAVEAT = (
    "⚠ **下面三行读数是「驱动的换算表回显」，不是测量值**：它们证的是「这套换算常量是这样」，"
    "**不证明舵机真的转了**。别把「读数正常」读成「舵机好」。"
)
SERVO_COMMON_TAIL = [
    SERVO_READ_CAVEAT,
    "正常范围参考：**0° / 90° / 180° 对应脉宽 0.5ms / 1.5ms / 2.5ms**（50Hz、20ms 周期）。"
    "想确认「它真的在动」：复测时**盯舵机臂**——按本格的扫描顺序，应看到舵机臂**一段一段地"
    "转到指定角度**（stm32 是 0°→90°→180°→90° 四段，mspm0 是 0°→90°→0° 三段），"
    "而不是纹丝不动或只抖一下。",
    "**上电瞬间会看到什么**：SysConfig 生成的 PWM 初值是「不出脉冲」，而 `servo_init()` 一跑就"
    "按 **0°** 配好并启动 ⇒ **舵机臂会猛地转到 0° 位置**。**这是正常现象，不是坏了。**",
    "**本单不修的驱动缺陷（如实提示，只记录不改库）**：`servo_init(servo_id, channel)` 与 "
    "`servo_set_angle(servo_id, angle)` 的 `servo_id` / `channel` 两个形参**在两侧实现里都被 "
    "`(void)` 丢弃**——也就是说「多舵机 / 换通道」是**假接口**，本驱动实际只能驱动被绑定的那一路。",
]
SERVO_NOTE_STM32 = [
    SERVO_NO_PROBE,
    "判「有没有坏」的实操：复测一遍，**盯舵机臂**——① 完全不动：先查 **信号线接在 PB6 上**"
    "（见下条接线）、再查**舵机的独立供电**（舵机堵转电流可达安培级，**别从板子 3V3 供**）；"
    "② 抖动 / 只往一个方向跑：多半是供电不足；③ 转到某个角度就卡住：机械限位或舵机本身坏了。"
    "⚠ 探头（这里是动作）跑完**不写判定**，所以**读数是照打的**。",
] + SERVO_COMMON_TAIL[:3] + [
    "**平台差异 / 接线**：stm32 侧 PWM = **TIM4_CH1 = PB6**（1MHz 计数、ARR=19999 ⇒ 20ms）。"
    "⚠ **PB6 与 `pid` 的 GRAY_D7、`rc522` 的 SCK、`lcd` / `oled` 的 SPI DC 默认脚重叠**——"
    "同一个物理脚只能接一件器件，同选经引脚绑定消解。",
    SERVO_COMMON_TAIL[3],
    UNBOARDED_SERVO,
]
SERVO_NOTE_MSPM0 = [
    SERVO_NO_PROBE,
    "判「有没有坏」的实操：复测一遍，**盯舵机臂**——① 完全不动：先查**信号线接在 PA7 上**、"
    "再查**舵机的独立供电**（**别从板子 3V3 供**）；② 抖动 / 只往一个方向跑：多半是供电不足；"
    "③ 转到某个角度就卡住：机械限位或舵机本身坏了。⚠ 本格**只扫 0° → 90° → 0°**，"
    "**故意不扫 180°**（见下面的驱动缺陷），别把「大角度不动」读成舵机坏。",
] + SERVO_COMMON_TAIL[:3] + [
    "**平台差异 / 接线**：mspm0 侧 PWM = **TIMG8 C0 = PA7**（SysConfig 实例 `SERVO_PWM`，"
    "周期在运行时按实例时钟算）。⚠ **PA7 与 `motor` 的 BIN2、`ds18b20` 的 DATA、`rc522` 的 CS "
    "默认脚重叠**——同一个物理脚只能接一件器件。⚠ 本平台（mspm0）**母版没有 .h**："
    "`init` / `probe` / `read` 里**只能出现本模块头（`servo.h`）里的名字**——`delay_ms` 写进 "
    "`init` / `probe` 会**构建期红**，所以本格把整条动作序列放进 **`prereq`**、`init` 段留空"
    "（这是形状被规矩逼出来的，不是随手选择）。",
    "**本单不修的驱动缺陷（如实提示，只记录不改库）**：本平台 `servo_period()` 算出的周期"
    "（`SERVO_PWM_INST_CLK_FREQ / 50`）**超过 16 位定时器量程**，而 `DL_Timer_setLoadValue` "
    "不做钳位 ⇒ **50Hz 很可能出不来、大角度（≈96° 以上）输出恒高**（推断，需上板复核，D1）。"
    "**这正是本格只扫到 90° 的原因**：扫 180° 可能完全不动，学生会误判成舵机坏了。"
    "同库的 `step_motor` 对同一件事**显式钳了位**（`period < 65536 ? period : 65535`），"
    "`servo` 没有这一步。",
    SERVO_COMMON_TAIL[3],
    UNBOARDED_SERVO,
]

SERVO = {
    "stm32": {
        "include": {"headers": ["servo.h"]},
        "init": {"calls": ["servo_init(0, 0)"]},
        "probe": {"calls": ["servo_set_angle(0, 0)", "delay_ms(600)",
                            "servo_set_angle(0, 90)", "delay_ms(600)",
                            "servo_set_angle(0, 180)", "delay_ms(600)",
                            "servo_set_angle(0, 90)"]},
        "read": SERVO_READ,
        "console": SERVO_CONSOLE,
        "note": {"lines": SERVO_NOTE_STM32},
    },
    "mspm0": {
        "include": {"headers": ["servo.h"]},
        "prereq": {"calls": ["servo_init(0, 0)", "delay_ms(600)", "servo_set_angle(0, 90)",
                             "delay_ms(600)", "servo_set_angle(0, 0)"]},
        "read": SERVO_READ,
        "console": SERVO_CONSOLE,
        "note": {"lines": SERVO_NOTE_MSPM0},
    },
}

# ---------------------------------------------------------------------------
# relay × stm32 / mspm0（纯写执行件：只有动作，没有判定）
# ---------------------------------------------------------------------------
RELAY_READ_STM32 = {
    "items": [
        {"expression": "gpio_get(RELAY_GPIO, RELAY_PIN)",
         "unit": "引脚实际电平（1 = 高 = 断开 = 正常收尾；0 = 还在吸合）"},
        {"expression": "RELAY_ON_LEVEL",
         "unit": "吸合电平（0 = 低电平吸合；实物高电平吸合才改成 1）"},
    ]
}
RELAY_READ_MSPM0 = {
    "items": [
        {"expression": "RELAY_ON_LEVEL",
         "unit": "吸合电平（0 = 低电平吸合；实物高电平吸合才改成 1）"},
    ]
}
RELAY_CONSOLE = {
    "command": "e",
    "candidates": candidates("n", "z"),
    "description": "继电器：吸合 0.5 秒再断开（听咔哒声 / 看模块指示灯）",
}
RELAY_NO_PROBE = (
    "**本件没有读取型探头，这是如实记账、不是漏测**：继电器是**纯写执行件**——驱动只有 "
    "`relay_init` / `relay_set` 两个 void 接口，没有读回，也没有身份寄存器。所以 `probe` 段放的是"
    "**不带期望值的动作**（吸合 → 等 0.5 秒 → 断开，照 `xunji` 先例）：板上会记一笔「未判定」，"
    "动作照跑。**它到底吸没吸，听咔哒声、看模块上的指示灯。**"
)
RELAY_LOOK = (
    "渲染器会给没探头的件打一句通用话术（「本件没有可读的身份 / 状态寄存器…（灯闪 / 屏亮）」）"
    "——**本件既没灯也没屏（指板子上）**，那句话在这里就是「**听继电器咔哒一声、看模块自己的"
    "指示灯亮灭**」：断开 → 吸合 → 断开的动作序列里，应听到一声「咔哒」、模块灯亮一下再灭。"
)
RELAY_TAIL = [
    "**收尾一定回到断开**：这一节的动作最后停在 `relay_set(0)`——**别让负载一直吸着**"
    "（线圈长期通电会发热，接市电负载时更不该长时间吸合）。",
    "正常范围参考：**吸合 = 听到一声清脆的「咔哒」+ 模块指示灯亮**（光耦隔离，MCU 侧只驱动"
    "光耦）；不吸合时既没声也没灯。**模块特性**：5V 工作、光耦隔离、可控 250V/10A AC 与 30V/10A DC。"
    "⚠ **继电器是感性负载**：接高压 / 市电负载之前先在**空载**下验这一节，别拿它当第一次试电的开关。",
    "**本单不修的驱动缺陷（如实提示，只记录不改库）**：接口只有 `relay_init()` / "
    "`relay_set(0|1)`——**没有** `relay_on` / `relay_off` / `relay_toggle`、**没有**通道宏"
    "（单路）。凭常识写 `relay_on()` 会构建期红。",
    UNBOARDED,
]
RELAY_NOTE_STM32 = [
    RELAY_NO_PROBE,
    RELAY_LOOK,
    "⚠ **上电 / 复位瞬间可能听到一声咔哒——这不是坏了**（本平台特有，最容易被吓到的一条）："
    "`relay_init()` 先 `gpio_init(..., OUT_PP)`（母版这个函数**只写 CRL/CRH、不写 ODR**），"
    "而该引脚复位后 **ODR 位 = 0 = 低电平 = 吸合档** ⇒ 这几条指令之间**PB4 会输出低电平**，"
    "随后才被 `relay_set(0)` 拉高断开。也就是说：**上电那一下继电器可能吸合几微秒**。"
    "mspm0 侧没有这个问题（syscfg 初值就是断开 + init 亦置断开，双保险）。",
    "**平台差异 / 接线**：stm32 默认 OUT = **PB4**。⚠ **PB4 在 F103 上是 NJTRST / JTAG 复用脚**："
    "当普通 GPIO 用需要释放 JTAG（保留 SWD），而**库内代码没有动 `SWJ_CFG`**——ST-Link 走 SWD "
    "下载不受影响；万一**继电器完全不动、上面那行引脚电平读数也不跟着变**，先把 OUT 换到"
    "一根普通 GPIO 脚再试。PB4 还与 `motor` 编码器方向输入、`hc05` KEY、`lcd`/`oled` 的 SPI SCL、"
    "`nrf24l01` MISO、`rc522` MOSI 等默认脚重叠（同选经引脚绑定消解）。",
    "读数怎么看：上面第一行是**真回读**——`gpio_get` 直接读 PB4 的**实际电平**："
    "**1 = 高 = 断开 = 动作正常收尾**；读到 **0** 说明动作结束后它**还在吸合**（驱动 / 接线有问题，"
    "或者你把负载接在了常闭触点上）。第二行是**极性宏回显**（不是测量值）："
    "本模块「低电平吸合」，所以 `RELAY_ON_LEVEL = 0`；换成高电平吸合的模块才改成 1。",
    RELAY_TAIL[0],
    RELAY_TAIL[1],
    RELAY_TAIL[2],
    UNBOARDED,
]
RELAY_NOTE_MSPM0 = [    RELAY_NO_PROBE,
    RELAY_LOOK,
    "**本平台没有「上电咔哒」这个问题**：SysConfig 里这个脚的初值就是**断开**，`relay_init()` "
    "又置一次断开，双保险 ⇒ **上电时继电器不会吸合**（stm32 侧因为母版 `gpio_init` 不写 ODR，"
    "会有一下——那是另一平台的现象）。",
    "**平台差异 / 接线**：mspm0 默认 OUT = **PA1**（引脚配置归 SysConfig 实例 `RELAY` + "
    "`SYSCFG_DL_init()`）。⚠ **PA1 与 `ml_mpu6050` 的 I2C_0 SCL、`i2c_probe` 的 SCL、"
    "`gp2y1014au` 的 LED 默认脚重叠**——同一个物理脚只能接一件器件，同选经引脚绑定消解。"
    "⚠ 本平台（mspm0）**母版没有 .h**：`init` / `probe` / `read` 里**只能出现本模块头里的名字**"
    "——`delay_ms` / `gpio_get` / `DL_GPIO_readPins` 写进这三段都会**构建期红**，所以本格把整条"
    "动作序列放进 **`prereq`**（形状被规矩逼出来的，`bh1750` / `hx711` 同款先例）。",
    "⚠ **本格的读数只有一行是诚实的**：本平台的 `relay.h` 里**没有**引脚宏（引脚名是 SysConfig "
    "生成的 `RELAY_PORT` / `RELAY_RELAY_OUT_PIN`，**配方里写不了**）、驱动也没有 `gpio_get` "
    "这类回读 ⇒ **本平台连引脚电平都读不了**，所以只有「吸合电平」这一行常量回显。"
    "**不硬凑**一行 `DL_GPIO_readPins(...)` 假装测了——那个名字在配方里是构建期红。",
    RELAY_TAIL[0],
    RELAY_TAIL[1],
    RELAY_TAIL[2],
    UNBOARDED,
]

RELAY = {
    "stm32": {
        "include": {"headers": ["relay_stm32.h", "pin_config.h", "ml_delay.h"]},
        "init": {"calls": ["relay_init()"]},
        "probe": {"calls": ["relay_set(1)", "delay_ms(500)", "relay_set(0)"]},
        "read": RELAY_READ_STM32,
        "console": RELAY_CONSOLE,
        "note": {"lines": RELAY_NOTE_STM32},
    },
    "mspm0": {
        "include": {"headers": ["relay.h"]},
        "prereq": {"calls": ["relay_init()", "relay_set(1)", "delay_ms(500)", "relay_set(0)"]},
        "read": RELAY_READ_MSPM0,
        "console": RELAY_CONSOLE,
        "note": {"lines": RELAY_NOTE_MSPM0},
    },
}

NEW = {"hx711": HX711, "joystick": JOYSTICK, "servo": SERVO, "relay": RELAY}

text = RECIPES.read_text(encoding="utf-8")
document = json.loads(text)
for slug, entry in NEW.items():
    document[slug] = entry
newline = "\r\n" if "\r\n" in text else "\n"
body = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline) + newline
RECIPES.write_bytes(body.encode("utf-8"))
print(f"已写入 {len(NEW)} 件：{sorted(NEW)}")
print(f"总件数 {len([k for k, v in document.items() if isinstance(v, dict)])}，"
      f"总格数 {sum(len(v) for v in document.values() if isinstance(v, dict))}")
