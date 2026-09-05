#!/usr/bin/env python
"""firstep 应用内更新器（工单 auto-update/04）——独立进程替换工具目录。

用法（由「一键更新」端点以独立进程拉起；也可手动运行）：
    .venv\\Scripts\\python.exe tools\\update-app.py --zip <firstep-update-vX.Y.Z.zip> [选项]

流程：停服（8000 LISTENING 先经 /api/health 确认是本应用再 kill，不误杀）
→ zip 条目安全校验（zip slip 整体拒绝）→ 备份将被覆盖的条目到
`<data-dir>\\updates\\backup\\<时间戳>\\` → 解压覆盖工具根（`.venv` /
`.contest_generator` / `sources/materials` 不在包内 = 天然保留）→ 按
removed.txt 删除（路径校验落工具根内）→ 依赖变更检测（覆盖前后
pyproject.toml SHA256 对比，变了才 pip install -e .）→ 清
`updating.lock` 与 `pending-update.json` → start-app.vbs 重启。

全流程日志写 `<data-dir>\\updates\\updater.log`；失败保留备份并提示位置
（不做自动回滚）。仅依赖标准库（zipfile / urllib / subprocess）。

测试友好：核心逻辑在 `run_update(opts)`，`main()` 只做参数解析与退出码；
`--no-stop --no-restart --skip-pip` 供集成测试在临时目录完整演练。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from optparse import OptionParser
from pathlib import Path
from typing import Any, Callable, Sequence

APP_ID = "contest-generator"
HEALTH_PATH = "/api/health"
DEFAULT_PORT = 8000
DEFAULT_DATA_DIR = Path.home() / ".contest_generator"


class UpdateError(RuntimeError):
    """更新流程错误（中文 message；调用方按非 0 退出码处理）。"""


@dataclass
class UpdateOptions:
    """run_update 的入参（命令行选项的解析结果）。"""

    zip_path: Path
    removed_path: Path | None = None
    root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    data_dir: Path = DEFAULT_DATA_DIR
    port: int = DEFAULT_PORT
    stop: bool = True
    restart: bool = True
    check_deps: bool = True
    log: logging.Logger | None = None

    @property
    def updates_dir(self) -> Path:
        return self.data_dir / "updates"

    @property
    def updater_log_path(self) -> Path:
        return self.updates_dir / "updater.log"

    @property
    def lock_path(self) -> Path:
        return self.updates_dir / "updating.lock"

    @property
    def pending_path(self) -> Path:
        return self.updates_dir / "pending-update.json"

    @property
    def result_path(self) -> Path:
        return self.updates_dir / "last-update.json"


# ---------------------------------------------------------------------------
# 停服：确认本体 → kill（避免误杀其他占用 8000 的程序）
# ---------------------------------------------------------------------------


def find_listening_pids(port: int) -> list[str]:
    """netstat -ano 解析：返回监听 port 的 PID 列表（标准库 subprocess）。"""
    try:
        output = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception as exc:  # netstat 不可用属于环境异常，报错不静默
        raise UpdateError(f"netstat 执行失败：{exc}") from exc
    pids: list[str] = []
    for line in output.splitlines():
        parts = line.split()
        # 形如：TCP  127.0.0.1:8000  0.0.0.0:0  LISTENING  12345
        if len(parts) >= 5 and parts[-2] == "LISTENING" and f":{port}" in parts[1]:
            pid = parts[-1]
            if pid not in pids:
                pids.append(pid)
    return pids


def is_firstep_service(host: str, port: int, timeout: float = 2.0) -> bool:
    """GET /api/health 判定端口上是不是本应用（故意不依赖任何配置）。"""
    try:
        with urllib.request.urlopen(
            f"http://{host}:{port}{HEALTH_PATH}", timeout=timeout
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("app") == APP_ID
    except Exception:
        return False


def stop_service(port: int, log: Callable[[str], None]) -> None:
    """停掉监听 port 的本应用；确认不是本应用 → 拒绝（防误杀）。"""
    pids = find_listening_pids(port)
    if not pids:
        log(f"端口 {port} 无监听进程，跳过停服")
        return
    if not is_firstep_service("127.0.0.1", port):
        raise UpdateError(
            f"端口 {port} 被其他程序占用（已确认不是本应用），拒绝停服——"
            "请先关闭占用该端口的程序后重试"
        )
    for pid in pids:
        log(f"停服：结束本应用进程 PID {pid}")
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)


# ---------------------------------------------------------------------------
# 安全路径：zip 条目 / removed 清单都必须落在工具根内（zip slip 防护）
# ---------------------------------------------------------------------------


def safe_join(root: Path, name: str) -> Path:
    """把 zip 内相对路径安全映射到 root 下；越界（../、绝对路径、盘符、
    前缀逃逸）抛 UpdateError。覆盖前对全部条目预检，任一越界整体拒绝。"""
    normalized = name.replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        raise UpdateError(f"更新包内含非法路径（绝对路径）：{name}")
    pure = Path(normalized)
    if pure.is_absolute() or pure.drive:
        raise UpdateError(f"更新包内含非法路径（盘符/绝对）：{name}")
    if ".." in pure.parts:
        raise UpdateError(f"更新包内含越界路径（..）：{name}")
    root_resolved = root.resolve()
    target = (root / pure).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise UpdateError(f"更新包内含越界路径（逃逸解析）：{name}")
    return target


def validate_zip_members(zip_path: Path, root: Path) -> list[zipfile.ZipInfo]:
    """预检全部 zip 成员：目录条目跳过，文件条目逐个 safe_join；
    任一非法 → 抛 UpdateError（此时尚未写任何文件，整体拒绝）。"""
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            for member in members:
                safe_join(root, member.filename)
            return members
    except zipfile.BadZipFile as exc:
        raise UpdateError(f"更新包不是有效的 zip：{exc}") from exc


# ---------------------------------------------------------------------------
# 备份 / 解压 / 删除
# ---------------------------------------------------------------------------


def backup_overwritten(
    root: Path, members: Sequence[zipfile.ZipInfo], backup_dir: Path
) -> int:
    """备份「将被覆盖且已存在」的普通文件（相对路径镜像）；返回备份数。"""
    count = 0
    for member in members:
        target = safe_join(root, member.filename)
        if target.is_file():
            dest = backup_dir / member.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            count += 1
    return count


def extract_zip(zip_path: Path, root: Path, members: Sequence[zipfile.ZipInfo]) -> int:
    """逐条目解压覆盖：先写 `<目标>.update-tmp` 再 os.replace（不半写）。"""
    count = 0
    with zipfile.ZipFile(zip_path) as archive:
        for member in members:
            target = safe_join(root, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".update-tmp")
            with archive.open(member) as source, open(tmp, "wb") as dest:
                shutil.copyfileobj(source, dest)
            os.replace(tmp, target)
            count += 1
    return count


def remove_removed_list(
    removed_path: Path | None, root: Path, log: Callable[[str], None]
) -> int:
    """按 removed.txt 删除已废弃文件（路径校验落工具根内；不存在跳过）。"""
    if removed_path is None or not removed_path.exists():
        log("无删除清单，跳过删除")
        return 0
    count = 0
    for raw_line in removed_path.read_text(encoding="utf-8-sig").splitlines():
        name = raw_line.strip()
        if not name or name.startswith("#"):
            continue
        target = safe_join(root, name)
        if target.is_file():
            target.unlink()
            count += 1
            log(f"删除已废弃文件：{name}")
        elif target.exists():
            log(f"跳过（非普通文件）：{name}")
        else:
            log(f"跳过（已不存在）：{name}")
    return count


# ---------------------------------------------------------------------------
# 依赖变更检测（覆盖前后 pyproject.toml 哈希对比，自包含、无隐式状态）
# ---------------------------------------------------------------------------


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pick_python(root: Path) -> str:
    """解释器：`.venv\\Scripts\\python.exe` 优先、系统 Python 兜底。"""
    venv = root / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        return str(venv)
    return sys.executable


def install_dependencies(root: Path, python: str) -> None:
    """pyproject 变了才跑 `pip install -e .`（失败抛错，不静默）。"""
    result = subprocess.run(
        [python, "-m", "pip", "install", "-e", str(root)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
        raise UpdateError("依赖安装失败（pip install -e . 退出码 "
                          f"{result.returncode}）：" + " / ".join(tail))


# ---------------------------------------------------------------------------
# 重启
# ---------------------------------------------------------------------------


def restart_app(root: Path, log: Callable[[str], None]) -> None:
    """调 start-app.vbs 重启（隐藏窗口，浏览器自动打开）。"""
    vbs = root / "start-app.vbs"
    if not vbs.is_file():
        raise UpdateError(f"未找到启动器：{vbs}")
    log("重启应用（start-app.vbs）")
    os.startfile(str(vbs))  # noqa: S606 — Windows 专用，无等待


def version_of(zip_path: Path) -> str:
    """从 `firstep-update-v1.1.0.zip` 提取版本标记 `v1.1.0`（结果记录用）。"""
    stem = zip_path.name
    for prefix in ("firstep-update-",):
        if stem.startswith(prefix):
            stem = stem.removeprefix(prefix)
    suffix = ".zip"
    if stem.endswith(suffix):
        stem = stem.removesuffix(suffix)
    return stem


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def _make_logger(path: Path) -> logging.Logger:
    logger = logging.getLogger("firstep-updater")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(logging.StreamHandler(sys.stdout))
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.addHandler(logging.FileHandler(path, encoding="utf-8"))
    return logger


def run_update(opts: UpdateOptions) -> int:
    """执行更新；返回进程退出码（0 = 成功；1 = 失败已保留备份与标记）。

    失败不删 pending-update.json（启动器据此提示手动处理）；无论成败都清
    updating.lock（更新器已退出，恢复启动器可用性）。
    """
    root = opts.root.resolve()
    if not root.is_dir():
        print(f"[错误] 工具根目录不存在：{root}", file=sys.stderr)
        return 1
    if not opts.zip_path.is_file():
        print(f"[错误] 更新包不存在：{opts.zip_path}", file=sys.stderr)
        return 1

    log = (opts.log or _make_logger(opts.updater_log_path)).info
    updates_dir = opts.updates_dir
    updates_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = updates_dir / "backup" / timestamp
    opts.lock_path.write_text(str(int(time.time() * 1000)), encoding="utf-8")

    try:
        log(f"=== firstep 更新开始（{timestamp}）===")
        log(f"更新包：{opts.zip_path}")
        log(f"工具根：{root}")

        # 1. zip slip 全量预检（未写盘前拒绝）
        members = validate_zip_members(opts.zip_path, root)
        log(f"更新包条目 {len(members)} 个，安全校验通过")

        # 2. 停服（确认是本应用才 kill）
        if opts.stop:
            stop_service(opts.port, log)
        else:
            log("跳过停服（--no-stop）")

        # 3. 备份将被覆盖的条目
        backup_count = backup_overwritten(root, members, backup_dir)
        log(f"已备份 {backup_count} 个将被覆盖的文件到 {backup_dir}")

        # 4. 覆盖前记录依赖指纹（缺失 = 无旧记录，走「变了」语义 ——
        #    首次更新只要包内带 pyproject 就装依赖，等价于“记录缺失则装”）
        old_pyproject_hash = file_sha256(root / "pyproject.toml")

        # 5. 解压覆盖
        written = extract_zip(opts.zip_path, root, members)
        log(f"已落位 {written} 个文件")

        # 6. 按删除清单清理
        removed_count = remove_removed_list(opts.removed_path, root, log)
        log(f"已删除 {removed_count} 个废弃文件")

        # 7. 依赖变更检测：覆盖前后 pyproject.toml 哈希对比
        if opts.check_deps:
            new_pyproject_hash = file_sha256(root / "pyproject.toml")
            if old_pyproject_hash != new_pyproject_hash:
                python = pick_python(root)
                log("pyproject.toml 已变化，重装依赖（pip install -e .）…")
                install_dependencies(root, python)
            else:
                log("pyproject.toml 未变化，跳过依赖安装")
        else:
            log("跳过依赖检测与安装（--skip-pip）")

        # 8. 清待更新标记（成功才算完成）
        if opts.pending_path.exists():
            opts.pending_path.unlink()
            log("已清除待更新标记（pending-update.json）")

        # 8b. 记录结果（status 端点据此报 done）
        result = {
            "status": "ok",
            "version": version_of(opts.zip_path),
            "finished_at": timestamp,
            "backup_dir": str(backup_dir),
        }
        opts.result_path.write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
        log(f"已记录更新结果：{opts.result_path}")

        # 9. 重启
        if opts.restart:
            restart_app(root, log)
        else:
            log("跳过重启（--no-restart）")

        log("=== 更新完成 ===")
        return 0
    except Exception as exc:
        log(f"[失败] {exc}")
        log(f"[失败] 备份保留在：{backup_dir}（未自动回滚）；"
            f"日志：{opts.updater_log_path}")
        # 失败也留结果（status 端点报 failed），pending 保留供启动器提示
        opts.result_path.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(exc),
                    "finished_at": timestamp,
                    "backup_dir": str(backup_dir),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"[失败] {exc}", file=sys.stderr)
        print(f"[失败] 备份保留在：{backup_dir}", file=sys.stderr)
        return 1
    finally:
        if opts.lock_path.exists():
            opts.lock_path.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    parser = OptionParser(usage="%prog --zip <更新包.zip> [选项]")
    parser.add_option("--zip", dest="zip_path", metavar="PATH", help="更新包 zip 路径（必填）")
    parser.add_option("--removed", dest="removed_path", metavar="PATH", help="removed.txt 路径（可选）")
    parser.add_option("--root", dest="root", metavar="PATH", help="工具根目录（默认 = 本脚本上级目录）")
    parser.add_option("--data-dir", dest="data_dir", metavar="PATH", help="用户数据目录（默认 ~/.contest_generator）")
    parser.add_option("--port", dest="port", type="int", default=DEFAULT_PORT, help=f"服务端口（默认 {DEFAULT_PORT}）")
    parser.add_option("--no-stop", action="store_true", dest="no_stop", default=False, help="跳过停服（测试用）")
    parser.add_option("--no-restart", action="store_true", dest="no_restart", default=False, help="跳过重启（测试用）")
    parser.add_option("--skip-pip", action="store_true", dest="skip_pip", default=False, help="跳过依赖检测与安装（测试用）")
    options, _args = parser.parse_args(list(argv) if argv is not None else None)

    if not options.zip_path:
        parser.error("缺少必填参数 --zip")
    root = Path(options.root) if options.root else Path(__file__).resolve().parent.parent
    opts = UpdateOptions(
        zip_path=Path(options.zip_path),
        removed_path=Path(options.removed_path) if options.removed_path else None,
        root=root,
        data_dir=Path(options.data_dir) if options.data_dir else DEFAULT_DATA_DIR,
        port=options.port,
        stop=not options.no_stop,
        restart=not options.no_restart,
        check_deps=not options.skip_pip,
    )
    return run_update(opts)


if __name__ == "__main__":
    sys.exit(main())
