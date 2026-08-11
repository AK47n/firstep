"""把 ESP32-CAM 开发板资料文本部分注册为参考库条目（.scratch 工具脚本）。

源：Desktop/C7-3-4L（ESP32-CAM 开发板资料，含 Arduino 例程 / 固件 / 手册 / 视频）。
入库范围（与 K230 同款：仅文本）：
- arduino例程/ESP32CAM/*.{ino,cpp,h,csv}  官方 WiFi 摄像头网页推流例程（5 文件 ~208KB）
- 使用教程.txt / 注意事项.txt
- 素材清单.txt：全树留痕（视频 / 固件 / zip / pdf 等二进制不入库）
锚定 none（视觉模块通用资料，不绑单题）；平台 any（ESP32-CAM 是视觉模块，非生成目标平台）。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    PLATFORM_ANY,
    add_reference,
    get_reference,
    list_references,
)

SRC_ROOT = Path(r"C:\Users\luoji\Desktop\C7-3-4L")
REFERENCE_ROOT = REPO_ROOT / "library" / "references"

TITLE = "C7-3-4L ESP32-CAM开发板资料"
TYPE = "开发板资料"
TEXT_SUFFIXES = {".ino", ".cpp", ".h", ".csv", ".txt"}


def iter_text_files() -> dict[str, str]:
    """源目录内 UTF-8 可读文本文件（相对路径 → 内容）；二进制跳过。"""
    files: dict[str, str] = {}
    for path in sorted(SRC_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        files[path.relative_to(SRC_ROOT).as_posix()] = content
    return files


def build_manifest() -> str:
    """源目录全部文件的《素材清单》文本（文件名 + 大小，二进制留痕）。"""
    lines = ["素材目录（Desktop/C7-3-4L）文件清单：", ""]
    for path in sorted(SRC_ROOT.rglob("*")):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        lines.append(f"{path.relative_to(SRC_ROOT).as_posix()}  {size} bytes")
    return "\n".join(lines)


def main() -> None:
    if TITLE in {e.title for e in list_references(REFERENCE_ROOT)}:
        print(f"[跳过] 条目已存在：{TITLE}")
        return
    files: dict[str, str] = {"素材清单.txt": build_manifest()}
    files.update(iter_text_files())
    print(f"文本文件 {len(files) - 1} 个（含素材清单共 {len(files)}）")
    entry = add_reference(
        REFERENCE_ROOT,
        title=TITLE,
        type=TYPE,
        description=(
            "ESP32-CAM 开发板资料：Arduino IDE 环境、官方 WiFi 摄像头网页推流例程"
            "（app_httpd.cpp 等 5 文件）、ESP32 数据手册与参考手册、OV2640 传感器"
            "手册、出厂固件与烧录工具、MicroPython 固件、烧录接线 / 注意事项 / "
            "使用教程等。文本例程已入库；视频 / 固件 / 手册 / 安装包（约 245M）"
            "不入库，完整保真见 Desktop/C7-3-4L；素材清单留痕。"
        ),
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files=files,
        kit_vocabulary=(),
        platform=PLATFORM_ANY,
    )
    print(
        f"[入库] {entry.id}  type={entry.type}  anchor={entry.anchor_kind}"
        f"  文件 {len(files)} 个  {entry.file_count} files / {entry.size_bytes} bytes"
    )
    print(f"       校验回读：{get_reference(REFERENCE_ROOT, entry.id).title}")


if __name__ == "__main__":
    main()
