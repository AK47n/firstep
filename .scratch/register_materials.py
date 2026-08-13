"""把 sources/materials/ 下素材目录注册为参考库条目（.scratch 工具脚本）。

规则（与参考库"存文本内容"的能力对齐）：
- 每个素材目录 → 一条参考文件条目（id = 目录名，便于对照备份）
- 入库文件 = UTF-8 可读的文本文件（read_fulltext 只能注入文本）+ 一张
  《素材清单.txt》（列出源目录全部文件与大小，二进制素材不进库但清单留痕）
- 二进制（zip / pdf / exe / 镜像等）不入库——UI 无下载/预览路由，注入也用
  不上；完整保真已由 sources/materials/ 备份承担
- 锚定：地猛星控制题配套 → 赛题 2026H（H 题=车载平衡滚球运动控制系统，
  配套即此题的逐步开发例程）；其余无归属 → 未锚定（anchor_kind=none）
- 已存在同名条目时跳过（可重复运行）
"""

from __future__ import annotations

import sys
from pathlib import Path

# Windows 控制台默认 GBK 会打花中文日志：脚本输出统一 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from contest_generator import config  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    ANCHOR_KIND_TOPIC,
    PLATFORM_ANY,
    add_reference,
    build_material_manifest,
    get_reference,
    list_references,
)

# 素材备份根 / 参考库目录：与 webapp 同源推导（config 唯一出处，脚本不再硬编码）
MATERIALS_ROOT = config.materials_dir(REPO_ROOT / "library" / "modules")
REFERENCE_ROOT = config.reference_library_dir(REPO_ROOT / "library" / "modules")

# 单个文件入库上限：超过视为大二进制（文本文件实际都在 MB 级以下）
MAX_TEXT_BYTES = 20 * 1024 * 1024

ENTRIES = [
    {
        "dir": "2026_04_地猛星电赛控制题配套资料",
        "type": "配套资料",
        "description": (
            "2026 年电赛控制题（H 题：车载平衡滚球运动控制系统）配套资料："
            "立创·地猛星 MSPM0G3507 开发板引脚图 / 原理图；小车（DC 电机 PID "
            "闭环、灰度巡线、MPU6050 陀螺仪、OLED、串口校准）与云台（步进电机、"
            "SPI 屏幕、激光笔）逐步开发例程；CCS 20.5 安装包与 2017-2025 真题汇总。"
            "二进制素材（zip/pdf/exe 约 1.9G）不入库，完整保真见 sources/materials 备份。"
        ),
        "anchor_kind": ANCHOR_KIND_TOPIC,
        "anchor_value": "2026H",
        "platform": PLATFORM_MSPM0,
    },
    {
        "dir": "2026_06_电赛视觉资料",
        "type": "视觉资料",
        "description": (
            "2026 年电赛视觉题配套资料：立创·泰山派开发板摄像头取流、参数设置、"
            "色块与激光点识别、GPIO 驱动激光笔、按键任务切换等脚本；刷机 / 推流 / "
            "调试工具（RKDevTool、VSCode、WinSCP、Ubuntu 镜像等）。文本脚本已入库；"
            "二进制工具 / 镜像 / 压缩包（约 2.7G）不入库，完整保真见 sources/materials 备份。"
        ),
        "anchor_kind": ANCHOR_KIND_NONE,
        "anchor_value": "",
    },
    {
        "dir": "2026_07_电赛带练真题资料",
        "type": "带练真题",
        "description": (
            "电赛真题带练资料：23 年 E 题（激光点识别）与 24 年 H 题（小车）逐步带练"
            "工程压缩包，及 2017-2025 全国大学生电子设计竞赛真题汇总 PDF。全部为"
            "压缩包 / PDF（约 43M）不入库，完整保真见 sources/materials 备份，素材清单见本条目文件。"
        ),
        "anchor_kind": ANCHOR_KIND_NONE,
        "anchor_value": "",
    },
    {
        "dir": "k230资料",
        "type": "开发板资料",
        "description": (
            "嘉楠 CanMV K230 开发板资料：micropython 固件镜像、CanMV IDE、"
            "摄像头 / 视觉 Python 例程（21 个 .py）、python 基础笔记等。文本脚本已入库；"
            "固件镜像 / IDE 安装包（约 1G）不入库，完整保真见 sources/materials 备份。"
        ),
        "anchor_kind": ANCHOR_KIND_NONE,
        "anchor_value": "",
    },
    # 「MSPM0_MOTOR参考例程」已由工单 reference-library-hygiene/02 拆为三条
    # （MSPM0-Motor_Ctrl 电机控制例程 / MSPM0-m0imu 姿态例程 / MSPM0-MOTOR 移植笔记，
    # .scratch/fix_mspm0_motor.py 维护，剥 SDK 副本树后精录）。此处不再登记：旧 id
    # 已删除，若保留会绕过 skip-on-exist 把整棵原始树（含已剥离的 SDK 副本）
    # 重新灌回库（工单 register-gbk-guard/01 真机重跑时实际踩中，已清退恢复）。
]


def _read_transcoded(path: Path) -> str | None:
    """UTF-8 失败后按 gb18030（GBK 超集）兜底转码，\r\n 归一化；仍失败返回 None。"""
    try:
        return path.read_bytes().decode("gb18030").replace("\r\n", "\n")
    except (UnicodeDecodeError, OSError):
        return None


def iter_text_files(src_dir: Path) -> dict[str, str]:
    """目录内 UTF-8 可读文本文件（相对路径 → 内容）；二进制 / 超大文件跳过。

    UTF-8 失败回退 gb18030 转码入库（中文注释 GBK 源码曾静默漏录，见工单
    register-gbk-guard/01）；仍失败按二进制跳过，收尾计数汇总打印（静默变可见）。
    """
    files: dict[str, str] = {}
    skipped = 0
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                skipped += 1
                continue
        except OSError:
            skipped += 1
            continue
        rel = path.relative_to(src_dir).as_posix()
        if rel == "reference.json":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = _read_transcoded(path)
            if content is None:
                skipped += 1
                continue
            print(f"[转码] {rel}（gbk→utf-8）")
        except OSError:
            skipped += 1
            continue
        files[rel] = content
    print(f"[跳过] {skipped} 个非文本文件未入库")
    return files


def main() -> None:
    existing = {e.id for e in list_references(REFERENCE_ROOT)}
    for spec in ENTRIES:
        src_dir = MATERIALS_ROOT / spec["dir"]
        if not src_dir.is_dir():
            print(f"[跳过] 目录不存在：{src_dir}")
            continue
        if spec["dir"] in existing:
            print(f"[跳过] 条目已存在：{spec['dir']}")
            continue
        files: dict[str, str] = {"素材清单.txt": build_material_manifest(src_dir)}
        files.update(iter_text_files(src_dir))
        entry = add_reference(
            REFERENCE_ROOT,
            title=spec["dir"],
            type=spec["type"],
            description=spec["description"],
            anchor_kind=spec["anchor_kind"],
            anchor_value=spec["anchor_value"],
            files=files,
            kit_vocabulary=(),
            platform=spec.get("platform", PLATFORM_ANY),
        )
        print(
            f"[入库] {entry.id}  type={entry.type}  anchor={entry.anchor_kind}:"
            f"{entry.anchor_value!r}  文件 {len(files)} 个"
        )
        print(f"       校验回读：{get_reference(REFERENCE_ROOT, entry.id).title}")


if __name__ == "__main__":
    main()
