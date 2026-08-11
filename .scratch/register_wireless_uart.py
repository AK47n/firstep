"""把无线串口模块资料注册为参考库条目（.scratch 工具脚本）。

源：Desktop/无线串口说明书（DL-20/22/30/43P 无线串口透传模块资料，25M）。
入库范围（沿用 register_materials.py 规则：仅 UTF-8 文本）：
- 亮灯信道对照表：docx 正文（zip 内 word/document.xml）提取为 txt——串口指令
  配置信道的关键对照，生成配置代码时有用
- 素材清单.txt：全树留痕（四型号 PDF 说明书/原理图/尺寸图、CP2102 驱动、
  调试助手 exe 等二进制不入库，完整保真靠源目录）
锚定 none；平台 any（无线串口透传是通用外设，stm32/mspm0 皆可用）。
"""

from __future__ import annotations

import re
import sys
import zipfile
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

SRC_ROOT = Path(r"C:\Users\luoji\Desktop\无线串口说明书")
REFERENCE_ROOT = REPO_ROOT / "library" / "references"

TITLE = "无线串口模块资料"
TYPE = "无线串口资料"
DOCX = "无线串口模块亮灯信道对照表.docx"
DOCX_TEXT_REL = "亮灯信道对照表.txt"


def extract_docx_text() -> str:
    """docx（zip）正文提取：word/document.xml 去标签 → 表格文本。"""
    with zipfile.ZipFile(SRC_ROOT / DOCX) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)  # 段落后换行
    xml = re.sub(r"</w:tr>", "\n", xml)  # 表格行后换行
    text = re.sub(r"<[^>]+>", "", xml)
    return text.strip()


def build_manifest() -> str:
    """源目录全部文件的《素材清单》文本（文件名 + 大小，二进制留痕）。"""
    lines = ["素材目录（Desktop/无线串口说明书）文件清单：", ""]
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
    files: dict[str, str] = {
        "素材清单.txt": build_manifest(),
        DOCX_TEXT_REL: extract_docx_text(),
    }
    entry = add_reference(
        REFERENCE_ROOT,
        title=TITLE,
        type=TYPE,
        description=(
            "无线串口透传模块资料（DL-20 / DL-22 / DL-30 / DL-43P 四型号）："
            "亮灯信道对照表（串口指令配置信道的亮灯与信道对应关系，docx 正文提取）；"
            "四型号使用说明书 / 原理图 / 尺寸图、CP2102 驱动、串口调试助手等二进制"
            "（约 25M）不入库，完整保真见 Desktop/无线串口说明书；素材清单留痕。"
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
