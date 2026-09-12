"""完整包应用编排（工单 full-download/04）。

下载全部校验通过后要做的三件事，**全都不在 webapp 进程内做替换**：
1. 写待更新标记 `pending-update.json`（版本 + 分卷表 + 清单路径，供排障与启动器提示）；
2. 以**独立进程**拉起 `tools/update-app.py`（停服 → 备份 → 覆盖 → 写资料库基线
   → 按清单删废弃文件 → 按需装依赖 → 重启都由它自己做）；
3. 返回摘要给任务状态。

替换动作绝不在运行中的 webapp 进程里执行：Windows 上正在运行的 python 进程
占着自己的 `.py` / `.pyd`，就地覆盖必失败（既有小发版更新器的同款决策）。

`spawn` 可注入：测试只断言「拉起的是哪条命令」，不真起进程。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

PENDING_FILENAME = "pending-update.json"
LOG_FILENAME = "full-apply.log"


@dataclass
class FullApplyResult:
    """编排摘要（任务状态与前端文案用）。"""

    ok: bool
    version: str = ""
    command: list[str] = field(default_factory=list)
    log_path: str = ""
    message: str = ""


def _python_for(root: Path) -> str:
    """解释器：`.venv\\Scripts\\python.exe` 优先、当前解释器兜底。"""
    venv = root / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.is_file() else sys.executable


def build_updater_command(
    *,
    root: Path,
    python: str,
    manifest_location: str,
    parts: Sequence[Path],
    port: int,
) -> list[str]:
    """更新器命令行：完整包模式（--full-manifest + 逐个 --part）。"""
    updater = root / "tools" / "update-app.py"
    command = [
        python,
        str(updater),
        "--zip",
        str(parts[0]),
        "--root",
        str(root),
        "--full-manifest",
        str(manifest_location),
        "--port",
        str(port),
    ]
    for part in parts:
        command += ["--part", str(part)]
    return command


def default_spawn(command: Sequence[str], cwd: Path, log_path: Path) -> int:
    """起独立进程（不等待）：stdout/stderr 落 `full-apply.log`，失败抛 OSError。"""
    import subprocess

    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log_path, "a", encoding="utf-8")
    try:
        process = subprocess.Popen(  # noqa: S603 - 命令由本模块构造，无外部输入
            list(command),
            cwd=str(cwd),
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        handle.close()
        raise
    return process.pid


def apply_full_package(
    *,
    parts: Sequence[dict[str, Any]],
    updates_dir: Path,
    tool_root: Path,
    version: str = "",
    manifest_url: str = "",
    port: int = 8000,
    python: str | None = None,
    spawn: Callable[[Sequence[str], Path, Path], int] = default_spawn,
) -> FullApplyResult:
    """写出待更新标记 → 拉起更新器 → 返回摘要。

    `parts` = 任务的就绪分卷（`{name, path, ...}`，按清单顺序）；`manifest_url`
    = 完整包清单地址（本地路径或 URL，更新器自己读——清单含全量文件清单，
    几 MB 级，不在浏览器与后端之间搬运）。
    """
    updates_dir = Path(updates_dir)
    tool_root = Path(tool_root)
    updates_dir.mkdir(parents=True, exist_ok=True)

    if not manifest_url.strip():
        # 没有清单就没法安全替换：删除清单与资料库基线都在清单里
        return FullApplyResult(
            ok=False,
            version=version,
            message="缺少完整包清单地址，无法应用（请重新检查更新）",
        )

    part_paths = [Path(str(p.get("path") or "")) for p in parts]
    missing = [str(p) for p in part_paths if not p.is_file()]
    if not part_paths or missing:
        return FullApplyResult(
            ok=False,
            version=version,
            message="分卷未就绪：" + ("、".join(missing) if missing else "（空分卷表）"),
        )

    pending = {
        "mode": "full",
        "version": version,
        "parts": [p.name for p in part_paths],
        "manifest": manifest_url,
        "created_at": _now_stamp(),
    }
    (updates_dir / PENDING_FILENAME).write_text(
        json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log_path = updates_dir / LOG_FILENAME
    command = build_updater_command(
        root=tool_root,
        python=python or _python_for(tool_root),
        manifest_location=manifest_url,
        parts=part_paths,
        port=port,
    )
    try:
        spawn(command, tool_root, log_path)
    except Exception as exc:  # 拉起失败：标记保留，前端可提示手动处理
        return FullApplyResult(
            ok=False,
            version=version,
            command=command,
            log_path=str(log_path),
            message=f"拉起更新器失败：{exc}",
        )
    return FullApplyResult(
        ok=True,
        version=version,
        command=command,
        log_path=str(log_path),
        message=(
            f"已开始应用完整包 {version or ''}（{len(part_paths)} 卷）："
            "工具将自动停止并重启"
        ).replace("  ", " "),
    )


def _now_stamp() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%S")
