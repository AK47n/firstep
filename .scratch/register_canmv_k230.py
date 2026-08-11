"""把官方 CanMV K230 固件源码树的文本例程注册为参考库条目（.scratch 工具脚本）。

源：Desktop/tuchuan/canmv_k230（kendryte/canmv_k230 官方 git clone，v1.5-legacy）。
入库范围（用户已定）：
- resources/examples/**/*.py     官方例程 359 个（27 类）
- resources/libs/*.py            AI 库 8 个（AIBase/PipeLine/YOLO/WBCRtsp/PlatTasks…）
- port/builtin_py/**/*.py        内置 media/mpp 绑定
- 素材清单.txt：全树文件留痕（C 源码 / 二进制不入库，完整保真靠官方 git clone）
锚定 none（通用 API 参考，不绑单题）；平台 any（K230 是视觉模块，非生成平台）。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from contest_generator import config  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    PLATFORM_ANY,
    add_reference,
    build_material_manifest,
    get_reference,
    list_references,
)

SRC_ROOT = Path(r"C:\Users\luoji\Desktop\tuchuan\canmv_k230")
# 参考库目录：与 webapp 同源推导（config 唯一出处，脚本不再硬编码）
REFERENCE_ROOT = config.reference_library_dir(REPO_ROOT / "library" / "modules")

TITLE = "canmv_k230官方源码"
TYPE = "官方源码"
INCLUDE_DIRS = ("resources/examples", "resources/libs", "port/builtin_py")


def iter_text_files() -> dict[str, str]:
    """三个入选目录内的 UTF-8 文本文件（相对路径 → 内容），二进制跳过。"""
    files: dict[str, str] = {}
    for sub in INCLUDE_DIRS:
        root = SRC_ROOT / sub
        if not root.is_dir():
            print(f"[警告] 目录不存在：{root}")
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() != ".py":
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            files[f"{sub}/{path.relative_to(root).as_posix()}"] = content
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
            "嘉楠 CanMV K230 官方固件源码树（kendryte/canmv_k230，v1.5-legacy "
            "2026-07 快照）文本子集：官方例程 359 个（色块追踪 / AprilTag / 二维码 / "
            "AI 检测 / UART / PWM / 显示 / LVGL 等 27 类）、AI 库 8 个（AIBase / "
            "PipeLine / YOLO / WBCRtsp / PlatTasks 等）、builtin_py 内置 media/mpp "
            "绑定。port/ C 固件源码与二进制（约 110MB）不入库，完整保真见 "
            "Desktop/tuchuan/canmv_k230 官方 git clone；素材清单留痕。"
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
