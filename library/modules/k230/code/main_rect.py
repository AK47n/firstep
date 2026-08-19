# K230 矩形识别脚本（CanMV main.py）——拷贝到 TF 卡根目录（替换同名文件），
# K230 上电自动运行（CanMV 开机自启动 main.py）。
#
# 闭环：sensor 采图 → 灰度二值化 → find_rects 矩形检测 → 组 CSV 帧 →
# UART 发给主控。主控侧解析由 coord_detect 模块提供（生成器按依赖自动挂上），
# 两侧帧契约同源——下面两个帧常量与串口波特率由生成器渲染占位符注入，不要
# 手改字面量（改了就和主控解析对不齐）。
#
# 串口接线（与色块模板同款）：
#   K230 11 脚 = UART2 TXD → 主控坐标检测串口 RX
#   K230 12 脚 = UART2 RXD → 主控坐标检测串口 TX（本脚本只发不收，可留空）
#
# 素材：参考库 k230资料/codecao/04矩形识别与常见的图像处理（find_rects）+
# 13_与天猛星串口通信（FPIOA + UART 发送）。检测结果的决策消费归生成骨架。

import os
import time

from machine import FPIOA
from machine import UART
from media.media import MediaManager
from media.sensor import Sensor

# ---- 帧契约（生成器从契约单源渲染注入；与主控 coord_detect 解析严格一致）----
FRAME_FORMAT = '{{coord_frame_format}}'   # B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>
NO_DETECT_FRAME = '{{no_detect_frame}}'  # N（本帧未检测到目标）

# ---- 二值化阈值（灰度 0-255：目标与背景的明暗分界；现值为 04 例程取数）----
# 现场标定：用 CanMV IDE 阈值工具观察目标/背景灰度，改这里即可，不用改代码。
BINARY_THRESHOLD = (82, 212)
# find_rects 面积阈值（像素）：目标太小 / 噪声矩形太多时调大
RECTS_THRESHOLD = 10000

sensor = None

try:
    # FPIOA 串口映射：11 = UART2 TXD、12 = UART2 RXD（与主控 RX/TX 交叉）
    fpioa = FPIOA()
    fpioa.set_function(11, FPIOA.UART2_TXD)
    fpioa.set_function(12, FPIOA.UART2_RXD)
    uart = UART(UART.UART2, {{uart_baudrate}})

    # sensor 初始化（分辨率照 04 矩形识别例程）
    sensor = Sensor(width=640, height=640)
    sensor.reset()
    sensor.set_framesize(width=640, height=640)
    sensor.set_pixformat(Sensor.RGB565)
    MediaManager.init()
    sensor.run()

    while True:
        os.exitpoint()
        img = sensor.snapshot()

        # 矩形识别：灰度 → 二值化 → find_rects（参数照 04 例程）
        gray = img.to_grayscale(copy=True)
        gray.binary([BINARY_THRESHOLD])
        rects = gray.find_rects(threshold=RECTS_THRESHOLD)
        if rects:
            # 多矩形取面积最大者，四个角点 → 外接框 → B 帧
            rect = max(rects, key=lambda r: r.w() * r.h())
            corners = rect.corners()
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            frame = FRAME_FORMAT.format(
                cx=(x1 + x2) // 2,
                cy=(y1 + y2) // 2,
                confidence=1.0,  # 传统视觉无置信度，恒 1.0
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
            )
            uart.write(frame + "\n")
        else:
            uart.write(NO_DETECT_FRAME + "\n")

        time.sleep_ms(50)  # 约 20 帧/秒，主控中断收帧无压力

except KeyboardInterrupt as e:
    print("用户停止: ", e)
except BaseException as e:
    print("异常: ", e)
finally:
    if isinstance(sensor, Sensor):
        sensor.stop()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
    time.sleep_ms(100)
    MediaManager.deinit()
