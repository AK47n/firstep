# -*- coding: utf-8 -*-
'''
数字识别 + 串口发送
功能：K230 实时检测数字，将每个数字的【类别、置信度、坐标、中心点】通过 UART2 发送给电脑
电脑端用串口调试助手（115200波特率）即可查看

使用方法：
    1. 复制此文件到 K230 SD 卡 /sdcard/ 目录
    2. 确保 SD 卡已有 mp_deployment_source 文件夹
    3. 接线：K230 引脚11(TX) → USB转TTL RX
              K230 引脚12(RX) → USB转TTL TX
              GND ↔ GND
    4. 电脑打开串口调试助手，波特率 115200
'''

import os, gc
from libs.PlatTasks import DetectionApp
from libs.PipeLine import PipeLine
from libs.Utils import *

from machine import FPIOA
from machine import UART

# ==================== UART 初始化 ====================
fpioa = FPIOA()
fpioa.set_function(11, FPIOA.UART2_TXD)
fpioa.set_function(12, FPIOA.UART2_RXD)
uart2 = UART(UART.UART2, 115200)

# ==================== 模型配置 ====================
display_mode = "lt9611"         # HDMI: "lt9611"  /  LCD: "st7701"
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

print("数字识别 + 串口通信 已启动")
print("标签: {}".format(labels))

# res['boxes'] 里的坐标已经是 rgb888p_size [1280,720] 空间，无需再缩放

# ==================== 主循环 ====================
frame_count = 0

while True:
    with ScopedTiming("total", 1):
        img = pl.get_frame()                         # 获取一帧图像
        res = det_app.run(img)                       # 推理检测数字
        det_app.draw_result(pl.osd_img, res)         # 在屏幕上画框
        pl.show_image()                              # 显示
        gc.collect()

    frame_count += 1

    # ---- 串口发送检测结果 ----
    # res 结构: {'boxes': [[x1,y1,x2,y2],...], 'idx': [2,0,...], 'scores': [0.95,0.87,...]}
    if res is not None and len(res['boxes']) > 0:

        if frame_count % 1 == 0:
            uart2.write("--- frame {} | {} targets ---\n".format(frame_count, len(res['boxes'])))

            for i in range(len(res['boxes'])):
                box = res['boxes'][i]        # [x1,y1,x2,y2]，已在图像空间(1280x720)
                class_id = res['idx'][i]     # 类别索引 → labels[class_id] 得到数字
                score = res['scores'][i]     # 置信度 0~1

                # 坐标直接用，无需缩放
                x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                cx = (x1 + x2) // 2          # 中心点 x
                cy = (y1 + y2) // 2          # 中心点 y
                w = x2 - x1                  # 框宽度
                h = y2 - y1                  # 框高度

                label_name = labels[class_id]

                # 输出: 数字,置信度,左上x,左上y,右下x,右下y,中心x,中心y,宽,高
                msg = "{},{:.2f},{},{},{},{},{},{},{},{}\n".format(
                    label_name, score, x1, y1, x2, y2, cx, cy, w, h
                )
                uart2.write(msg)

            uart2.write("\n")

    # ---- 接收电脑指令（可选） ----
    recv = uart2.read()
    if recv is not None:
        try:
            cmd = recv.decode().strip()
            print("收到PC指令: {}".format(cmd))
        except:
            pass

# ==================== 清理 ====================
det_app.deinit()
pl.destroy()
uart2.deinit()
