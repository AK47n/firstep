# -*- coding: utf-8 -*-
"""新批次资料按"参考意义"补充备份到 sources/materials/（.scratch 工具脚本）。

背景：K230/ESP32-CAM/塔克/无线串口 四批入库时只做了参考库文本 + 素材清单，
PDF 等"用户要保留"的二进制没进 firstep——删掉桌面即丢。本脚本补上。

保留规则（用户定：非全量，按参考意义筛选）：
- 必保：全部 PDF（说明书 / 手册 / 原理图 / 规格书 / 教程）
- 必保：完整工程 zip（塔克 DB20×5 + 底盘控制源码——商业资料，文本已提但
  完整 Keil 工程含 uvprojx/标准库，保真有意义）
- 必保：docx 原件（无线串口信道对照表，已提文本但原件小）
- 不保：exe 安装包 / 驱动 / 固件镜像 / 视频 / 3D 模型 / gif png jpg /
  开源可重新下载的 zip（ESP32_CAMERA_QR-master 等）——重新获得成本低

镜像源目录相对路径（与素材清单一一对应）。全部 <50MB，直接 git 追踪。
"""
import shutil
import sys
from pathlib import Path

REPO = Path(r"C:\Users\luoji\Desktop\firstep")

# 源目录 → (备份目标目录名, 额外保留的 zip/docx 白名单)
BATCHES = [
    (
        Path(r"C:\Users\luoji\Desktop\塔克 l R3系列两驱小车底盘资料_20241015"),
        "塔克R3两驱小车底盘资料",
        {
            "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_1直流电机调速.zip",
            "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_2编码器数据采集.zip",
            "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_3PID速度控制.zip",
            "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_4PID位置控制.zip",
            "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_5舵机角度控制.zip",
            "5 小车底盘控制源码/编码器电机小车控制源码V1.0.230626.zip",
        },
    ),
    (
        Path(r"C:\Users\luoji\Desktop\无线串口说明书"),
        "无线串口模块资料",
        {"无线串口模块亮灯信道对照表.docx"},
    ),
    (
        Path(r"C:\Users\luoji\Desktop\C7-3-4L"),
        "C7-3-4L-ESP32-CAM开发板资料",
        set(),
    ),
]

KEEP_SUFFIXES = {".pdf", ".zip", ".docx"}


def main() -> None:
    copied = 0
    for src_root, dest_name, whitelist in BATCHES:
        dest_root = REPO / "sources" / "materials" / dest_name
        dest_root.mkdir(parents=True, exist_ok=True)
        for path in sorted(src_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(src_root).as_posix()
            keep = (
                path.suffix.lower() == ".pdf"
                or rel in whitelist
            )
            if not keep:
                continue
            # zip 白名单之外仍按后缀撞上的（如驱动 zip）——白名单制兜底
            if path.suffix.lower() == ".zip" and rel not in whitelist:
                continue
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
            print(f"[拷] {dest_name}/{rel}  {path.stat().st_size // 1024}KB")
        print(f"[完成] {dest_name}: 共 {copied  if copied else 0} 文件")
    print(f"\n总计拷贝 {copied} 个文件到 sources/materials/")


if __name__ == "__main__":
    main()
