"""交付域模块（工单 delivery-suite/01）：打开工程 / 交付检查 / 一键打包。

三个独立动作组装在一次「交付」体验里（任务推进区第 11 步的「🚀 交付」卡）：
- open_project_dir：按平台打开工程——stm32 优先拉起 Keil（uv4_path 覆盖 >
  C:/Keil*/UV4/UV4.exe 探测 > 系统关联 startfile），兜底 explorer 打开文件夹；
  mspm0 = explorer 打开文件夹（CCS 是 Eclipse 工作区模型，手动导入
  .ccsproject，message 说明）。
- delivery_check：任务清单完成度汇总（verified+skipped = 完成；其余状态
  = 未完成并逐条列出）；未拆解清单 = ok False + 中文提示。
- package_project：工程目录打包 zip（排除 .contest_* 内部状态文件与
  *.tmp / *.bak），时间戳命名放父目录不覆盖旧包。

Windows-only 的进程启动/关联打开都包 try（OSError → 降级 message），不抛
异常；只有目录缺失 / 平台未知才是 DeliveryError（400 中文）。
from task_progress import TaskError 仅为防环占位——本模块不抛 TaskError
（错误类型 = DeliveryError，errors.py 登记）；注释保留说明防环关系。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .task_progress import TaskError  # noqa: F401  # 防环占位（见模块 docstring）

if TYPE_CHECKING:
    pass


class DeliveryError(ValueError):
    """交付操作失败（输出目录缺失 / 平台未知），400 中文（errors.py 登记）。"""


def _find_uv4(uv4_path: str) -> str | None:
    """Keil UV4.exe 定位：config 覆盖 > 常见安装目录（C:/Keil*/UV4/UV4.exe）>
    PATH 探测（shutil.which）。返回绝对路径字符串；找不到 = None（调用方
    走 startfile 关联 / explorer 兜底，不报错）。"""
    if uv4_path:
        p = Path(uv4_path)
        if p.is_file():
            return str(p)
        return None  # config 覆盖指向不存在文件：视为未配置（不静默用别的）
    try:
        candidates = sorted(Path("C:/").glob("Keil*/UV4/UV4.exe"))
        if candidates:
            return str(candidates[0])
    except OSError:
        pass  # C:/ 不可读（非 Windows / 权限）：走 PATH
    which = shutil.which("UV4")
    return which if which else None


def _open_folder(output_dir: Path, message: str) -> dict:
    """explorer 打开文件夹兜底（Windows 资源管理器；非 Windows 或启动失败
    = 仍返回 folder 模式 + message 指引手动打开——不抛异常）。"""
    try:
        subprocess.Popen(["explorer", str(output_dir)])
    except OSError:
        return {
            "mode": "folder",
            "target": str(output_dir),
            "message": message + "（当前环境无法自动打开资源管理器，请手动打开该路径）",
        }
    return {"mode": "folder", "target": str(output_dir), "message": message}


def open_project_dir(output_dir: Path, *, uv4_path: str = "") -> dict:
    """打开工程（平台自适应）：stm32 优先 Keil / 关联打开 / explorer 兜底；
    mspm0 = explorer 打开文件夹。返回 {"mode": "ide"|"folder", "target",
    "message"}。平台未知（_infer_platform 抛 ContextError）→ DeliveryError。"""
    from .context_manifest import _infer_platform
    from .platforms import PLATFORM_STM32

    try:
        platform = _infer_platform(output_dir)
    except Exception as exc:  # ContextError（400 语义透传）
        raise DeliveryError(str(exc)) from exc

    if platform == PLATFORM_STM32:
        try:
            proj = next(iter(sorted(output_dir.rglob("*.uvprojx"))), None)
        except OSError:
            proj = None
        uv4 = _find_uv4(uv4_path)
        if proj is not None and uv4 is not None:
            try:
                subprocess.Popen([uv4, str(proj)])
                return {
                    "mode": "ide",
                    "target": str(proj),
                    "message": "已启动 Keil uVision（UV4）打开工程文件。",
                }
            except OSError:
                pass  # 启动失败：降级关联打开 / 文件夹
        if proj is not None:
            try:
                os.startfile(str(proj))  # 系统关联程序打开 .uvprojx
                return {
                    "mode": "ide",
                    "target": str(proj),
                    "message": "已按默认关联程序打开工程文件（若关联为 Keil 则拉起 uVision）。",
                }
            except OSError:
                pass
        return _open_folder(
            output_dir,
            "未找到 Keil（UV4.exe），已打开工程文件夹——请手动用 Keil 打开 .uvprojx。",
        )

    return _open_folder(
        output_dir,
        "已打开工程文件夹——CCS 工程请手动导入：File → Import → Existing CCS Projects。",
    )


def delivery_check(output_dir: Path) -> dict:
    """交付前检查：任务清单完成度汇总 + 未完成清单（逐条列出，失败一眼可见）。

    返回 {"ok", "plan_present", "stats"|None, "incomplete", "message"}：
    - 清单已拆解：stats = 各状态计数（verified/skipped/unverified/failed/
      pending/doing）；incomplete = 状态不在 {verified, skipped} 的任务
      [{id, title, status}]；ok = 无未完成。
    - 未拆解（plan None）：ok False、plan_present False、stats None、
      incomplete []、message 中文。
    - main.c 缺失 = message 追加提示（不改变 ok——清单状态为准）。
    """
    from .task_progress import read_task_plan

    if not output_dir.is_dir():
        raise DeliveryError(f"输出目录不存在：{output_dir}")
    notes: list[str] = []
    if not (output_dir / "main.c").is_file():
        notes.append("main.c 不存在（未生成骨架？）")

    plan = read_task_plan(output_dir)
    if plan is None:
        message = "尚未拆解任务清单——可先「拆解任务」或直接打包。"
        if notes:
            message += "；" + "；".join(notes)
        return {
            "ok": False,
            "plan_present": False,
            "stats": None,
            "incomplete": [],
            "message": message,
        }

    statuses = ("verified", "skipped", "unverified", "failed", "pending", "doing")
    counts = {status: 0 for status in statuses}
    incomplete: list[dict] = []
    for task in plan.tasks:
        status = task.status if task.status in counts else "pending"
        counts[status] += 1
        if status not in ("verified", "skipped"):
            incomplete.append(
                {"id": task.id, "title": task.title, "status": status}
            )

    done = counts["verified"] + counts["skipped"]
    message = (
        f"已完成 {done}/{len(plan.tasks)}（已验证 {counts['verified']} · "
        f"已跳过 {counts['skipped']}）"
    )
    if incomplete:
        message += f"；还有 {len(incomplete)} 步未完成："
        message += "、".join(
            f"{item['title']}（{item['status']}）" for item in incomplete
        )
    else:
        message += "——全部步骤完成，可以打包交付。"
    if notes:
        message += "；" + "；".join(notes)
    return {
        "ok": not incomplete,
        "plan_present": True,
        "stats": counts,
        "incomplete": incomplete,
        "message": message,
    }


def package_project(output_dir: Path) -> dict:
    """一键打包：工程目录 → zip（父目录，时间戳命名不覆盖旧包）。

    排除规则：文件名 `.contest_*` 前缀（内部状态文件——留在工程目录原处，
    不进交付包）、`*.tmp`、`*.bak`。返回 {"zip_path", "size", "files",
    "message"}。目录缺失 → DeliveryError。
    """
    if not output_dir.is_dir():
        raise DeliveryError(f"输出目录不存在：{output_dir}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = output_dir.parent / f"{output_dir.name}-交付-{stamp}"
    zip_path = Path(f"{base}.zip")
    serial = 2
    while zip_path.exists():  # 同秒重打包：追加序号不覆盖旧包
        zip_path = Path(f"{base}-{serial}.zip")
        serial += 1
    files = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith(".contest_"):
                continue
            if path.suffix.lower() in (".tmp", ".bak"):
                continue
            zf.write(path, path.relative_to(output_dir).as_posix())
            files += 1
    size = zip_path.stat().st_size
    return {
        "zip_path": str(zip_path),
        "size": size,
        "files": files,
        "message": f"已打包 {files} 个文件：{zip_path.name}（{size} 字节）",
    }
