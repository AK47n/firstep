# K230 视觉副控脚本（CanMV main.py）——拷贝到 TF 卡根目录（替换同名文件），
# K230 上电自动运行（CanMV 开机自启动 main.py）。
#
# 闭环：sensor 采图 → find_blobs 色块追踪 → 组 CSV 帧 → UART 发给主控。
# 主控侧解析由 coord_detect 模块提供（生成器按依赖自动挂上），两侧帧契约
# 同源——下面两个帧常量与串口波特率由生成器渲染占位符注入，不要手改字面量
# （改了就和主控解析对不齐）。
#
# 串口接线（参考库 13_与天猛星串口通信 例程同款）：
#   K230 11 脚 = UART2 TXD → 主控坐标检测串口 RX
#   K230 12 脚 = UART2 RXD → 主控坐标检测串口 TX（本脚本只发不收，可留空）
#
# 素材：参考库 k230资料/code/05色块追踪与线段识别（find_blobs）+
# 13_与天猛星串口通信（FPIOA + UART 发送）。

import os
import time

from machine import FPIOA
from machine import UART
from media.media import MediaManager
from media.sensor import Sensor

# ---- 帧契约（生成器从契约单源渲染注入；与主控 coord_detect 解析严格一致）----
FRAME_FORMAT = '{{coord_frame_format}}'   # B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>
NO_DETECT_FRAME = '{{no_detect_frame}}'  # N（本帧未检测到目标）

# ---- 颜色阈值（LAB：Lmin,Lmax,Amin,Amax,Bmin,Bmax；现值为红色系）----
# 换跟踪颜色就改这里；现场标定可用参考库 14_脱机调整阈值 例程取数。
COLOR_THRESHOLD = (41, 57, 31, 83, 13, 71)

sensor = None

try:
    # FPIOA 串口映射：11 = UART2 TXD、12 = UART2 RXD（与主控 RX/TX 交叉）
    fpioa = FPIOA()
    fpioa.set_function(11, FPIOA.UART2_TXD)
    fpioa.set_function(12, FPIOA.UART2_RXD)
    uart = UART(UART.UART2, {{uart_baudrate}})

    # sensor 初始化（分辨率/参数照 05 色块追踪例程）
    sensor = Sensor(width=1024, height=768)
    sensor.reset()
    sensor.set_framesize(width=1024, height=768)
    sensor.set_pixformat(Sensor.RGB565)
    MediaManager.init()
    sensor.run()

    while True:
        os.exitpoint()
        img = sensor.snapshot()

        # 色块追踪（参数照 05 例程：ROI 640x640、步长 5、像素阈值 3000、合并）
        blobs = img.find_blobs([COLOR_THRESHOLD], False, (0, 0, 640, 640),
                               x_stride=5, y_stride=5, pixels_threshold=3000,
                               margin=True)
        if blobs:
            blob = max(blobs, key=lambda b: b.w() * b.h())  # 多色块取最大
            frame = FRAME_FORMAT.format(
                cx=blob.cx(),
                cy=blob.cy(),
                confidence=1.0,  # 色块识别无置信度，恒 1.0（识别类能力后续给真值）
                x1=blob.x(),
                y1=blob.y(),
                x2=blob.x() + blob.w(),
                y2=blob.y() + blob.h(),
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
