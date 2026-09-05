#!/usr/bin/env python
"""端到端演练：小发版更新全链路（工单 auto-update/07）。

在临时目录构造「假新版」本地 mock 更新源（release JSON + zip + sha256 +
removed），从假旧版工具根走：检查更新 → 下载 + SHA256 校验 → 更新器
（停服/重启跳过，目录替换全真）→ 验证版本号更新、配置保留、资料库未动、
备份生成、git 仓库未受影响（git pull 路线）。

运行：python .scratch/auto-update/e2e/e2e_update.py
输出：演练结论（断言失败 = 非 0 退出）。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]  # .scratch/auto-update/e2e → 仓库根
sys.path.insert(0, str(REPO / "src"))

from contest_generator.update import check_for_update  # noqa: E402
from contest_generator.webapp import download_to  # noqa: E402

# tools/update-app.py 文件名带连字符，不能按模块名 import —— 用 importlib
# 加载并注册 sys.modules（dataclass 注解解析依赖模块注册，同测试先例）
_spec = importlib.util.spec_from_file_location(
    "update_app", REPO / "tools" / "update-app.py"
)
assert _spec and _spec.loader is not None
updater = importlib.util.module_from_spec(_spec)
sys.modules["update_app"] = updater
_spec.loader.exec_module(updater)

STEPS: list[str] = []


def step(name: str) -> None:
    STEPS.append(name)
    print(f"[演练] {name}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_fake_root(tmp: Path) -> Path:
    """假旧版工具根：只留更新所需的最小文件集 + 模拟资料库/venv/用户数据。"""
    root = tmp / "firstep-root"
    (root / "src" / "contest_generator").mkdir(parents=True)
    (root / "tools").mkdir(parents=True)
    (root / "sources" / "materials").mkdir(parents=True)
    (root / ".venv" / "Scripts").mkdir(parents=True)
    (root / "src" / "contest_generator" / "__init__.py").write_text(
        '__version__ = "1.0.0"\n', encoding="utf-8"
    )
    (root / "pyproject.toml").write_text("project v1\n", encoding="utf-8")
    (root / "VERSIONS.md").write_text("v1.0.0\n", encoding="utf-8")
    (root / "old.txt").write_text("bye", encoding="utf-8")
    (root / "start-app.vbs").write_text("' fake\n", encoding="utf-8")
    shutil.copy2(REPO / "tools" / "update-app.py", root / "tools" / "update-app.py")
    (root / "sources" / "materials" / "big-tool.zip").write_bytes(b"BIG" * 1000)
    (root / ".venv" / "Scripts" / "python.exe").write_bytes(b"FakePython")
    return root


def build_update_package(tmp: Path) -> tuple[Path, Path, str]:
    """假新版更新包：zip（src 新版本 + VERSIONS + pyproject 同 + 新文件）、
    removed.txt（删 old.txt）、返回 (zip, removed, sha256)。"""
    root = tmp / "pkg"
    root.mkdir()
    (root / "src" / "contest_generator").mkdir(parents=True)
    (root / "src" / "contest_generator" / "__init__.py").write_text(
        '__version__ = "1.1.0"\n', encoding="utf-8"
    )
    (root / "VERSIONS.md").write_text("v1.0.0\n\n## v1.1.0 (2026-09-02)\n- 新增：测试\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("project v1\n", encoding="utf-8")  # 相同 → 跳过 pip
    (root / "NEW.md").write_text("hello new\n", encoding="utf-8")
    zip_path = tmp / "firstep-update-v1.1.0.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(root.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(root).as_posix())
    removed = tmp / "firstep-update-v1.1.0.removed.txt"
    removed.write_text("old.txt\n", encoding="utf-8")
    return zip_path, removed, sha256_of(zip_path)


class MockServer:
    """本地 mock GitHub：/releases/latest + /files/*。"""

    def __init__(self, zip_path: Path, removed: Path, sha256: str):
        self.zip_path = zip_path
        self.removed = removed
        self.sha256 = sha256
        self.port = 0
        self._server: HTTPServer | None = None

    def start(self) -> str:
        def handler_factory():
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):  # noqa: N802
                    server = self.server  # type: ignore[attr-defined]
                    port = server.server_address[1]
                    zip_path = server.zip_path  # 挂在 server 实例上（Handler 无闭包）
                    removed = server.removed
                    sha256 = server.sha256
                    if self.path == "/releases/latest":
                        payload = {
                            "tag_name": "v1.1.0",
                            "body": "测试新版说明",
                            "published_at": "2026-09-02T00:00:00Z",
                            "assets": [
                                {
                                    "name": "firstep-update-v1.1.0.zip",
                                    "browser_download_url": f"http://127.0.0.1:{port}/files/firstep-update-v1.1.0.zip",
                                    "size": zip_path.stat().st_size,
                                },
                                {
                                    "name": "firstep-update-v1.1.0.sha256.txt",
                                    "browser_download_url": f"http://127.0.0.1:{port}/files/firstep-update-v1.1.0.sha256.txt",
                                    "size": 92,
                                },
                                {
                                    "name": "firstep-update-v1.1.0.removed.txt",
                                    "browser_download_url": f"http://127.0.0.1:{port}/files/firstep-update-v1.1.0.removed.txt",
                                    "size": removed.stat().st_size,
                                },
                            ],
                        }
                        data = json.dumps(payload).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    if self.path == f"/files/firstep-update-v1.1.0.zip":
                        data = zip_path.read_bytes()
                    elif self.path == f"/files/firstep-update-v1.1.0.removed.txt":
                        data = removed.read_bytes()
                    elif self.path == f"/files/firstep-update-v1.1.0.sha256.txt":
                        data = (sha256 + "  firstep-update-v1.1.0.zip\n").encode("utf-8")
                    else:
                        self.send_response(404)
                        self.end_headers()
                        return
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

                def log_message(self, *args):  # 静默
                    pass

            return Handler

        self._server = HTTPServer(("127.0.0.1", 0), handler_factory())
        self._server.zip_path = self.zip_path  # type: ignore[attr-defined]
        self._server.removed = self.removed  # type: ignore[attr-defined]
        self._server.sha256 = self.sha256  # type: ignore[attr-defined]
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self.port}"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="firstep-e2e-"))
    try:
        root = build_fake_root(tmp)
        data_dir = tmp / "user-data"
        (data_dir / "updates").mkdir(parents=True)
        (data_dir / "config.json").write_text(
            '{"api_key":"sk-fake","task":"keep-me"}', encoding="utf-8"
        )
        zip_path, removed, sha = build_update_package(tmp)
        server = MockServer(zip_path, removed, sha)
        base = server.start()
        step("① mock 更新源就绪（检查/zip/sha256/removed）")

        # --- 检查更新（真实 HTTP，注入本地 mock：把 GitHub API 前缀重写为
        # mock base，资产 URL 在 MockServer payload 里已指向 mock）---
        def fetch_json(url: str):
            import urllib.request

            real = base + "/releases/latest"  # mock 固定路径（资产 URL 已指向 mock）
            with urllib.request.urlopen(real, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))

        def fetch_text(url: str) -> str:
            import urllib.request

            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.read().decode("utf-8")

        check = check_for_update("1.0.0", fetch_json, fetch_text)
        assert check["update_available"] is True, check
        assert check["latest_version"] == "1.1.0", check
        assert check["sha256"] == sha, "sha256 契约不符"
        assert check["removed_url"], "removed_url 缺失"
        step("② 检查更新：发现 v1.1.0，sha256/removed 契约齐")

        # --- 下载 + 校验（模拟 apply 的下载段，真实 HTTP → 流式 + SHA256）---
        updates = data_dir / "updates"
        zip_local = updates / "firstep-update-v1.1.0.zip"
        actual = download_to(check["zip_url"], zip_local)
        assert actual == sha, "下载后 SHA256 不匹配"
        (updates / "firstep-update-v1.1.0.removed.txt").write_text(
            removed.read_text(encoding="utf-8"), encoding="utf-8"
        )
        step("③ 下载 + SHA256 校验通过（真实 HTTP）")

        # --- 写待更新标记 → 更新器（停服/重启跳过，替换全真）---
        (updates / "pending-update.json").write_text(
            json.dumps({"version": "v1.1.0", "zip": str(zip_local)}),
            encoding="utf-8",
        )
        opts = updater.UpdateOptions(
            zip_path=zip_local,
            removed_path=updates / "firstep-update-v1.1.0.removed.txt",
            root=root,
            data_dir=data_dir,
            stop=False,
            restart=False,
            check_deps=True,
        )
        rc = updater.run_update(opts)
        assert rc == 0, f"更新器退出码 {rc}"
        step("④ 更新器执行完成（备份/覆盖/删除/依赖判定）")

        # --- 验证 ---
        init_py = root / "src" / "contest_generator" / "__init__.py"
        assert "__version__" in init_py.read_text(encoding="utf-8")
        assert '"1.1.0"' in init_py.read_text(encoding="utf-8"), "版本号未更新"
        assert (root / "NEW.md").read_text(encoding="utf-8") == "hello new\n"
        assert not (root / "old.txt").exists(), "removed 未删除"
        assert (data_dir / "config.json").read_text(encoding="utf-8") == (
            '{"api_key":"sk-fake","task":"keep-me"}'
        ), "用户配置被改动"
        assert (root / "sources" / "materials" / "big-tool.zip").exists(), "资料库被动"
        assert (root / ".venv" / "Scripts" / "python.exe").exists(), ".venv 被动"
        backups = list((updates / "backup").glob("*"))
        assert len(backups) == 1, "备份目录数量异常"
        backup = backups[0]
        assert (backup / "src" / "contest_generator" / "__init__.py").exists(), (
            "被覆盖文件未备份"
        )
        assert (backup / "VERSIONS.md").exists(), "被覆盖文件未备份"
        result = json.loads((updates / "last-update.json").read_text(encoding="utf-8"))
        assert result["status"] == "ok" and result["version"] == "v1.1.0", result
        step("⑤ 验证：版本 1.1.0 / 新文件落位 / removed 删除 / 配置保留 / 资料库与 .venv 未动")

        # --- git pull 路线不受影响 ---
        git_ok = subprocess.run(
            ["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
        ).returncode == 0
        archive_ok = subprocess.run(
            ["git", "-C", str(REPO), "archive", "--format=zip", "HEAD", "--", "src"],
            capture_output=True,
        ).returncode == 0
        assert git_ok and archive_ok, "git 仓库异常（git pull 路线受损）"
        step("⑥ git pull 路线未受影响（status / archive HEAD 正常）")

        print("=== 端到端演练通过（6 步全绿）===")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
