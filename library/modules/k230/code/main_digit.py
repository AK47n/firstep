# K230 AI 数字识别脚本（CanMV main.py）——拷贝到 TF 卡根目录（替换同名文件），
# K230 上电自动运行（CanMV 开机自启动 main.py）。
#
# 闭环：AI 检测 8 类数字（AnchorBaseDet 模型）→ 组 DIGIT CSV 帧 → UART 发给主控。
# 主控侧解析由 digit_uart 模块提供（生成器按模板级依赖自动挂上），两侧帧契约
# 同源——下面帧头 / 数据行格式与串口波特率由生成器渲染占位符注入，不要手改
# 字面量（改了就和主控解析对不齐）；索引按逗号位置数，主控只消费
# label/confidence/cx/cy，其余字段为契约占位（不可删）。
#
# 串口接线（与参考库 21F 数字识别例程同款）：
#   K230 11 脚 = UART2 TXD → 主控数字识别串口 RX
#   K230 12 脚 = UART2 RXD → 主控数字识别串口 TX（本脚本只发不收，可留空）
#
# 部署包：模板随生成工程复制 mp_deployment_source/（deploy_config.json +
# digit8_anchorbase_320.kmodel）——整目录（连同 main.py）拷入 SD 卡 /sdcard/，
# 模型路径 /sdcard/mp_deployment_source/ 由部署包自己指定（deploy_config.json
# 的 kmodel_path），换模型/调阈值改 deploy_config.json 即可，无需改本脚本。
#
# 素材：参考库 21F det_uart.py（libs.PlatTasks.DetectionApp +
# libs.PipeLine.PipeLine + libs.Utils.read_json，CanMV 镜像自带 libs）。

import gc
import os

from libs.PipeLine import PipeLine
from libs.PlatTasks import DetectionApp
from libs.Utils import ScopedTiming, read_json

from machine import FPIOA
from machine import UART

# ---- 帧契约（生成器从契约单源渲染注入；与主控 digit_uart 解析严格一致）----
FRAME_HEADER = '{{digit_frame_header}}'  # --- frame N | M targets ---
FRAME_LINE = '{{digit_frame_line}}'      # label,confidence,x1,y1,x2,y2,cx,cy,w,h

uart = None
pl = None
det_app = None

try:
    # FPIOA 串口映射：11 = UART2 TXD、12 = UART2 RXD（与主控 RX/TX 交叉）
    fpioa = FPIOA()
    fpioa.set_function(11, FPIOA.UART2_TXD)
    fpioa.set_function(12, FPIOA.UART2_RXD)
    uart = UART(UART.UART2, {{uart_baudrate}})

    # 显示模式（与 21F 例程一致）：HDMI = "lt9611" / LCD = "st7701"
    display_mode = "lt9611"
    rgb888p_size = [1280, 720]

    # ---- 模型配置（运行期读部署包，换模型/调阈值只改 deploy_config.json）----
    root_path = "/sdcard/mp_deployment_source/"
    deploy_conf = read_json(root_path + "deploy_config.json")
    kmodel_path = root_path + deploy_conf["kmodel_path"]
    labels = deploy_conf["categories"]
    confidence_threshold = deploy_conf["confidence_threshold"]
    nms_threshold = deploy_conf["nms_threshold"]
    model_input_size = deploy_conf["img_size"]
    model_type = deploy_conf["model_type"]
    anchors = []
    if model_type == "AnchorBaseDet":
        anchors = (
            deploy_conf["anchors"][0] + deploy_conf["anchors"][1]
            + deploy_conf["anchors"][2]
        )

    # ---- 初始化推理管线与检测应用（CanMV 镜像自带 libs）----
    pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode)
    pl.create()
    display_size = pl.get_display_size()

    det_app = DetectionApp(
        "video", kmodel_path, labels, model_input_size,
        anchors, model_type, confidence_threshold, nms_threshold,
        rgb888p_size, display_size,
    )
    det_app.config_preprocess()

    print("AI 数字识别 + 串口通信 已启动")
    print("标签: {}".format(labels))

    frame_count = 0

    # res['boxes'] 坐标已在 rgb888p_size [1280,720] 空间，无需缩放
    while True:
        os.exitpoint()
        with ScopedTiming("total", 1):
            img = pl.get_frame()          # 获取一帧图像
            res = det_app.run(img)        # 推理检测数字
            det_app.draw_result(pl.osd_img, res)
            pl.show_image()
            gc.collect()

        frame_count += 1

        # ---- 串口发送检测结果（DIGIT 契约：帧头 + 每目标一行 + 空行帧尾）----
        # 无检测也发帧头（0 目标帧）——主控每帧都有稳定帧界；解析端 count=0
        # 帧不参与最佳帧比较，不污染结果。
        count = len(res["boxes"]) if res is not None else 0
        uart.write(FRAME_HEADER.format(n=frame_count, m=count) + "\n")
        for i in range(count):
            box = res["boxes"][i]       # [x1,y1,x2,y2]，已在图像空间(1280x720)
            class_id = res["idx"][i]    # 类别索引 → labels[class_id] 得到数字
            score = res["scores"][i]    # 置信度 0~1

            # 坐标直接用，无需缩放
            x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            cx = (x1 + x2) // 2         # 中心点 x
            cy = (y1 + y2) // 2         # 中心点 y
            w = x2 - x1                 # 框宽度
            h = y2 - y1                 # 框高度

            uart.write(
                FRAME_LINE.format(
                    label=labels[class_id], confidence=score,
                    x1=x1, y1=y1, x2=x2, y2=y2, cx=cx, cy=cy, w=w, h=h,
                ) + "\n"
            )
        uart.write("\n")  # 空行 = 帧尾

except KeyboardInterrupt as e:
    print("用户停止: ", e)
except BaseException as e:
    print("异常: ", e)
finally:
    if isinstance(det_app, DetectionApp):
        det_app.deinit()
    if isinstance(pl, PipeLine):
        pl.destroy()
    if isinstance(uart, UART):
        uart.deinit()
    os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
