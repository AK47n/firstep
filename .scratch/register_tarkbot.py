"""把塔克 R3 两驱小车底盘资料 zip 内应用代码注册为参考库条目（.scratch 工具脚本）。

源：Desktop/塔克 l R3系列两驱小车底盘资料_20241015（2.2G，几乎全二进制）。
入库范围（用户已定：解压提应用代码）：
- DB20 电机 PID 教程 5 工程（STM32F10x）：直流调速 / 编码器采集 / PID 速度 / PID 位置 / 舵机角度
- 小车底盘控制源码（STM32F4xx）：ax_* 驱动（encoder/motor/ps2/servo…）+ main
- 每个 zip 只取 Doc/ + User/ + X-SOFT|Driver/ 文本（.c/.h/.txt/.md），Libraries/ 标准库排除
- 素材清单.txt：全树留痕（pdf/zip/step/exe 等二进制不入库）
锚定 none；平台 stm32（STM32 专用电机/PID 参考，与 MSPM0_MOTOR 同款对偶）。
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from contest_generator import config  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    add_reference,
    build_material_manifest,
    get_reference,
    list_references,
)

SRC_ROOT = Path(r"C:\Users\luoji\Desktop\塔克 l R3系列两驱小车底盘资料_20241015")
# 参考库目录：与 webapp 同源推导（config 唯一出处，脚本不再硬编码）
REFERENCE_ROOT = config.reference_library_dir(REPO_ROOT / "library" / "modules")

TITLE = "塔克R3两驱小车底盘资料"
TYPE = "小车底盘资料"
TEXT_SUFFIXES = {".c", ".h", ".txt", ".md"}

# zip 相对路径 → 解压后顶层目录名（zip 内已自带顶层目录，仅用于提示）
ZIPS = [
    "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_1直流电机调速.zip",
    "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_2编码器数据采集.zip",
    "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_3PID速度控制.zip",
    "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_4PID位置控制.zip",
    "3 STM32电机PID教程/DB20 电机PID闭环控制程序源码/DB20_5舵机角度控制.zip",
    "5 小车底盘控制源码/编码器电机小车控制源码V1.0.230626.zip",
]


def _decode_name(raw: str) -> str:
    """zip 内文件名：UTF-8 标志缺失时按 GBK 回退（中文工程名）。"""
    try:
        raw.encode("cp437").decode("gbk")
        return raw.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def extract_zip_app(zip_rel: str) -> dict[str, str]:
    """解压单个 zip 的应用代码（排除 Libraries/），返回 相对路径→内容。"""
    files: dict[str, str] = {}
    with zipfile.ZipFile(SRC_ROOT / zip_rel) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _decode_name(info.filename)
            suffix = Path(name).suffix.lower()
            if suffix not in TEXT_SUFFIXES:
                continue
            if "/Libraries/" in f"/{name}":
                continue
            try:
                content = zf.read(info).decode("utf-8")
            except (UnicodeDecodeError, OSError):
                try:
                    content = zf.read(info).decode("gbk")
                except (UnicodeDecodeError, OSError):
                    continue
            files[name] = content
    return files


def iter_text_files() -> dict[str, str]:
    """zip 应用代码 + 散落文本文件（相对路径 → 内容）。"""
    files: dict[str, str] = {}
    for zip_rel in ZIPS:
        extracted = extract_zip_app(zip_rel)
        if not extracted:
            print(f"[警告] zip 无可入库文本：{zip_rel}")
        files.update(extracted)
        print(f"[解压] {Path(zip_rel).name}: {len(extracted)} 个文本")
    for path in sorted(SRC_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        files[path.relative_to(SRC_ROOT).as_posix()] = content
    return files


def main() -> None:
    if TITLE in {e.title for e in list_references(REFERENCE_ROOT)}:
        print(f"[跳过] 条目已存在：{TITLE}")
        return
    files: dict[str, str] = {"素材清单.txt": build_material_manifest(SRC_ROOT)}
    files.update(iter_text_files())
    print(f"文本文件 {len(files) - 1} 个（含素材清单共 {len(files)}）")
    entry = add_reference(
        REFERENCE_ROOT,
        title=TITLE,
        type=TYPE,
        description=(
            "塔克创新 R3 系列两驱小车底盘资料：DB20 电机 PID 闭环教程 5 工程"
            "（STM32F10x 标准库——直流调速 / 编码器采集 / PID 速度控制 / PID "
            "位置控制 / 舵机角度控制）+ 编码器电机小车底盘控制源码（STM32F4xx，"
            "ax_encoder / ax_motor / ax_ps2 / ax_servo 等封装驱动），仅取应用代码，"
            "Libraries/ 标准库排除。用户手册 / 电机手册 / 运动学教程 / 驱动芯片 "
            "资料 / 3D 模型 / 软件安装包（约 2.2G）不入库，完整保真见源目录；素材清单留痕。"
        ),
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files=files,
        kit_vocabulary=(),
        platform=PLATFORM_STM32,
    )
    print(
        f"[入库] {entry.id}  type={entry.type}  anchor={entry.anchor_kind}"
        f"  platform={entry.platform}  文件 {len(files)} 个"
        f"  {entry.file_count} files / {entry.size_bytes} bytes"
    )
    print(f"       校验回读：{get_reference(REFERENCE_ROOT, entry.id).title}")


if __name__ == "__main__":
    main()
