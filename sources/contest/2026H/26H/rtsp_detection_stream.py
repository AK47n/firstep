"""CanMV K230 - AI Detection (High Accuracy) + RTSP Streaming (Smooth, Low Quality).

Strategy:
  - AI input  1280x720  →  high-accuracy detection, every frame
  - Display    640x360  →  low-res framebuffer → WBC encodes fast → smooth RTSP
  - Two sensor channels are independent; lowering display res doesn't hurt AI.
  - WBC bitrate dropped to 800 kbps (plenty for 360p).

Tuning knobs (top of file):
  - RGB888P_SIZE:    AI resolution  (keep high for accuracy)
  - DISPLAY_SIZE:    RTSP resolution (lower = smoother)
  - SENSOR_FPS:      sensor frame rate
  - WBC_BITRATE:     H264 bitrate in kbps
"""

import _thread
import os, gc, time
import network
from libs.PlatTasks import DetectionApp
from libs.PipeLine import PipeLine
from libs.WBCRtsp import WBCRtsp
from libs.Utils import *

# ============================================================
# WiFi Configuration
# ============================================================
WIFI_SSID = "gyzqxj"
WIFI_PASSWORD = "gyzqxjxj"      # WiFi password
WIFI_CONNECT_TIMEOUT_S = 15
WIFI_RETRY_DELAY_S = 3

# ============================================================
# Performance Tuning
# ============================================================
DISPLAY_MODE = "virt"           # Virtual display (headless)
RGB888P_SIZE = [1280, 720]      # AI input  — high resolution = accurate detection
DISPLAY_SIZE = [640, 360]       # RTSP/WBC  — low resolution = smooth stream
SENSOR_ID = 2                   # Camera sensor ID (0/1/2/3 on 01studio K230)
SENSOR_FPS = 30                 # Sensor frame rate
WBC_BITRATE = 800               # H264 bitrate (kbps), plenty for 640x360
GC_EVERY_N = 10                 # GC interval (frames)
STATUS_INTERVAL_S = 5           # Status log interval

# ============================================================
# Model Configuration (loaded from SD card)
# ============================================================
ROOT_PATH = "/sdcard/mp_deployment_source/"


def connect_wifi(ssid, password, timeout_s=WIFI_CONNECT_TIMEOUT_S):
    """Connect to WiFi with robust retry logic."""
    sta = network.WLAN(network.STA_IF)
    while not sta.isconnected():
        access_points = sta.scan(ssid)
        if not access_points:
            print("Wi-Fi not found, retrying:", ssid)
            time.sleep(WIFI_RETRY_DELAY_S)
            continue

        access_point = max(access_points, key=lambda item: item.rssi)
        print("selected access point:", access_point)
        try:
            if password:
                print("connect request:",
                      sta.connect(ssid, password))
            else:
                print("connect request:",
                      sta.connect(None, None, info=access_point))
        except Exception as error:
            print("Wi-Fi connect request failed:", error)
            time.sleep(WIFI_RETRY_DELAY_S)
            continue

        started = time.time()
        while not sta.isconnected() and time.time() - started <= timeout_s:
            time.sleep(1)
        if not sta.isconnected():
            print("Wi-Fi connection timed out, retrying")
            time.sleep(WIFI_RETRY_DELAY_S)

    print("network information:", sta.ifconfig())
    return sta


