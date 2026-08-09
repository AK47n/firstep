# -*- coding: utf-8 -*-
'''
钢珠检测 + 串口发送
功能：K230 实时检测钢珠位置，将钢珠的【中心坐标、置信度、边界框】通过 UART2 发送给 STM32

与 det_uart.py（数字识别+串口）的区别：
    - 只检测一个钢珠（取置信度最高的检测结果），数字可能有多个
    - 协议更简洁：每帧一行 CSV，无帧头/目标数量统计
    - 无检测时发送 "N" 告知 STM32 钢珠丢失

使用方法：
    1. 复制此文件到 K230 SD 卡 /sdcard/ 目录
    2. 确保 SD 卡已有 mp_deployment_source 文件夹（含钢珠检测模型和 deploy_config.json）
    3. 接线：K230 Pin8 (IO3/TX1) → STM32 UART1 RX
              K230 Pin10 (IO4/RX1) → STM32 UART1 TX
              GND ↔ GND
    4. 上电自动运行（或通过 IDE 运行）

协议格式（115200, 8N1）：
    检测到钢珠:  B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>\n
    未检测到:    N\n

    字段说明：
    - B/N:  数据类型标识（B=钢珠数据，N=无检测）
    - cx:   钢珠中心 X 坐标（图像空间 1280x720，像素）
    - cy:   钢珠中心 Y 坐标（图像空间 1280x720，像素）
    - confidence: 置信度（0.00~1.00）
    - x1,y1: 边界框左上角坐标
    - x2,y2: 边界框右下角坐标
'''

import os, gc
from libs.PlatTasks import DetectionApp
from libs.PipeLine import PipeLine
from libs.Utils import *

from machine import FPIOA
from machine import UART

# ==================== UART 初始化 ====================
# 使用 UART1：K230 Pin8(IO3/TX1) → STM32 UART1 RX
#              K230 Pin10(IO4/RX1) → STM32 UART1 TX
#              GND ↔ GND
fpioa = FPIOA()
fpioa.set_function(3, FPIOA.UART1_TXD)
fpioa.set_function(4, FPIOA.UART1_RXD)
uart1 = UART(UART.UART1, 115200)

# ==================== 模型配置 ====================
display_mode = "lcd"            # K230 LCKFB 版本使用 ST7701 LCD
rgb888p_size = [1280, 720]

root_path = "/sdcard/mp_deployment_source/"
deploy_conf = read_json(root_path + "/deploy_config.json")
kmodel_path = root_path + deploy_conf["kmodel_path"]
labels = deploy_conf["categories"]
confidence_threshold = deploy_conf["confidence_threshold"]
nms_threshold = deploy_conf["nms_threshold"]
model_input_size = deploy_conf["img_size"]
nms_option = deploy_conf["nms_option"]
model_type = deploy_conf["model_type"]
anchors = []
if model_type == "AnchorBaseDet":
    anchors = deploy_conf["anchors"][0] + deploy_conf["anchors"][1] + deploy_conf["anchors"][2]

inference_mode = "video"
debug_mode = 0

# ==================== 初始化 Pipeline 和检测应用 ====================
pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode)
pl.create()
display_size = pl.get_display_size()

det_app = DetectionApp(
    inference_mode, kmodel_path, labels, model_input_size,
    anchors, model_type, confidence_threshold, nms_threshold,
    rgb888p_size, display_size, debug_mode=debug_mode
)
det_app.config_preprocess()

print("钢珠检测 + 串口通信 已启动")
print("标签: {}".format(labels))
print("UART1 波特率: 115200")
print("协议: B,<cx>,<cy>,<conf>,<x1>,<y1>,<x2>,<y2>  /  N (无检测)")

# res['boxes'] 里的坐标已经是 rgb888p_size [1280,720] 空间，无需再缩放

# ==================== 消抖参数 ====================
# EMA 平滑系数：越小越平滑但响应越慢，越大响应越快但抖动越多
# 建议范围 0.3~0.7：静止场景用 0.3，运动场景用 0.5~0.7
EMA_ALPHA = 1.0                    # 新帧权重（0~1），1.0=不消抖（原始输出），<1=平滑

# ==================== 主循环 ====================
frame_count = 0
no_detect_count = 0                # 连续未检测计数

# EMA 平滑状态（初始化为 None，首帧直接赋值）
ema_cx, ema_cy = None, None
ema_x1, ema_y1, ema_x2, ema_y2 = None, None, None, None
ema_score = None

while True:
    with ScopedTiming("total", 1):
        img = pl.get_frame()                          # 获取一帧图像
        res = det_app.run(img)                        # 推理检测钢珠
        det_app.draw_result(pl.osd_img, res)          # 在屏幕上画框
        pl.show_image()                               # 显示
        gc.collect()

    frame_count += 1

    # ---- 串口发送钢珠坐标（含 EMA 消抖） ----
    # res 结构: {'boxes': [[x1,y1,x2,y2],...], 'idx': [...], 'scores': [...]}
    if res is not None and len(res['boxes']) > 0:

        no_detect_count = 0

        # 只取置信度最高的一个（钢珠只有一个，过滤可能的误检）
        best_idx = 0
        best_score = res['scores'][0]
        for i in range(1, len(res['scores'])):
            if res['scores'][i] > best_score:
                best_score = res['scores'][i]
                best_idx = i

        box = res['boxes'][best_idx]       # [x1, y1, x2, y2]，已在图像空间(1280x720)
        score = res['scores'][best_idx]    # 置信度 0~1

        # 原始坐标
        raw_x1, raw_y1 = int(box[0]), int(box[1])
        raw_x2, raw_y2 = int(box[2]), int(box[3])
        raw_cx = (raw_x1 + raw_x2) // 2
        raw_cy = (raw_y1 + raw_y2) // 2

        # ---- EMA 消抖 ----
        alpha = EMA_ALPHA
        if ema_cx is None:
            # 首帧直接赋值，不做平滑
            ema_cx, ema_cy = raw_cx, raw_cy
            ema_x1, ema_y1 = raw_x1, raw_y1
            ema_x2, ema_y2 = raw_x2, raw_y2
            ema_score = score
        else:
            ema_cx  = alpha * raw_cx  + (1 - alpha) * ema_cx
            ema_cy  = alpha * raw_cy  + (1 - alpha) * ema_cy
            ema_x1  = alpha * raw_x1  + (1 - alpha) * ema_x1
            ema_y1  = alpha * raw_y1  + (1 - alpha) * ema_y1
            ema_x2  = alpha * raw_x2  + (1 - alpha) * ema_x2
            ema_y2  = alpha * raw_y2  + (1 - alpha) * ema_y2
            ema_score = alpha * score + (1 - alpha) * ema_score

        # 输出平滑后的整数坐标
        cx = int(ema_cx)
        cy = int(ema_cy)
        x1 = int(ema_x1)
        y1 = int(ema_y1)
        x2 = int(ema_x2)
        y2 = int(ema_y2)

        # 协议: B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>
        msg = "B,{},{},{:.2f},{},{},{},{}\n".format(cx, cy, ema_score, x1, y1, x2, y2)
        uart1.write(msg)

    else:
        # 无检测 → 发送 N 告知 STM32 钢珠丢失，同时重置 EMA 状态
        no_detect_count += 1
        if no_detect_count == 1:
            uart1.write("N\n")
        # 丢帧时重置平滑状态，下次检测到球时重新初始化
        ema_cx, ema_cy = None, None
        ema_x1, ema_y1, ema_x2, ema_y2 = None, None, None, None
        ema_score = None

# ==================== 清理 ====================
det_app.deinit()
pl.destroy()
uart1.deinit()