if __name__ == "__main__":
    os.exitpoint(os.EXITPOINT_ENABLE)

    # ---- 1. Connect WiFi ----
    nic = connect_wifi(WIFI_SSID, WIFI_PASSWORD)

    # ---- 2. Load detection model config from SD card ----
    deploy_conf = read_json(ROOT_PATH + "/deploy_config.json")
    kmodel_path = ROOT_PATH + deploy_conf["kmodel_path"]
    labels = deploy_conf["categories"]
    confidence_threshold = deploy_conf["confidence_threshold"]
    nms_threshold = deploy_conf["nms_threshold"]
    model_input_size = deploy_conf["img_size"]
    model_type = deploy_conf["model_type"]
    anchors = []
    if model_type == "AnchorBaseDet":
        anchors = (deploy_conf["anchors"][0] +
                   deploy_conf["anchors"][1] +
                   deploy_conf["anchors"][2])

    # ---- 3. Clean up any previously-initialized media resources ----
    try:
        from media.media import MediaManager
        MediaManager.deinit()
        time.sleep_ms(200)
    except Exception:
        pass

    # ---- 4. Create PipeLine ----
    # CHN0 → display at DISPLAY_SIZE (640x360 YUV) → WBC captures for RTSP
    # CHN2 → AI     at RGB888P_SIZE  (1280x720 RGB) → detection
    pl = PipeLine(rgb888p_size=RGB888P_SIZE,
                   display_mode=DISPLAY_MODE,
                   display_size=DISPLAY_SIZE)
    pl.create(to_ide=False, fps=SENSOR_FPS, sensor_id=SENSOR_ID)
    display_size = pl.get_display_size()

    # ---- 4. Start WBC RTSP (encodes display framebuffer → H264 → RTSP) ----
    WBCRtsp.configure(wbc_width=display_size[0],
                       wbc_height=display_size[1])
    WBCRtsp.start()
    rtsp_url = WBCRtsp.rtspserver.get_rtsp_url()
    print("service ready:", rtsp_url)

    # ---- 5. Initialize AI detection (high-res input) ----
    det_app = DetectionApp(
        "video", kmodel_path, labels, model_input_size,
        anchors, model_type, confidence_threshold, nms_threshold,
        RGB888P_SIZE, display_size, debug_mode=0
    )
    det_app.config_preprocess()

    # ---- 6. Main loop: capture → detect → draw → display (→ WBC → RTSP) ----
    frame_count = 0
    last_status = time.ticks_ms()
    fps_clock = time.ticks_ms()
    fps_frames = 0

    try:
        while True:
            os.exitpoint()

            # --- Capture & detect (every frame, high-res for accuracy) ---
            img = pl.get_frame()                          # 1280x720 RGB from CHN2
            res = det_app.run(img)                        # AI inference
            det_app.draw_result(pl.osd_img, res)          # Draw boxes on OSD
            pl.show_image()                               # Composite → display (640x360)
            frame_count += 1

            # --- Periodic GC ---
            if frame_count % GC_EVERY_N == 0:
                gc.collect()

            # --- FPS counter ---
            fps_frames += 1
            elapsed = time.ticks_diff(time.ticks_ms(), fps_clock)
            if elapsed >= 5000:
                fps = fps_frames * 1000.0 / elapsed
                print("fps=%.1f ai=%dx%d stream=%dx%d bitrate=%d" %
                      (fps, RGB888P_SIZE[0], RGB888P_SIZE[1],
                       display_size[0], display_size[1], WBC_BITRATE))
                fps_frames = 0
                fps_clock = time.ticks_ms()

            # --- WiFi reconnect check ---
            if not nic.isconnected():
                print("Wi-Fi disconnected; reconnecting to", WIFI_SSID)
                nic = connect_wifi(WIFI_SSID, WIFI_PASSWORD)
                print("Wi-Fi reconnected:", nic.ifconfig())

            # --- Periodic status ---
            if time.ticks_diff(time.ticks_ms(), last_status) >= STATUS_INTERVAL_S * 1000:
                print("STATUS ip=%s wifi=%d rtsp=%s" %
                      (nic.ifconfig()[0], nic.isconnected(), rtsp_url))
                last_status = time.ticks_ms()

    except KeyboardInterrupt:
        print("user stop")
    except BaseException as e:
        import sys
        sys.print_exception(e)
    finally:
        det_app.deinit()
        WBCRtsp.stop()
        pl.destroy()
        os.exitpoint(os.EXITPOINT_ENABLE_SLEEP)
